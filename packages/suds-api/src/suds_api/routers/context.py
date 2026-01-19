from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.services.context import get_context_metrics_radius

router = APIRouter()


@router.get("")
def context_radius(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = Query(default=300, gt=0),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    return get_context_metrics_radius(session, lat=lat, lon=lon, radius_m=radius_m)