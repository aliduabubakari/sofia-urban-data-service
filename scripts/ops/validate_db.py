from __future__ import annotations

from sqlalchemy import text

from suds_core.db.engine import get_engine

GEOM_TABLES = [
    "neighbourhoods",
    "green_areas",
    "trees",
    "pedestrian_network",
    "streets",
    "buildings",
    "pois",
]

NON_GEOM_TABLES = [
    "weather_daily_point",
    "osm_metrics_point",
]


def main() -> None:
    engine = get_engine()

    with engine.connect() as conn:
        print("\n=== POSTGIS VERSION ===")
        try:
            v = conn.execute(text("SELECT PostGIS_Version();")).scalar_one()
            print(v)
        except Exception as e:
            print("Could not query PostGIS_Version:", e)

        print("\n=== GEOMETRY TABLE COUNTS / SRID / INVALID GEOMS / EXTENT ===")
        for t in GEOM_TABLES:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t};")).scalar_one()

            srid = conn.execute(
                text(f"SELECT ST_SRID(geom) FROM {t} WHERE geom IS NOT NULL LIMIT 1;")
            ).scalar_one()

            invalid = conn.execute(
                text(f"SELECT COUNT(*) FROM {t} WHERE geom IS NOT NULL AND NOT ST_IsValid(geom);")
            ).scalar_one()

            extent = conn.execute(
                text(f"SELECT ST_Extent(geom) FROM {t};")
            ).scalar_one()

            print(f"\n[{t}]")
            print(f"  rows:     {count:,}")
            print(f"  srid:     {srid}")
            print(f"  invalid:  {invalid:,}")
            print(f"  extent:   {extent}")

        print("\n=== NON-GEOMETRY TABLE COUNTS ===")
        for t in NON_GEOM_TABLES:
            count = conn.execute(text(f"SELECT COUNT(*) FROM {t};")).scalar_one()
            print(f"\n[{t}]")
            print(f"  rows:     {count:,}")

        print("\n=== GEOMETRY TYPE DISTRIBUTIONS ===")
        for t in GEOM_TABLES:
            print(f"\n[{t}]")
            rows = conn.execute(
                text(f"SELECT ST_GeometryType(geom) AS gtype, COUNT(*) FROM {t} GROUP BY 1 ORDER BY 2 DESC;")
            ).all()
            for gtype, n in rows:
                print(f"  {gtype:25s} {n:,}")

        print("\n=== SPATIAL INDEX CHECK (GiST on geom) ===")
        # show indexes that look like geometry gist indexes
        idx_rows = conn.execute(
            text(
                """
                SELECT tablename, indexname
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename = ANY(:tables)
                ORDER BY tablename, indexname;
                """
            ),
            {"tables": GEOM_TABLES},
        ).all()

        # Print only gist ones as a quick check
        for tablename in GEOM_TABLES:
            tab_idxs = [r for r in idx_rows if r[0] == tablename]
            gist_idxs = [r for r in tab_idxs if "gist" in r[1].lower()]
            print(f"{tablename:20s} indexes={len(tab_idxs):2d} gist={len(gist_idxs):2d}")
            for _, idxname in gist_idxs:
                print(f"  - {idxname}")

    print("\nOK: validation complete.")


if __name__ == "__main__":
    main()