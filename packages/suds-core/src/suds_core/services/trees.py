from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from suds_core.db.models import Trees
from suds_core.geo.crs import BBox
from suds_core.services.datasets import get_features_bbox, get_features_radius


def get_trees_bbox(
    session: Session,
    *,
    bbox: BBox,
    limit: int | None = None,
    offset: int = 0,
    include_boundary: bool = True,
    order_by: str = "id",
    order_point: Optional[tuple[float, float]] = None,  # (lon, lat) when order_by="distance"
    include_distance: bool = False,
) -> dict[str, Any]:
    """
    Trees bbox query (GeoJSON).
    Uses the generic datasets service to ensure consistent behavior across datasets
    (boundary semantics, distance ordering, etc.).
    """
    return get_features_bbox(
        session,
        model=Trees,
        bbox=bbox,
        limit=limit,
        offset=offset,
        simplify_m=None,  # points do not need simplification
        include_boundary=include_boundary,
        order_by=order_by,
        order_point=order_point,
        include_distance=include_distance,
    )


def get_trees_radius(
    session: Session,
    *,
    lat: float,
    lon: float,
    radius_m: float = 300,
    limit: int | None = None,
    offset: int = 0,
    include_boundary: bool = True,
    order_by: str = "distance",
    include_distance: bool = False,
) -> dict[str, Any]:
    """
    Trees radius query (GeoJSON).
    """
    return get_features_radius(
        session,
        model=Trees,
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        limit=limit,
        offset=offset,
        simplify_m=None,  # points do not need simplification
        include_boundary=include_boundary,
        order_by=order_by,
        include_distance=include_distance,
    )