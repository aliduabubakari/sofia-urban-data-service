from __future__ import annotations

from typing import Any, Optional, Type

from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session
from geoalchemy2.types import Geography

from suds_core.config.settings import get_settings
from suds_core.geo.crs import BBox
from suds_core.geo.geometry import sql_envelope_4326, sql_geom_simplify_m, sql_point_4326
from suds_core.geo.serialization import feature, feature_collection


def _apply_limit(limit: Optional[int]) -> int:
    settings = get_settings()
    if limit is None:
        limit = settings.default_page_size
    return min(int(limit), int(settings.max_page_size))


def get_features_bbox(
    session: Session,
    *,
    model: Type[Any],
    bbox: BBox,
    limit: int | None = None,
    offset: int = 0,
    simplify_m: float | None = None,
    include_source_id: bool = True,
) -> dict[str, Any]:
    """
    Generic bbox query returning GeoJSON FeatureCollection for any model with:
      - id
      - props (JSONB)
      - geom (Geometry)
      - optional source_id
    """
    limit_n = _apply_limit(limit)
    envelope = sql_envelope_4326(bbox)
    geom_expr = sql_geom_simplify_m(model.geom, simplify_m)

    cols = [
        model.id.label("id"),
        model.props.label("props"),
        func.ST_AsGeoJSON(geom_expr).label("geom_geojson"),
    ]

    has_source_id = hasattr(model, "source_id")
    if include_source_id and has_source_id:
        cols.insert(1, model.source_id.label("source_id"))

    stmt = (
        select(*cols)
        .where(func.ST_Intersects(model.geom, envelope))
        .order_by(model.id)
        .limit(limit_n)
        .offset(int(offset))
    )

    rows = session.execute(stmt).all()

    feats = []
    for r in rows:
        props = dict(r.props or {})
        if include_source_id and hasattr(r, "source_id"):
            if r.source_id is not None:
                props["source_id"] = r.source_id
        feats.append(feature(r.geom_geojson, props, fid=r.id))

    return feature_collection(feats)


def get_features_radius(
    session: Session,
    *,
    model: Type[Any],
    lat: float,
    lon: float,
    radius_m: float = 300,
    limit: int | None = None,
    offset: int = 0,
    simplify_m: float | None = None,
    include_source_id: bool = True,
) -> dict[str, Any]:
    """
    Generic radius query (meters) using geography casting for accuracy.
    Returns GeoJSON FeatureCollection.
    """
    limit_n = _apply_limit(limit)
    pt = sql_point_4326(lon, lat)
    geom_expr = sql_geom_simplify_m(model.geom, simplify_m)

    cols = [
        model.id.label("id"),
        model.props.label("props"),
        func.ST_AsGeoJSON(geom_expr).label("geom_geojson"),
    ]

    has_source_id = hasattr(model, "source_id")
    if include_source_id and has_source_id:
        cols.insert(1, model.source_id.label("source_id"))

    # Properly cast to Geography type
    geog = Geography(geometry_type="GEOMETRY", srid=4326)

    stmt = (
        select(*cols)
        .where(func.ST_DWithin(cast(model.geom, geog), cast(pt, geog), float(radius_m)))
        .order_by(model.id)
        .limit(limit_n)
        .offset(int(offset))
    )

    rows = session.execute(stmt).all()

    feats = []
    for r in rows:
        props = dict(r.props or {})
        if include_source_id and hasattr(r, "source_id"):
            if r.source_id is not None:
                props["source_id"] = r.source_id
        feats.append(feature(r.geom_geojson, props, fid=r.id))

    return feature_collection(feats)