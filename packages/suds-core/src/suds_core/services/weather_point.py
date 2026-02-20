from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Literal, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from suds_core.config.settings import get_settings
from suds_core.connectors.openmeteo import OpenMeteoClient
from suds_core.db.models import WeatherDailyPoint, WeatherHourlyPoint


Source = Literal["archive", "forecast"]
Granularity = Literal["daily", "hourly"]


def _round_coord(x: float, precision: int = 4) -> float:
    return round(float(x), precision)


def _provider(source: Source) -> str:
    return "openmeteo_archive" if source == "archive" else "openmeteo_forecast"


def _forecast_cutoff() -> dt.datetime:
    settings = get_settings()
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=settings.weather_forecast_cache_ttl_hours)


def get_or_fetch_weather_daily_point(
    session: Session,
    *,
    lat: float,
    lon: float,
    start_date: dt.date,
    end_date: dt.date,
    source: Source = "archive",
    coord_precision: int = 4,
    timezone: str = "UTC",
) -> List[Dict[str, Any]]:
    lat_r = _round_coord(lat, coord_precision)
    lon_r = _round_coord(lon, coord_precision)
    provider = _provider(source)

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

    # Decide which dates need fetching (missing or stale forecast)
    stale_cutoff = _forecast_cutoff() if source == "forecast" else None
    missing: list[dt.date] = []
    cur = start_date
    while cur <= end_date:
        row = existing_by_date.get(cur)
        if row is None:
            missing.append(cur)
        elif stale_cutoff is not None and row.updated_at < stale_cutoff:
            missing.append(cur)
        cur += dt.timedelta(days=1)

    if missing:
        client = OpenMeteoClient()
        fetched = client.fetch_daily(
            source=source,
            lat=lat_r,
            lon=lon_r,
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
        )

        # Upsert into DB
        rows = []
        for row in fetched:
            d = dt.date.fromisoformat(row["date"])
            rows.append(
                {
                    "lat_round": lat_r,
                    "lon_round": lon_r,
                    "date": d,
                    "provider": provider,
                    "values": row,
                }
            )

        if rows:
            stmt = insert(WeatherDailyPoint).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["lat_round", "lon_round", "date", "provider"],
                set_={
                    "values": stmt.excluded["values"],  # <-- IMPORTANT FIX
                    "updated_at": func.now(),
                },
            )
            session.execute(stmt)

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


def get_or_fetch_weather_hourly_point(
    session: Session,
    *,
    lat: float,
    lon: float,
    start_date: dt.date,
    end_date: dt.date,
    source: Source = "archive",
    coord_precision: int = 4,
    timezone: str = "UTC",
    max_days: int = 14,
) -> List[Dict[str, Any]]:
    """
    Hourly time series cached in DB. Uses start/end dates (inclusive) and returns hourly timestamps.
    Safety: caps range length to max_days (default 14).
    """
    if (end_date - start_date).days + 1 > max_days:
        raise ValueError(f"Hourly range too large: {(end_date - start_date).days + 1} days > {max_days} days")

    lat_r = _round_coord(lat, coord_precision)
    lon_r = _round_coord(lon, coord_precision)
    provider = _provider(source)

    # Expected hours (UTC): days * 24
    expected_hours = ((end_date - start_date).days + 1) * 24
    start_dt = dt.datetime.combine(start_date, dt.time(0, 0), tzinfo=dt.timezone.utc)
    end_dt = dt.datetime.combine(end_date + dt.timedelta(days=1), dt.time(0, 0), tzinfo=dt.timezone.utc)

    existing = session.execute(
        select(WeatherHourlyPoint)
        .where(
            and_(
                WeatherHourlyPoint.lat_round == lat_r,
                WeatherHourlyPoint.lon_round == lon_r,
                WeatherHourlyPoint.provider == provider,
                WeatherHourlyPoint.timestamp >= start_dt,
                WeatherHourlyPoint.timestamp < end_dt,
            )
        )
        .order_by(WeatherHourlyPoint.timestamp)
    ).scalars().all()

    existing_count = len(existing)

    # For forecast, also require "freshness" (any stale -> refresh range)
    stale_cutoff = _forecast_cutoff() if source == "forecast" else None
    stale = False
    if stale_cutoff is not None and existing:
        newest_update = max(r.updated_at for r in existing)
        stale = newest_update < stale_cutoff

    needs_fetch = (existing_count < expected_hours) or stale

    if needs_fetch:
        client = OpenMeteoClient()
        fetched = client.fetch_hourly(
            source=source,
            lat=lat_r,
            lon=lon_r,
            start_date=start_date,
            end_date=end_date,
            timezone=timezone,
        )

        rows = []
        for row in fetched:
            # timestamp like "2024-08-01T00:00" (UTC) -> aware UTC datetime
            ts = dt.datetime.fromisoformat(row["timestamp"])
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=dt.timezone.utc)

            rows.append(
                {
                    "lat_round": lat_r,
                    "lon_round": lon_r,
                    "timestamp": ts,
                    "provider": provider,
                    "values": row,
                }
            )

        if rows:
            stmt = insert(WeatherHourlyPoint).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["lat_round", "lon_round", "timestamp", "provider"],
                set_={
                    "values": stmt.excluded["values"],  # <-- IMPORTANT FIX
                    "updated_at": func.now(),
                },
            )
            session.execute(stmt)

        existing = session.execute(
            select(WeatherHourlyPoint)
            .where(
                and_(
                    WeatherHourlyPoint.lat_round == lat_r,
                    WeatherHourlyPoint.lon_round == lon_r,
                    WeatherHourlyPoint.provider == provider,
                    WeatherHourlyPoint.timestamp >= start_dt,
                    WeatherHourlyPoint.timestamp < end_dt,
                )
            )
            .order_by(WeatherHourlyPoint.timestamp)
        ).scalars().all()

    out: List[Dict[str, Any]] = []
    for r in existing:
        rec = {
            "timestamp": r.timestamp.isoformat(),
            "lat_round": r.lat_round,
            "lon_round": r.lon_round,
            "provider": r.provider,
        }
        rec.update(r.values or {})
        out.append(rec)
    return out


def get_or_fetch_weather_timeseries(
    session: Session,
    *,
    lat: float,
    lon: float,
    start_date: dt.date,
    end_date: dt.date,
    granularity: Granularity,
    source: Source,
) -> Dict[str, Any]:
    if granularity == "daily":
        rows = get_or_fetch_weather_daily_point(
            session,
            lat=lat,
            lon=lon,
            start_date=start_date,
            end_date=end_date,
            source=source,
        )
        return {"granularity": "daily", "source": source, "lat": lat, "lon": lon, "start": start_date.isoformat(), "end": end_date.isoformat(), "rows": rows}

    rows = get_or_fetch_weather_hourly_point(
        session,
        lat=lat,
        lon=lon,
        start_date=start_date,
        end_date=end_date,
        source=source,
    )
    return {"granularity": "hourly", "source": source, "lat": lat, "lon": lon, "start": start_date.isoformat(), "end": end_date.isoformat(), "rows": rows}