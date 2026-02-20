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
from suds_core.services.buildings_stats import buildings_stats_bbox, buildings_stats_radius
from suds_core.services.datasets import get_features_bbox, get_features_radius
from suds_core.services.green_areas_stats import green_areas_stats_bbox, green_areas_stats_radius
from suds_core.services.pedestrian_stats import pedestrian_stats_bbox, pedestrian_stats_radius
from suds_core.services.streets_stats import streets_stats_bbox, streets_stats_radius
from suds_core.services.trees_stats import trees_stats_bbox, trees_stats_radius

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

DATASET_MAX_LIMIT = {
    "trees": 20000,
    "buildings": 20000,
    "streets": 20000,
    "green_areas": 20000,
    "pedestrian_network": 20000,
    "pois": 20000,
    "neighbourhoods": 20000,
}

# Maximum radius in meters for stats endpoints (pedestrian/street safety)
MAX_RADIUS_M = 1000

# Trees-specific caps
MAX_TREES_RADIUS_GEOM_M = 500
MAX_TREES_RADIUS_STATS_M = 1000

# Datasets that support clipping (line datasets)
CLIP_SUPPORTED = {"pedestrian_network", "streets"}

# Only keep bbox requirement where you truly want to DISABLE radius queries.
# Trees now supports radius, so remove it.
BBOX_REQUIRED: set[str] = set()


@router.get("")
def list_datasets(_: None = Depends(require_api_key)) -> dict[str, Any]:
    return {"datasets": sorted(DATASET_MODELS.keys())}


@router.get("/{dataset_name}/stats")
def dataset_stats(
    dataset_name: str,
    bbox: Optional[str] = Query(default=None, description="minx,miny,maxx,maxy (EPSG:4326)"),
    lat: Optional[float] = Query(default=None),
    lon: Optional[float] = Query(default=None),
    radius_m: float = Query(default=300, gt=0),

    include_boundary: bool = Query(
        default=True,
        description="For buildings/green_areas: if false, only features strictly inside bbox/circle are included.",
    ),

    accurate_coverage: bool = Query(
        default=False,
        description=(
            "Green areas and trees: if true, computes coverage via union geometry "
            "(slower; avoids overlap double-counting)."
        ),
    ),

    center_lat: Optional[float] = Query(default=None, description="Reference point for nearest feature (bbox mode)"),
    center_lon: Optional[float] = Query(default=None, description="Reference point for nearest feature (bbox mode)"),
    include_nearest_geometry: bool = Query(default=False),

    top_n_functype: int = Query(default=10, ge=1, le=50),
    top_n: int = Query(default=10, ge=1, le=50),

    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    if dataset_name not in DATASET_MODELS:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_name}")

    if dataset_name == "buildings":
        if bbox:
            bb = parse_bbox(bbox)

            # convenience reuse of lat/lon if user provided
            if center_lat is None and lat is not None:
                center_lat = lat
            if center_lon is None and lon is not None:
                center_lon = lon

            return buildings_stats_bbox(
                session,
                bbox=bb,
                include_boundary=include_boundary,
                center_lat=center_lat,
                center_lon=center_lon,
                include_nearest_geometry=include_nearest_geometry,
                top_n_functype=top_n_functype,
            )

        if lat is not None and lon is not None:
            return buildings_stats_radius(
                session,
                lat=lat,
                lon=lon,
                radius_m=radius_m,
                include_boundary=include_boundary,
                include_nearest_geometry=include_nearest_geometry,
                top_n_functype=top_n_functype,
            )

        raise HTTPException(status_code=400, detail="Provide bbox=... OR lat+lon (+ optional radius_m).")

    if dataset_name == "green_areas":
        if bbox:
            bb = parse_bbox(bbox)

            if center_lat is None and lat is not None:
                center_lat = lat
            if center_lon is None and lon is not None:
                center_lon = lon

            return green_areas_stats_bbox(
                session,
                bbox=bb,
                include_boundary=include_boundary,
                accurate_coverage=accurate_coverage,
                center_lat=center_lat,
                center_lon=center_lon,
                include_nearest_geometry=include_nearest_geometry,
            )

        if lat is not None and lon is not None:
            return green_areas_stats_radius(
                session,
                lat=lat,
                lon=lon,
                radius_m=radius_m,
                include_boundary=include_boundary,
                accurate_coverage=accurate_coverage,
                include_nearest_geometry=include_nearest_geometry,
            )

        raise HTTPException(status_code=400, detail="Provide bbox=... OR lat+lon (+ optional radius_m).")

    if dataset_name == "trees":
        # trees stats returns both intersecting + strict, and supports accurate canopy coverage
        if bbox:
            bb = parse_bbox(bbox)

            if center_lat is None and lat is not None:
                center_lat = lat
            if center_lon is None and lon is not None:
                center_lon = lon

            try:
                return trees_stats_bbox(
                    session,
                    bbox=bb,
                    center_lat=center_lat,
                    center_lon=center_lon,
                    include_nearest_geometry=include_nearest_geometry,
                    top_n=top_n,
                    accurate_coverage=accurate_coverage,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        if lat is not None and lon is not None:
            if radius_m > MAX_TREES_RADIUS_STATS_M:
                raise HTTPException(
                    status_code=400,
                    detail=f"radius_m too large for trees stats (max {MAX_TREES_RADIUS_STATS_M})",
                )

            try:
                return trees_stats_radius(
                    session,
                    lat=lat,
                    lon=lon,
                    radius_m=radius_m,
                    include_nearest_geometry=include_nearest_geometry,
                    top_n=top_n,
                    accurate_coverage=accurate_coverage,
                )
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        raise HTTPException(status_code=400, detail="Provide bbox=... OR lat+lon (+ optional radius_m).")

    if dataset_name == "pedestrian_network":
        # pedestrian stats always return BOTH intersecting + strict in one response
        if bbox:
            bb = parse_bbox(bbox)

            if center_lat is None and lat is not None:
                center_lat = lat
            if center_lon is None and lon is not None:
                center_lon = lon

            return pedestrian_stats_bbox(
                session,
                bbox=bb,
                center_lat=center_lat,
                center_lon=center_lon,
                include_nearest_geometry=include_nearest_geometry,
                top_n=top_n,
            )

        if lat is not None and lon is not None:
            if radius_m > MAX_RADIUS_M:
                raise HTTPException(
                    status_code=400,
                    detail=f"radius_m too large for pedestrian_network stats (max {MAX_RADIUS_M})",
                )

            return pedestrian_stats_radius(
                session,
                lat=lat,
                lon=lon,
                radius_m=radius_m,
                include_nearest_geometry=include_nearest_geometry,
                top_n=top_n,
            )

        raise HTTPException(status_code=400, detail="Provide bbox=... OR lat+lon (+ optional radius_m).")

    if dataset_name == "streets":
        # streets stats always return BOTH intersecting + strict
        if bbox:
            bb = parse_bbox(bbox)

            if center_lat is None and lat is not None:
                center_lat = lat
            if center_lon is None and lon is not None:
                center_lon = lon

            return streets_stats_bbox(
                session,
                bbox=bb,
                center_lat=center_lat,
                center_lon=center_lon,
                include_nearest_geometry=include_nearest_geometry,
                top_n=top_n,
            )

        if lat is not None and lon is not None:
            if radius_m > MAX_RADIUS_M:
                raise HTTPException(status_code=400, detail=f"radius_m too large for streets stats (max {MAX_RADIUS_M})")

            return streets_stats_radius(
                session,
                lat=lat,
                lon=lon,
                radius_m=radius_m,
                include_nearest_geometry=include_nearest_geometry,
                top_n=top_n,
            )

        raise HTTPException(status_code=400, detail="Provide bbox=... OR lat+lon (+ optional radius_m).")

    raise HTTPException(status_code=501, detail=f"Stats not implemented for dataset '{dataset_name}' yet.")


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

    include_boundary: bool = Query(
        default=True,
        description=(
            "Controls boundary inclusion for BOTH bbox and radius queries. "
            "If true: includes features touching boundary. "
            "If false: only features strictly inside bbox/circle."
        ),
    ),

    order_by: Optional[str] = Query(
        default=None,
        description=(
            "Ordering: 'id' or 'distance'. "
            "If omitted: bbox->id, radius->distance. "
            "If order_by=distance, lat+lon are required."
        ),
    ),
    include_distance: bool = Query(
        default=False,
        description="If true, includes distance_m in each feature properties when order_by=distance.",
    ),

    clip: bool = Query(
        default=False,
        description="Pedestrian network/streets only: if true, clip segments to bbox/circle region.",
    ),
    include_clipped_metrics: bool = Query(
        default=False,
        description=(
            "Pedestrian network/streets only (requires clip=true): includes clipped_length_m and time estimates per feature."
        ),
    ),

    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
) -> dict[str, Any]:
    model = DATASET_MODELS.get(dataset_name)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_name}")

    limit = min(limit, DATASET_MAX_LIMIT.get(dataset_name, limit))

    if dataset_name in BBOX_REQUIRED and bbox is None:
        raise HTTPException(status_code=400, detail=f"{dataset_name} requires bbox=... (radius queries disabled)")

    # enforce clip support
    if (clip or include_clipped_metrics) and dataset_name not in CLIP_SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail="clip/include_clipped_metrics are only supported for pedestrian_network and streets",
        )

    if include_clipped_metrics and not clip:
        raise HTTPException(status_code=400, detail="include_clipped_metrics=true requires clip=true")

    if order_by is None:
        order_by = "id" if bbox else "distance"

    if order_by not in {"id", "distance"}:
        raise HTTPException(status_code=400, detail="order_by must be 'id' or 'distance'")

    if order_by == "distance":
        if lat is None or lon is None:
            raise HTTPException(status_code=400, detail="order_by=distance requires lat and lon")
        include_distance = True

    # bbox branch
    if bbox:
        bb = parse_bbox(bbox)

        fc = get_features_bbox(
            session,
            model=model,
            bbox=bb,
            limit=limit,
            offset=offset,
            simplify_m=simplify_m,
            include_boundary=include_boundary,
            order_by=order_by,
            order_point=(lon, lat) if order_by == "distance" else None,
            include_distance=include_distance,
            clip_to_region=clip,
            clip_dim=2 if clip else None,
            include_clipped_length_m=include_clipped_metrics,
        )

        if include_clipped_metrics:
            if dataset_name == "pedestrian_network":
                _inject_pedestrian_clipped_time_metrics(fc)
            elif dataset_name == "streets":
                _inject_streets_clipped_time_metrics(fc)

        return fc

    # radius branch
    if lat is not None and lon is not None:
        # Enforce radius caps (geometry endpoints)
        if dataset_name == "streets" and radius_m > MAX_RADIUS_M:
            raise HTTPException(status_code=400, detail=f"radius_m too large for streets (max {MAX_RADIUS_M})")

        if dataset_name == "trees" and radius_m > MAX_TREES_RADIUS_GEOM_M:
            raise HTTPException(
                status_code=400,
                detail=f"radius_m too large for trees geometry endpoint (max {MAX_TREES_RADIUS_GEOM_M})",
            )

        fc = get_features_radius(
            session,
            model=model,
            lat=lat,
            lon=lon,
            radius_m=radius_m,
            limit=limit,
            offset=offset,
            simplify_m=simplify_m,
            include_boundary=include_boundary,
            order_by=order_by,
            include_distance=include_distance,
            clip_to_region=clip,
            clip_dim=2 if clip else None,
            include_clipped_length_m=include_clipped_metrics,
        )

        if include_clipped_metrics:
            if dataset_name == "pedestrian_network":
                _inject_pedestrian_clipped_time_metrics(fc)
            elif dataset_name == "streets":
                _inject_streets_clipped_time_metrics(fc)

        return fc

    raise HTTPException(status_code=400, detail="Provide either bbox=... OR lat+lon (+ optional radius_m).")


def _inject_pedestrian_clipped_time_metrics(fc: dict[str, Any]) -> None:
    feats = fc.get("features", [])
    for f in feats:
        props = f.get("properties") or {}
        try:
            clipped_len = props.get("clipped_length_m")
            seg_len = props.get("segment_le")
            time_raw = props.get("minutes")
            if clipped_len is None or seg_len in (None, 0) or time_raw is None:
                continue

            clipped_len = float(clipped_len)
            seg_len = float(seg_len)
            time_raw = float(time_raw)
            if seg_len <= 0:
                continue

            time_scaled = time_raw * (clipped_len / seg_len)
            props["time_raw_clipped_est"] = time_scaled
            props["time_minutes_if_seconds_clipped_est"] = time_scaled / 60.0
            props["time_note"] = "time_raw uses props['minutes'] and may not be literal minutes."
        except Exception:
            continue


def _inject_streets_clipped_time_metrics(fc: dict[str, Any]) -> None:
    feats = fc.get("features", [])
    for f in feats:
        props = f.get("properties") or {}
        try:
            clipped_len = props.get("clipped_length_m")
            if clipped_len is None:
                continue
            clipped_len = float(clipped_len)

            speed = props.get("SpeedLimit")
            if speed is None:
                speed = props.get("max_speed")
            if speed is None:
                speed = props.get("speed_limit")
            if speed is None:
                continue

            speed = float(speed)
            if speed <= 0:
                continue

            travel_time_s = (clipped_len * 3.6) / speed
            props["travel_time_seconds_est"] = travel_time_s
            props["travel_time_minutes_est"] = travel_time_s / 60.0
            props["travel_time_note"] = "Estimated from speed limit; no junction delays/turn penalties."
        except Exception:
            continue


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

    count = session.execute(text(f"SELECT COUNT(*) FROM {table};")).scalar_one()
    srid = session.execute(text(f"SELECT ST_SRID(geom) FROM {table} WHERE geom IS NOT NULL LIMIT 1;")).scalar_one()
    extent = session.execute(text(f"SELECT ST_Extent(geom) FROM {table};")).scalar_one()
    geom_types = session.execute(
        text(f"SELECT ST_GeometryType(geom) AS gtype, COUNT(*) FROM {table} GROUP BY 1 ORDER BY 2 DESC;")
    ).all()

    return {
        "dataset": dataset_name,
        "table": table,
        "count": int(count),
        "srid": int(srid),
        "extent": extent,
        "geometry_types": [{"type": gt, "count": int(n)} for gt, n in geom_types],
    }