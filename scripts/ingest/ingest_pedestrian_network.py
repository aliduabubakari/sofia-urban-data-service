from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from suds_core.db.engine import session_scope
from suds_core.db.ingest import SourceSpec, clean_and_reproject, gdf_to_mappings, load_geodataframe
from suds_core.db.models import PedestrianNetwork


def ingest_pedestrian(session: Session, *, path: Path, layer: str, truncate: bool = False) -> int:
    spec = SourceSpec(
        path=path,
        layer=layer,
        source_id_col="id",
        expected_geom="MULTILINESTRING",
        force_2d=True,
    )

    gdf = load_geodataframe(spec)
    gdf = clean_and_reproject(gdf, target_epsg=4326, spec=spec)

    if truncate:
        session.execute(delete(PedestrianNetwork))

    records = gdf_to_mappings(gdf, source_id_col=spec.source_id_col)
    session.bulk_insert_mappings(PedestrianNetwork, records)
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Path to pedestrian network GPKG")
    parser.add_argument(
        "--layer",
        default="pedestrian_with_adj_pois",
        help="Layer name in GPKG (default: pedestrian_with_adj_pois)",
    )
    parser.add_argument("--truncate", action="store_true", help="Delete existing rows first")
    args = parser.parse_args()

    with session_scope() as session:
        n = ingest_pedestrian(
            session,
            path=Path(args.path),
            layer=args.layer,
            truncate=args.truncate,
        )
        print(f"OK: inserted {n:,} pedestrian segments from layer '{args.layer}'")


if __name__ == "__main__":
    main()