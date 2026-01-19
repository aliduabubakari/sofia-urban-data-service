from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from suds_core.db.models import POIs
from suds_core.geo.crs import BBox
from suds_core.services.datasets import get_features_bbox, get_features_radius


def pois_bbox(
    session: Session,
    *,
    bbox: BBox,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    return get_features_bbox(
        session,
        model=POIs,
        bbox=bbox,
        limit=limit,
        offset=offset,
        simplify_m=None,  # points don't need simplification
    )


def pois_radius(
    session: Session,
    *,
    lat: float,
    lon: float,
    radius_m: float = 300,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    return get_features_radius(
        session,
        model=POIs,
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        limit=limit,
        offset=offset,
        simplify_m=None,
    )