from __future__ import annotations

import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.db.models import CityLabStation
from suds_core.services.airquality import airquality_exposure_point

router = APIRouter()

@router.get("/stations")
def airquality_stations(
    station_type: str = Query(default="airquality"),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    rows = (
        session.query(CityLabStation)
        .filter(CityLabStation.station_type == station_type)
        .order_by(CityLabStation.name)
        .all()
    )

    return {
        "station_type": station_type,
        "count": len(rows),
        "stations": [
            {
                "external_id": r.external_id,
                "name": r.name,
                "station_type": r.station_type,
                "address": r.address,
                "operator": r.operator,
                "model": r.model,
                "serial_number": r.serial_number,
                "props": r.props,
            }
            for r in rows
        ],
    }

@router.get("/exposure/point")
def airquality_exposure(
    lat: float = Query(...),
    lon: float = Query(...),
    start: dt.date = Query(...),
    end: dt.date = Query(...),
    params: str = Query(default="PM2.5,PM10,NO2,O3"),
    method: str = Query(default="idw", pattern="^(nearest|idw)$"),
    k: int = Query(default=3, ge=1, le=5),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    if end < start:
        raise HTTPException(status_code=400, detail="end must be >= start")

    plist = [p.strip() for p in params.split(",") if p.strip()]
    try:
        return airquality_exposure_point(
            session,
            lat=lat,
            lon=lon,
            start=start,
            end=end,
            params=plist,
            method=method,  # type: ignore[arg-type]
            k=k,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))