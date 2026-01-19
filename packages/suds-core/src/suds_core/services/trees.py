# packages/suds-core/src/suds_core/services/trees.py
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from suds_core.config.settings import get_settings
from suds_core.db.models import Trees
from suds_core.geo.crs import BBox
from suds_core.geo.geometry import sql_envelope_4326, sql_point_4326
from suds_core.geo.serialization import feature, feature_collection


def get_trees_bbox(
    session: Session,
    *,
    bbox: BBox,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    settings = get_settings()
    limit = limit or settings.default_page_size
    limit = min(limit, settings.max_page_size)

    envelope = sql_envelope_4326(bbox)

    stmt = (
        select(
            Trees.id,
            Trees.props,
            func.ST_AsGeoJSON(Trees.geom).label("geom_geojson"),
        )
        .where(func.ST_Intersects(Trees.geom, envelope))
        .order_by(Trees.id)
        .limit(limit)
        .offset(offset)
    )

    rows = session.execute(stmt).all()
    feats = [feature(r.geom_geojson, r.props or {}, fid=r.id) for r in rows]
    return feature_collection(feats)


def get_trees_radius(
    session: Session,
    *,
    lat: float,
    lon: float,
    radius_m: float = 300,
    limit: int | None = None,
    offset: int = 0,
) -> dict[str, Any]:
    settings = get_settings()
    limit = limit or settings.default_page_size
    limit = min(limit, settings.max_page_size)

    pt = sql_point_4326(lon, lat)

    # Use geography for accurate meters in EPSG:4326
    stmt = (
        select(
            Trees.id,
            Trees.props,
            func.ST_AsGeoJSON(Trees.geom).label("geom_geojson"),
        )
        .where(func.ST_DWithin(Trees.geom.cast("geography"), pt.cast("geography"), radius_m))
        .order_by(Trees.id)
        .limit(limit)
        .offset(offset)
    )

    rows = session.execute(stmt).all()
    feats = [feature(r.geom_geojson, r.props or {}, fid=r.id) for r in rows]
    return feature_collection(feats)