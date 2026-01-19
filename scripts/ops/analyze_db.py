from __future__ import annotations

from sqlalchemy import text

from suds_core.db.engine import get_engine

TABLES = [
    "neighbourhoods",
    "green_areas",
    "trees",
    "pedestrian_network",
    "streets",
    "buildings",
    "pois",
]


def main() -> None:
    engine = get_engine()

    # VACUUM must run in autocommit mode
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        for t in TABLES:
            try:
                print(f"Running VACUUM (ANALYZE) on {t} ...")
                conn.execute(text(f"VACUUM (ANALYZE, VERBOSE) {t};"))
            except Exception as e:
                print(f"WARNING: VACUUM failed on {t}: {e}")
                print(f"Falling back to ANALYZE {t} ...")
                conn.execute(text(f"ANALYZE {t};"))

    print("OK: analyze complete (vacuum where possible).")


if __name__ == "__main__":
    main()