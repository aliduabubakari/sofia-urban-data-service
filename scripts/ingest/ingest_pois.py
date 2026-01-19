from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from suds_core.db.engine import session_scope
from suds_core.db.ingest import SourceSpec, clean_and_reproject, gdf_to_mappings, load_geodataframe
from suds_core.db.models import POIs


def ingest_pois(
    session: Session,
    *,
    path: Path,
    truncate: bool = False,
    source_id_col: str | None = "id",
) -> int:
    spec = SourceSpec(
        path=path,
        layer=None,
        source_id_col=source_id_col,
        expected_geom="POINT",  # will explode MultiPoint and keep Points
        force_2d=True,
    )

    gdf = load_geodataframe(spec)
    gdf = clean_and_reproject(gdf, target_epsg=4326, spec=spec)

    if truncate:
        session.execute(delete(POIs))

    records = gdf_to_mappings(gdf, source_id_col=spec.source_id_col)
    session.bulk_insert_mappings(POIs, records)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Path to POIs (shp/geojson)")
    parser.add_argument("--truncate", action="store_true", help="Delete existing rows first")
    parser.add_argument(
        "--source-id-col",
        default="id",
        help="Optional column to store as source_id (default: id).",
    )
    args = parser.parse_args()

    with session_scope() as session:
        n = ingest_pois(
            session,
            path=Path(args.path),
            truncate=args.truncate,
            source_id_col=args.source_id_col,
        )
        print(f"OK: inserted {n:,} POIs")


if __name__ == "__main__":
    main()