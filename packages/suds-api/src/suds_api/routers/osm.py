from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.services.osm_point import get_or_compute_osm_metrics

router = APIRouter()

@router.get("/metrics")
def osm_metrics(
    # Either bbox OR lat/lon/radius
    bbox: Optional[str] = Query(default=None, description="minx,miny,maxx,maxy (EPSG:4326)"),
    lat: Optional[float] = Query(default=None),
    lon: Optional[float] = Query(default=None),
    radius_m: int = Query(default=300, gt=0),

    # Behavior
    detail: str = Query(default="basic", pattern="^(basic|full)$"),
    accurate_coverage: bool = Query(default=False, description="Full mode only: union polygons for accurate landuse cover."),
    top_n: int = Query(default=10, ge=1, le=50),
    refresh: bool = Query(default=False),

    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    try:
        if bbox:
            parts = [float(x.strip()) for x in bbox.split(",")]
            if len(parts) != 4:
                raise HTTPException(status_code=400, detail="bbox must be minx,miny,maxx,maxy")
            minx, miny, maxx, maxy = parts
            return get_or_compute_osm_metrics(
                session,
                bbox=(minx, miny, maxx, maxy),
                detail=detail,  # type: ignore[arg-type]
                accurate_coverage=accurate_coverage,
                top_n=top_n,
                refresh=refresh,
            )

        if lat is None or lon is None:
            raise HTTPException(status_code=400, detail="Provide either bbox=... OR lat+lon (+ radius_m).")

        return get_or_compute_osm_metrics(
            session,
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            detail=detail,  # type: ignore[arg-type]
            accurate_coverage=accurate_coverage,
            top_n=top_n,
            refresh=refresh,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))