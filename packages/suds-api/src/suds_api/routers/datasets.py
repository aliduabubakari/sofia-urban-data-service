from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.db.models import (
    Buildings,
    GreenAreas,
    Neighbourhoods,
    POIs,
    PedestrianNetwork,
    Streets,
    Trees,
)
from suds_core.geo.crs import parse_bbox
from suds_core.services.datasets import get_features_bbox, get_features_radius

router = APIRouter()

DATASET_MODELS: dict[str, Any] = {
    "buildings": Buildings,
    "green_areas": GreenAreas,
    "neighbourhoods": Neighbourhoods,
    "streets": Streets,
    "pedestrian_network": PedestrianNetwork,
    "trees": Trees,
    "pois": POIs,
}

# Per-dataset caps to prevent huge GeoJSON responses
DATASET_MAX_LIMIT = {
    "trees": 20000,
    "buildings": 20000,
    "streets": 20000,
    "green_areas": 20000,
    # keep others default
}

# Optional: require bbox for heavy polygon/point layers (recommended)
BBOX_REQUIRED = {"trees", "buildings"}


@router.get("")
def list_datasets(_: None = Depends(require_api_key)) -> dict[str, Any]:
    return {"datasets": sorted(DATASET_MODELS.keys())}


@router.get("/{dataset_name}")
def get_dataset_features(
    dataset_name: str,
    bbox: Optional[str] = Query(default=None, description="minx,miny,maxx,maxy in EPSG:4326 (lon/lat)"),
    lat: Optional[float] = Query(default=None),
    lon: Optional[float] = Query(default=None),
    radius_m: float = Query(default=300, gt=0),
    limit: int = Query(default=2000, gt=0),
    offset: int = Query(default=0, ge=0),
    simplify_m: Optional[float] = Query(default=None, description="Simplify tolerance in meters (lines/polygons)"),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    model = DATASET_MODELS.get(dataset_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_name}")

    # Clamp limit per dataset
    limit = min(limit, DATASET_MAX_LIMIT.get(dataset_name, limit))

    # Enforce bbox requirement for heavy datasets
    if dataset_name in BBOX_REQUIRED and bbox is None:
        raise HTTPException(
            status_code=400,
            detail=f"{dataset_name} requires bbox=... (radius queries disabled)"
        )

    if bbox:
        bb = parse_bbox(bbox)
        return get_features_bbox(
            session,
            model=model,
            bbox=bb,
            limit=limit,
            offset=offset,
            simplify_m=simplify_m,
        )

    if lat is not None and lon is not None:
        return get_features_radius(
            session,
            model=model,
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            limit=limit,
            offset=offset,
            simplify_m=simplify_m,
        )

    raise HTTPException(
        status_code=400,
        detail="Provide either bbox=minx,miny,maxx,maxy OR lat+lon (+ optional radius_m).",
    )


@router.get("/{dataset_name}/metadata")
def dataset_metadata(
    dataset_name: str,
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    model = DATASET_MODELS.get(dataset_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_name}")

    table = model.__tablename__

    # Count
    count = session.execute(text(f"SELECT COUNT(*) FROM {table};")).scalar_one()

    # SRID, geometry type, extent
    srid = session.execute(
        text(f"SELECT ST_SRID(geom) FROM {table} WHERE geom IS NOT NULL LIMIT 1;")
    ).scalar_one()

    extent = session.execute(text(f"SELECT ST_Extent(geom) FROM {table};")).scalar_one()

    geom_types = session.execute(
        text(f"SELECT ST_GeometryType(geom) AS gtype, COUNT(*) FROM {table} GROUP BY 1 ORDER BY 2 DESC;")
    ).all()

    return {
        "dataset": dataset_name,
        "table": table,
        "count": int(count),
        "srid": int(srid),
        "extent": extent,  # BOX(minx miny,maxx maxy)
        "geometry_types": [{"type": gt, "count": int(n)} for gt, n in geom_types],
    }