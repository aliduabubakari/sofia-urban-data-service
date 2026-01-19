from __future__ import annotations

import datetime as dt

from sqlalchemy import delete

from suds_core.config.settings import get_settings
from suds_core.db.engine import session_scope
from suds_core.db.models import OsmMetricsPoint, WeatherDailyPoint


def main() -> None:
    settings = get_settings()
    now = dt.datetime.now(dt.timezone.utc)

    osm_cutoff = now - dt.timedelta(days=settings.osm_cache_ttl_days)
    weather_cutoff = now - dt.timedelta(days=settings.weather_cache_ttl_days)

    with session_scope() as session:
        osm_deleted = session.execute(
            delete(OsmMetricsPoint).where(OsmMetricsPoint.extracted_at < osm_cutoff)
        ).rowcount or 0

        # WeatherDailyPoint uses "date" not extracted_at for semantics
        weather_deleted = session.execute(
            delete(WeatherDailyPoint).where(WeatherDailyPoint.date < weather_cutoff.date())
        ).rowcount or 0

        print(
            {
                "osm_deleted": osm_deleted,
                "osm_cutoff": osm_cutoff.isoformat(),
                "weather_deleted": weather_deleted,
                "weather_cutoff_date": weather_cutoff.date().isoformat(),
            }
        )


if __name__ == "__main__":
    main()