from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.db.models import Buildings, GreenAreas, POIs, PedestrianNetwork, Streets, Trees
from suds_core.geo.bbox import bbox_from_point_radius
from suds_core.geo.crs import parse_bbox
from suds_core.services.datasets import get_features_bbox, get_features_radius
from suds_core.services.osm_point import get_or_compute_osm_metrics_point
from suds_core.services.weather_point import get_or_fetch_weather_daily_point

router = APIRouter()

DATASET_MODELS: dict[str, Any] = {
    "trees": Trees,
    "buildings": Buildings,
    "streets": Streets,
    "green_areas": GreenAreas,
    "pedestrian_network": PedestrianNetwork,
    "pois": POIs,
}

# Safeguards
MAX_RADIUS_M = 1000
DEFAULT_DATASETS = ["streets", "green_areas", "pois"]
DATASET_MAX_LIMIT = {
    "trees": 10000,
    "buildings": 10000,
    "streets": 20000,
    "green_areas": 20000,
    "pedestrian_network": 20000,
    "pois": 20000,
}

@router.get("/point")
def enrich_point(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: int = Query(default=300, gt=0, le=MAX_RADIUS_M),

    # Weather
    start: Optional[dt.date] = Query(default=None),
    end: Optional[dt.date] = Query(default=None),
    include_weather: bool = Query(default=True),

    # OSM
    include_osm: bool = Query(default=True),
    osm_refresh: bool = Query(default=False),

    # Geometries
    include_geometries: bool = Query(default=True),
    mode: str = Query(default="both", description="bbox | radius | both | none"),
    datasets: Optional[str] = Query(default=None, description="Comma-separated dataset names"),
    bbox: Optional[str] = Query(default=None, description="minx,miny,maxx,maxy; overrides auto bbox"),
    limit: int = Query(default=2000, gt=0),
    simplify_m: Optional[float] = Query(default=None),

    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
) -> dict[str, Any]:

    if mode not in {"bbox", "radius", "both", "none"}:
        raise HTTPException(status_code=400, detail="mode must be one of: bbox, radius, both, none")

    # dataset selection
    if datasets:
        requested = [d.strip() for d in datasets.split(",") if d.strip()]
    else:
        requested = DEFAULT_DATASETS

    unknown = [d for d in requested if d not in DATASET_MODELS]
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown datasets: {unknown}")

    # bbox computation
    if bbox:
        bb = parse_bbox(bbox)
        bbox_source = "user"
    else:
        bb = bbox_from_point_radius(lat, lon, radius_m)
        bbox_source = "computed_from_radius"

    result: dict[str, Any] = {
        "point": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "bbox": {"minx": bb.minx, "miny": bb.miny, "maxx": bb.maxx, "maxy": bb.maxy, "source": bbox_source},
        "limits": {"limit_requested": limit, "dataset_caps": DATASET_MAX_LIMIT, "max_radius_m": MAX_RADIUS_M},
    }

    # OSM metrics (cached in DB)
    if include_osm:
        result["osm"] = get_or_compute_osm_metrics_point(
            session,
            lat=lat,
            lon=lon,
            buffer_m=radius_m,
            force_refresh=osm_refresh,
        )

    # Weather (cached in DB)
    if include_weather:
        if start is None or end is None:
            raise HTTPException(status_code=400, detail="start and end are required when include_weather=true")
        rows = get_or_fetch_weather_daily_point(
            session,
            lat=lat,
            lon=lon,
            start_date=start,
            end_date=end,
            provider="openmeteo",
        )
        result["weather_daily"] = {"provider": "openmeteo", "rows": rows}

        # Convenience: expose elevation once (same for all rows)
        if rows:
            result["elevation_m"] = rows[0].get("elevation_m")

    # Geometries
    if include_geometries and mode != "none":
        geoms: dict[str, Any] = {}

        for d in requested:
            model = DATASET_MODELS[d]
            cap = DATASET_MAX_LIMIT.get(d, limit)
            effective_limit = min(limit, cap)

            if mode in {"bbox", "both"}:
                geoms.setdefault("bbox", {})[d] = get_features_bbox(
                    session,
                    model=model,
                    bbox=bb,
                    limit=effective_limit,
                    offset=0,
                    simplify_m=simplify_m,
                )

            if mode in {"radius", "both"}:
                geoms.setdefault("radius", {})[d] = get_features_radius(
                    session,
                    model=model,
                    lat=lat,
                    lon=lon,
                    radius_m=radius_m,
                    limit=effective_limit,
                    offset=0,
                    simplify_m=simplify_m,
                )

        result["geometries"] = geoms

    return result