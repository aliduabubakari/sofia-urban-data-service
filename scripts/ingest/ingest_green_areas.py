from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from suds_core.db.engine import session_scope
from suds_core.db.ingest import SourceSpec, clean_and_reproject, gdf_to_mappings, load_geodataframe
from suds_core.db.models import GreenAreas


def ingest_green_areas(session: Session, *, path: Path, truncate: bool = False) -> int:
    spec = SourceSpec(
        path=path,
        layer=None,
        source_id_col="id",              # your green file has: id, source, area_m, geometry
        expected_geom="MULTIPOLYGON",
        force_2d=True,
    )

    gdf = load_geodataframe(spec)
    gdf = clean_and_reproject(gdf, target_epsg=4326, spec=spec)

    if truncate:
        session.execute(delete(GreenAreas))

    records = gdf_to_mappings(gdf, source_id_col=spec.source_id_col)
    session.bulk_insert_mappings(GreenAreas, records)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Path to green areas GeoJSON")
    parser.add_argument("--truncate", action="store_true", help="Delete existing rows first")
    args = parser.parse_args()

    with session_scope() as session:
        n = ingest_green_areas(session, path=Path(args.path), truncate=args.truncate)
        print(f"OK: inserted {n:,} green areas")


if __name__ == "__main__":
    main()