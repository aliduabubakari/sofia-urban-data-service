from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from suds_core.config.settings import get_settings
from suds_core.connectors.openmeteo import OpenMeteoClient
from suds_core.db.models import WeatherDailyPoint


def _round_coord(x: float, precision: int = 4) -> float:
    # ~11m precision at equator; fine for weather caching
    return round(float(x), precision)


def get_or_fetch_weather_daily_point(
    session: Session,
    *,
    lat: float,
    lon: float,
    start_date: dt.date,
    end_date: dt.date,
    provider: str = "openmeteo",
    coord_precision: int = 4,
) -> List[Dict[str, Any]]:
    settings = get_settings()

    lat_r = _round_coord(lat, coord_precision)
    lon_r = _round_coord(lon, coord_precision)

    existing = session.execute(
        select(WeatherDailyPoint)
        .where(
            and_(
                WeatherDailyPoint.lat_round == lat_r,
                WeatherDailyPoint.lon_round == lon_r,
                WeatherDailyPoint.provider == provider,
                WeatherDailyPoint.date >= start_date,
                WeatherDailyPoint.date <= end_date,
            )
        )
        .order_by(WeatherDailyPoint.date)
    ).scalars().all()

    existing_by_date = {r.date: r for r in existing}

    # Find missing dates
    missing = []
    cur = start_date
    while cur <= end_date:
        if cur not in existing_by_date:
            missing.append(cur)
        cur += dt.timedelta(days=1)

    if missing:
        if provider != "openmeteo":
            raise ValueError("Only provider='openmeteo' is implemented right now.")

        client = OpenMeteoClient()
        fetched = client.fetch_daily(lat=lat_r, lon=lon_r, start_date=start_date, end_date=end_date)

        for row in fetched:
            d = dt.date.fromisoformat(row["date"])
            if d in existing_by_date:
                continue
            session.add(
                WeatherDailyPoint(
                    lat_round=lat_r,
                    lon_round=lon_r,
                    date=d,
                    provider="openmeteo",
                    values=row,
                )
            )

        session.flush()

        # Reload
        existing = session.execute(
            select(WeatherDailyPoint)
            .where(
                and_(
                    WeatherDailyPoint.lat_round == lat_r,
                    WeatherDailyPoint.lon_round == lon_r,
                    WeatherDailyPoint.provider == provider,
                    WeatherDailyPoint.date >= start_date,
                    WeatherDailyPoint.date <= end_date,
                )
            )
            .order_by(WeatherDailyPoint.date)
        ).scalars().all()

    out: List[Dict[str, Any]] = []
    for r in existing:
        rec = {"date": r.date.isoformat(), "lat_round": r.lat_round, "lon_round": r.lon_round, "provider": r.provider}
        rec.update(r.values or {})
        out.append(rec)

    return out