from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.services.spatial_lookup import lookup_neighbourhood_for_point

router = APIRouter()


@router.get("/lookup/neighbourhood")
def lookup_neighbourhood(
    lat: float = Query(...),
    lon: float = Query(...),

    include_boundary: bool = Query(
        default=True,
        description="If true, includes points on polygon boundary (ST_Covers). If false, strict inside only (ST_ContainsProperly).",
    ),
    fallback_nearest: bool = Query(
        default=True,
        description="If no polygon contains the point, return the nearest neighbourhood polygon.",
    ),
    max_nearest_distance_m: float | None = Query(
        default=None,
        description="If set, nearest fallback is returned only when within this distance (meters).",
    ),
    include_geometry: bool = Query(default=False, description="If true, include neighbourhood polygon geometry (GeoJSON)."),

    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    try:
        return lookup_neighbourhood_for_point(
            session,
            lat=lat,
            lon=lon,
            include_boundary=include_boundary,
            fallback_nearest=fallback_nearest,
            max_nearest_distance_m=max_nearest_distance_m,
            include_geometry=include_geometry,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))