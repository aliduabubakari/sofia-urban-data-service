from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.orm import Session

from suds_core.db.engine import session_scope
from suds_core.db.ingest import SourceSpec, clean_and_reproject, gdf_to_mappings
from suds_core.db.models import Trees

try:
    import pyogrio  # type: ignore
except Exception:
    pyogrio = None


def iter_gpkg_chunks(path: Path, layer: Optional[str], chunk_size: int):
    """
    Yield GeoDataFrame chunks from a GPKG using pyogrio.
    """
    if pyogrio is None:
        raise RuntimeError("pyogrio is required for chunked GPKG ingestion. Install pyogrio and retry.")

    # How many features total?
    meta = pyogrio.read_info(str(path), layer=layer)
    total = meta["features"]

    for skip in range(0, total, chunk_size):
        gdf = pyogrio.read_dataframe(
            str(path),
            layer=layer,
            skip_features=skip,
            max_features=chunk_size,
        )
        # Ensure geopandas wrapper
        import geopandas as gpd
        gdf = gpd.GeoDataFrame(gdf, geometry="geometry")
        yield skip, total, gdf


def ingest_trees(
    session: Session,
    *,
    path: Path,
    layer: Optional[str],
    truncate: bool,
    chunk_size: int,
) -> int:
    spec = SourceSpec(
        path=path,
        layer=layer,
        source_id_col="id",          # trees dataset has 'id'
        expected_geom="POINT",
        force_2d=True,               # recommended: store geom as 2D; keep height in props
    )

    if truncate:
        session.execute(delete(Trees))

    inserted = 0

    # Prefer chunked ingestion
    if pyogrio is not None:
        for skip, total, gdf in iter_gpkg_chunks(path, layer, chunk_size):
            gdf = clean_and_reproject(gdf, target_epsg=4326, spec=spec)

            records = gdf_to_mappings(gdf, source_id_col=spec.source_id_col)

            session.bulk_insert_mappings(Trees, records)
            session.commit()  # commit per chunk to keep memory + locks under control

            inserted += len(records)
            print(f"Chunk {skip:,}-{min(skip+chunk_size, total):,} / {total:,} -> inserted {inserted:,}")

        return inserted

    # Fallback: load whole file (not recommended for huge files)
    import geopandas as gpd
    gdf = gpd.read_file(str(path), layer=layer)
    gdf = clean_and_reproject(gdf, target_epsg=4326, spec=spec)
    records = gdf_to_mappings(gdf, source_id_col=spec.source_id_col)
    session.bulk_insert_mappings(Trees, records)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Path to trees GPKG")
    parser.add_argument("--layer", default=None, help="Layer name (optional; if None uses default)")
    parser.add_argument("--truncate", action="store_true", help="Delete existing rows first")
    parser.add_argument("--chunk-size", type=int, default=50000, help="Chunk size for ingestion (default 50000)")
    args = parser.parse_args()

    with session_scope() as session:
        n = ingest_trees(
            session,
            path=Path(args.path),
            layer=args.layer,
            truncate=args.truncate,
            chunk_size=args.chunk_size,
        )
        print(f"OK: inserted {n:,} trees")


if __name__ == "__main__":
    main()