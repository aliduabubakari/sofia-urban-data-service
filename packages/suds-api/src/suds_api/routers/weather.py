from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.services.weather_point import get_or_fetch_weather_daily_point

router = APIRouter()

@router.get("/daily")
def weather_daily(
    lat: float = Query(...),
    lon: float = Query(...),
    start: dt.date = Query(...),
    end: dt.date = Query(...),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    rows = get_or_fetch_weather_daily_point(session, lat=lat, lon=lon, start_date=start, end_date=end)
    return {"lat": lat, "lon": lon, "start": start.isoformat(), "end": end.isoformat(), "rows": rows}