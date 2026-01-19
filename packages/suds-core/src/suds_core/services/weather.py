# packages/suds-core/src/suds_core/services/weather.py
from __future__ import annotations

import datetime as dt
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from suds_core.connectors.openmeteo import OpenMeteoClient
from suds_core.db.models import Stations, WeatherDaily


def get_or_fetch_weather_daily_for_station(
    session: Session,
    *,
    station_name: str,
    start_date: dt.date,
    end_date: dt.date,
) -> list[dict[str, Any]]:
    """
    Returns list of rows: [{date, ...weather vars...}]
    Cached in WeatherDaily(values JSONB).
    """
    station = session.execute(
        select(Stations).where(Stations.station_name == station_name)
    ).scalar_one_or_none()
    if not station:
        raise ValueError(f"Unknown station: {station_name}")

    # Determine which dates are missing
    existing = session.execute(
        select(WeatherDaily)
        .where(
            and_(
                WeatherDaily.station_id == station.id,
                WeatherDaily.date >= start_date,
                WeatherDaily.date <= end_date,
            )
        )
        .order_by(WeatherDaily.date)
    ).scalars().all()

    existing_by_date = {row.date: row for row in existing}

    # Fetch missing if needed
    missing_dates = []
    cur = start_date
    while cur <= end_date:
        if cur not in existing_by_date:
            missing_dates.append(cur)
        cur += dt.timedelta(days=1)

    if missing_dates:
        client = OpenMeteoClient()
        # We can fetch once for the whole range
        # Need station lat/lon -> stored in geom. We'll read it via ST_X/Y
        # For now, station props may also contain lat/lon. Best practice is to query from geom in SQL.
        # We'll assume station.props has lat/lon as fallback.
        lat = float(station.props.get("lat", 0.0))
        lon = float(station.props.get("lon", 0.0))
        if lat == 0.0 and lon == 0.0:
            raise ValueError("Station lat/lon not found in station.props; store them at ingestion time.")

        fetched = client.fetch_daily(lat=lat, lon=lon, start_date=start_date, end_date=end_date)

        for row in fetched:
            d = dt.date.fromisoformat(row["date"])
            if d in existing_by_date:
                continue
            session.add(
                WeatherDaily(
                    station_id=station.id,
                    date=d,
                    values=row,
                )
            )
        session.flush()

        # reload rows
        existing = session.execute(
            select(WeatherDaily)
            .where(
                and_(
                    WeatherDaily.station_id == station.id,
                    WeatherDaily.date >= start_date,
                    WeatherDaily.date <= end_date,
                )
            )
            .order_by(WeatherDaily.date)
        ).scalars().all()

    # Return normalized dict list
    out: list[dict[str, Any]] = []
    for row in existing:
        rec = {"date": row.date.isoformat()}
        rec.update(row.values or {})
        out.append(rec)
    return out