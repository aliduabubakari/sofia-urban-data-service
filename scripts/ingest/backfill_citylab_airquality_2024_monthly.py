from suds_core.db.engine import session_scope
from suds_core.services.citylab_aggregates import backfill_citylab_monthly_means

def main():
    with session_scope() as session:
        res = backfill_citylab_monthly_means(
            session,
            year=2024,
            station_type="airquality",
            params=["PM2.5", "PM10", "NO2", "O3"],
        )
        print(res)

if __name__ == "__main__":
    main()