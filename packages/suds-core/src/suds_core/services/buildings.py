# packages/suds-core/src/suds_core/services/buildings.py
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from suds_core.config.settings import get_settings
from suds_core.db.models import Buildings
from suds_core.geo.crs import BBox
from suds_core.geo.geometry import sql_envelope_4326, sql_geom_simplify_m
from suds_core.geo.serialization import feature, feature_collection


def get_buildings_bbox(
    session: Session,
    *,
    bbox: BBox,
    limit: int | None = None,
    offset: int = 0,
    simplify_m: float | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    limit = limit or settings.default_page_size
    limit = min(limit, settings.max_page_size)

    envelope = sql_envelope_4326(bbox)
    geom_expr = sql_geom_simplify_m(Buildings.geom, simplify_m)

    stmt: Select = (
        select(
            Buildings.id,
            Buildings.props,
            func.ST_AsGeoJSON(geom_expr).label("geom_geojson"),
        )
        .where(func.ST_Intersects(Buildings.geom, envelope))
        .order_by(Buildings.id)
        .limit(limit)
        .offset(offset)
    )

    rows = session.execute(stmt).all()

    feats = [
        feature(r.geom_geojson, r.props or {}, fid=r.id)
        for r in rows
    ]
    return feature_collection(feats)