from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.services.osm_point import get_or_compute_osm_metrics_point

router = APIRouter()

@router.get("/metrics")
def osm_metrics(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: int = Query(default=300, gt=0),
    refresh: bool = Query(default=False),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    metrics = get_or_compute_osm_metrics_point(
        session,
        lat=lat,
        lon=lon,
        buffer_m=radius_m,
        force_refresh=refresh,
    )
    return metrics