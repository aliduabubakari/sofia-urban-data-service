from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import numpy as np
import math
import geopandas as gpd
import pandas as pd
from geoalchemy2.elements import WKBElement
from shapely.geometry.base import BaseGeometry

from suds_core.config.logging import configure_logging
from suds_core.config.settings import get_settings

logger = configure_logging("INFO", "suds.ingest")


try:
    import pyogrio  # type: ignore
except Exception:  # pragma: no cover
    pyogrio = None


@dataclass(frozen=True)
class SourceSpec:
    """
    Defines how to load a dataset from disk.
    """
    path: Path
    layer: Optional[str] = None
    source_id_col: Optional[str] = None   # store this into `source_id` (string)
    expected_geom: str = "GEOMETRY"       # POINT | MULTIPOLYGON | MULTILINESTRING | GEOMETRY
    force_2d: bool = True


def _safe_make_valid(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Fix invalid geometries using shapely.make_valid if available; else buffer(0) fallback.
    """
    try:
        from shapely import make_valid  # shapely>=2
        gdf["geometry"] = gdf["geometry"].apply(lambda g: make_valid(g) if g is not None else None)
        return gdf
    except Exception:
        # buffer(0) works for many polygon issues but not all
        try:
            gdf["geometry"] = gdf["geometry"].buffer(0)
        except Exception:
            pass
        return gdf


def _force_2d_geom(geom: BaseGeometry) -> BaseGeometry:
    """
    Remove Z dimension if present.
    """
    try:
        from shapely import force_2d  # shapely>=2
        return force_2d(geom)
    except Exception:
        # Shapely<2 fallback: reconstruct via WKB ignoring Z not trivial.
        # Most PostGIS setups accept Z even if column is POINT, so we can return as-is.
        return geom


def _normalize_geometry_type(gdf: gpd.GeoDataFrame, expected: str) -> gpd.GeoDataFrame:
    expected = expected.upper().strip()
    if expected in ("GEOMETRY", "", None):
        return gdf

    # explode MultiPoint -> Point rows for POIs if needed
    if expected == "POINT":
        if (gdf.geometry.geom_type == "MultiPoint").any():
            gdf = gdf.explode(index_parts=False).reset_index(drop=True)
        # ensure points only
        gdf = gdf[gdf.geometry.geom_type.isin(["Point"])].copy()
        return gdf

    if expected == "MULTIPOLYGON":
        # polygons -> multipolygons
        gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
        gdf["geometry"] = gdf["geometry"].apply(lambda g: g if g is None else _to_multipolygon(g))
        return gdf

    if expected == "MULTILINESTRING":
        gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
        gdf["geometry"] = gdf["geometry"].apply(lambda g: g if g is None else _to_multilinestring(g))
        return gdf

    return gdf


def _to_multipolygon(g: BaseGeometry) -> BaseGeometry:
    from shapely.geometry import MultiPolygon, Polygon
    if g.geom_type == "MultiPolygon":
        return g
    if g.geom_type == "Polygon":
        return MultiPolygon([g])  # type: ignore[arg-type]
    return g


def _to_multilinestring(g: BaseGeometry) -> BaseGeometry:
    from shapely.geometry import LineString, MultiLineString
    if g.geom_type == "MultiLineString":
        return g
    if g.geom_type == "LineString":
        return MultiLineString([g])  # type: ignore[arg-type]
    return g


def load_geodataframe(spec: SourceSpec) -> gpd.GeoDataFrame:
    """
    Load with pyogrio if available (faster), else geopandas.
    """
    path = str(spec.path)
    if pyogrio is not None:
        gdf = pyogrio.read_dataframe(path, layer=spec.layer)
        gdf = gpd.GeoDataFrame(gdf, geometry="geometry")
    else:
        gdf = gpd.read_file(path, layer=spec.layer)

    return gdf

def clean_and_reproject(gdf: gpd.GeoDataFrame, *, target_epsg: int = 4326, spec: Optional[SourceSpec] = None) -> gpd.GeoDataFrame:
    settings = get_settings()

    # Drop empty/null
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    # Ensure CRS
    if gdf.crs is None:
        raise ValueError("Source has no CRS defined. Provide a CRS before ingesting (fix source file or add override).")

    # Fix invalid
    invalid = (~gdf.geometry.is_valid).sum()
    if invalid:
        logger.info(f"Fixing {invalid} invalid geometries...")
        gdf = _safe_make_valid(gdf)
        gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    # Force 2D
    if spec and spec.force_2d:
        gdf["geometry"] = gdf["geometry"].apply(lambda g: _force_2d_geom(g) if g is not None else None)

    # Normalize geometry type
    if spec:
        gdf = _normalize_geometry_type(gdf, spec.expected_geom)

    # Reproject to WGS84 (4326)
    if str(gdf.crs).upper() != f"EPSG:{target_epsg}":
        gdf = gdf.to_crs(epsg=target_epsg)

    # Final cleanup
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()

    # Keep only valid geoms (optional strictness)
    gdf = gdf[gdf.geometry.is_valid].copy()

    return gdf

def sanitize_json_value(v: Any) -> Any:
    """
    Convert values into PostgreSQL-JSON-safe equivalents.
    Postgres JSON does NOT allow NaN/Infinity.
    """
    if v is None:
        return None

    # pandas NA / numpy NaN
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    # numpy scalar -> python scalar
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        v = float(v)

    # float: remove NaN/inf
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v

    # containers: sanitize recursively
    if isinstance(v, dict):
        return {str(k): sanitize_json_value(val) for k, val in v.items()}
    if isinstance(v, (list, tuple)):
        return [sanitize_json_value(x) for x in v]

    # primitives ok
    if isinstance(v, (str, int, bool)):
        return v

    # fallback: string
    return str(v)


def gdf_to_mappings(
    gdf,
    *,
    source_id_col: Optional[str],
    srid: int = 4326,
) -> list[dict[str, Any]]:
    """
    Convert a GeoDataFrame chunk into mappings for SQLAlchemy bulk_insert_mappings,
    ensuring JSONB-safe props (no NaN/inf).
    """
    if len(gdf) == 0:
        return []

    df_props = gdf.drop(columns=["geometry"], errors="ignore").copy()
    df_props = df_props.astype("object")

    # Replace pandas/numpy missing values with None
    df_props = df_props.where(pd.notna(df_props), None)

    # Avoid DataFrame.applymap deprecation: map per column
    df_props = df_props.apply(lambda col: col.map(sanitize_json_value))

    props_records = df_props.to_dict(orient="records")

    # SECOND PASS (CRITICAL): sanitize dicts recursively again.
    # This guarantees no NaN survives even if pandas created float('nan') again.
    props_records = [sanitize_json_value(rec) for rec in props_records]

    # source_id
    if source_id_col and source_id_col in df_props.columns:
        source_ids = [
            None if v is None else str(v)
            for v in df_props[source_id_col].tolist()
        ]
    else:
        source_ids = [None] * len(gdf)

    # geometry -> WKBElement
    try:
        from shapely import to_wkb  # shapely>=2
        wkbs = [to_wkb(geom, hex=False) for geom in gdf.geometry.tolist()]
    except Exception:
        wkbs = [geom.wkb for geom in gdf.geometry.tolist()]

    geoms = [WKBElement(wkb, srid=srid) for wkb in wkbs]

    out: list[dict[str, Any]] = []
    for sid, props, geom in zip(source_ids, props_records, geoms):
        out.append({"source_id": sid, "props": props, "geom": geom})
    return out

def row_to_record(
    row: Any,
    *,
    source_id_col: Optional[str],
    drop_cols: tuple[str, ...] = ("geometry",),
) -> dict[str, Any]:
    """
    Row-wise converter (safe but slower). Uses the same sanitization rules as gdf_to_mappings().
    """
    geom = row.geometry
    if geom is None:
        raise ValueError("Row geometry is None")

    props: dict[str, Any] = {}
    for k, v in row.items():
        if k in drop_cols:
            continue
        props[k] = sanitize_json_value(v)

    source_id = None
    if source_id_col and source_id_col in row and row[source_id_col] is not None:
        source_id = str(row[source_id_col])

    try:
        from shapely import to_wkb  # shapely>=2
        wkb = to_wkb(geom, hex=False)
    except Exception:
        wkb = geom.wkb

    return {"source_id": source_id, "props": props, "geom": WKBElement(wkb, srid=4326)}