from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from suds_core.db.engine import session_scope
from suds_core.db.ingest import SourceSpec, clean_and_reproject, gdf_to_mappings, load_geodataframe
from suds_core.db.models import Buildings

try:
    import pyogrio  # type: ignore
except Exception:
    pyogrio = None


def iter_chunks(path: Path, layer: Optional[str], chunk_size: int):
    if pyogrio is None:
        # fallback: single chunk by geopandas
        gdf = load_geodataframe(SourceSpec(path=path, layer=layer))
        yield 0, len(gdf), gdf
        return

    meta = pyogrio.read_info(str(path), layer=layer)
    total = meta["features"]
    for skip in range(0, total, chunk_size):
        gdf = pyogrio.read_dataframe(
            str(path),
            layer=layer,
            skip_features=skip,
            max_features=chunk_size,
        )
        import geopandas as gpd
        gdf = gpd.GeoDataFrame(gdf, geometry="geometry")
        yield skip, total, gdf


def ingest_buildings(
    session: Session,
    *,
    path: Path,
    layer: Optional[str],
    truncate: bool,
    chunk_size: int,
    source_id_col: str | None,
) -> int:
    spec = SourceSpec(
        path=path,
        layer=layer,
        source_id_col=source_id_col,      # you may want cadnum or cadbuild, etc.
        expected_geom="MULTIPOLYGON",
        force_2d=True,
    )

    if truncate:
        session.execute(delete(Buildings))
        session.commit()

    inserted = 0
    for skip, total, gdf in iter_chunks(path, layer, chunk_size):
        gdf = clean_and_reproject(gdf, target_epsg=4326, spec=spec)

        records = gdf_to_mappings(gdf, source_id_col=spec.source_id_col)
        session.bulk_insert_mappings(Buildings, records)
        session.commit()

        inserted += len(records)
        print(f"Chunk {skip:,}-{min(skip+chunk_size, total):,} / {total:,} -> inserted {inserted:,}")

    return inserted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Path to buildings GPKG")
    parser.add_argument("--layer", default=None, help="Optional layer for GPKG")
    parser.add_argument("--truncate", action="store_true", help="Delete existing rows first")
    parser.add_argument("--chunk-size", type=int, default=50000, help="Chunk size (default 50000)")
    parser.add_argument(
        "--source-id-col",
        default=None,
        help="Optional column name to store as source_id (e.g., cadnum)",
    )
    args = parser.parse_args()

    with session_scope() as session:
        n = ingest_buildings(
            session,
            path=Path(args.path),
            layer=args.layer,
            truncate=args.truncate,
            chunk_size=args.chunk_size,
            source_id_col=args.source_id_col,
        )
        print(f"OK: inserted {n:,} buildings")


if __name__ == "__main__":
    main()