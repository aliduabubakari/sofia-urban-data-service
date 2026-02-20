from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from suds_core.db.models import Streets
from suds_core.geo.crs import BBox
from suds_core.services.datasets import get_features_bbox, get_features_radius


def streets_bbox(
    session: Session,
    *,
    bbox: BBox,
    limit: int | None = None,
    offset: int = 0,
    simplify_m: float | None = None,
    include_boundary: bool = True,
    order_by: str = "id",
    order_point: tuple[float, float] | None = None,  # (lon, lat)
    include_distance: bool = False,
    clip: bool = False,
    include_clipped_length_m: bool = False,
) -> dict[str, Any]:
    return get_features_bbox(
        session,
        model=Streets,
        bbox=bbox,
        limit=limit,
        offset=offset,
        simplify_m=simplify_m,
        include_boundary=include_boundary,
        order_by=order_by,
        order_point=order_point,
        include_distance=include_distance,
        clip_to_region=clip,
        clip_dim=2 if clip else None,
        include_clipped_length_m=include_clipped_length_m,
    )


def streets_radius(
    session: Session,
    *,
    lat: float,
    lon: float,
    radius_m: float = 300,
    limit: int | None = None,
    offset: int = 0,
    simplify_m: float | None = None,
    include_boundary: bool = True,
    order_by: str = "distance",
    include_distance: bool = False,
    clip: bool = False,
    include_clipped_length_m: bool = False,
) -> dict[str, Any]:
    return get_features_radius(
        session,
        model=Streets,
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
        include_clipped_length_m=include_clipped_length_m,
    )