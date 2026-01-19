from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.services.stations import (
    get_station,
    list_stations,
    list_stations_geojson,
    upsert_stations_from_gate,
)

router = APIRouter()

@router.get("")
def stations_list(session: Session = Depends(get_db_session), _: None = Depends(require_api_key)):
    return {"stations": list_stations(session)}

@router.get("/geojson")
def stations_geojson(session: Session = Depends(get_db_session), _: None = Depends(require_api_key)):
    return list_stations_geojson(session)

@router.get("/{station_name}")
def stations_get(station_name: str, session: Session = Depends(get_db_session), _: None = Depends(require_api_key)):
    st = get_station(session, station_name)
    if not st:
        raise HTTPException(status_code=404, detail="Station not found")
    return st

@router.post("/refresh")
def stations_refresh(session: Session = Depends(get_db_session), _: None = Depends(require_api_key)):
    return upsert_stations_from_gate(session)