from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from suds_core.db.engine import session_scope
from suds_core.db.ingest import SourceSpec, clean_and_reproject, load_geodataframe, row_to_record
from suds_core.db.models import Neighbourhoods


def ingest_neighbourhoods(session: Session, *, path: Path, truncate: bool = False) -> int:
    spec = SourceSpec(
        path=path,
        layer=None,
        source_id_col="id",          # from your sample: ['id','regname','rajon','geometry']
        expected_geom="MULTIPOLYGON",
        force_2d=True,
    )

    gdf = load_geodataframe(spec)
    gdf = clean_and_reproject(gdf, target_epsg=4326, spec=spec)

    if truncate:
        session.execute(delete(Neighbourhoods))

    # Insert in chunks (safe for small dataset too)
    total = 0
    chunk_size = 5000
    for start in range(0, len(gdf), chunk_size):
        chunk = gdf.iloc[start : start + chunk_size]
        records = [row_to_record(row, source_id_col=spec.source_id_col) for _, row in chunk.iterrows()]
        session.bulk_insert_mappings(Neighbourhoods, records)
        total += len(records)

    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Path to neighbourhoods GeoJSON")
    parser.add_argument("--truncate", action="store_true", help="Delete existing rows before ingest")
    args = parser.parse_args()

    path = Path(args.path)
    with session_scope() as session:
        n = ingest_neighbourhoods(session, path=path, truncate=args.truncate)
        print(f"OK: inserted {n:,} neighbourhoods")


if __name__ == "__main__":
    main()