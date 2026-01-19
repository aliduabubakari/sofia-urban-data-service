# packages/suds-core/src/suds_core/geo/geometry.py
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.sql.elements import ColumnElement

from suds_core.geo.crs import BBox


def sql_point_4326(lon: float, lat: float) -> ColumnElement:
    """
    SQL expression for a POINT in SRID 4326.
    """
    return func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)


def sql_envelope_4326(bbox: BBox) -> ColumnElement:
    """
    SQL expression for a bbox envelope in SRID 4326.
    """
    return func.ST_MakeEnvelope(bbox.minx, bbox.miny, bbox.maxx, bbox.maxy, 4326)


def sql_geom_simplify_m(geom_col: ColumnElement, simplify_m: float | None) -> ColumnElement:
    """
    Simplify geometry in meters by transforming to EPSG:3857 temporarily.
    """
    if simplify_m is None or simplify_m <= 0:
        return geom_col

    # 3857 is ok for simplification tolerances in meters (approx).
    return func.ST_Transform(
        func.ST_SimplifyPreserveTopology(func.ST_Transform(geom_col, 3857), simplify_m),
        4326,
    )
