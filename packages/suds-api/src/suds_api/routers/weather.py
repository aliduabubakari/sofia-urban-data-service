from __future__ import annotations

import datetime as dt
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.services.weather_point import get_or_fetch_weather_timeseries
from suds_core.services.weather_point_stats import weather_timeseries_stats

router = APIRouter()

Granularity = Literal["daily", "hourly"]
Source = Literal["archive", "forecast"]


@router.get("/daily")
def weather_daily(
    lat: float = Query(...),
    lon: float = Query(...),
    start: dt.date = Query(...),
    end: dt.date = Query(...),
    source: Source = Query(default="archive"),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    # Just a compatibility wrapper around /weather/timeseries
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    payload = get_or_fetch_weather_timeseries(
        session,
        lat=lat,
        lon=lon,
        start_date=start,
        end_date=end,
        granularity="daily",
        source=source,
    )
    return payload


@router.get("/timeseries")
def weather_timeseries(
    lat: float = Query(...),
    lon: float = Query(...),
    start: dt.date = Query(...),
    end: dt.date = Query(...),
    granularity: Granularity = Query(default="daily"),
    source: Source = Query(default="archive"),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    return get_or_fetch_weather_timeseries(
        session,
        lat=lat,
        lon=lon,
        start_date=start,
        end_date=end,
        granularity=granularity,
        source=source,
    )


@router.get("/stats")
def weather_stats(
    lat: float = Query(...),
    lon: float = Query(...),
    start: dt.date = Query(...),
    end: dt.date = Query(...),
    granularity: Granularity = Query(default="daily"),
    source: Source = Query(default="archive"),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    payload = get_or_fetch_weather_timeseries(
        session,
        lat=lat,
        lon=lon,
        start_date=start,
        end_date=end,
        granularity=granularity,
        source=source,
    )

    stats = weather_timeseries_stats(granularity=granularity, rows=payload["rows"])
    return {**payload, "stats": stats}