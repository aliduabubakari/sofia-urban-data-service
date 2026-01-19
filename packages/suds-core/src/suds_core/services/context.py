# packages/suds-core/src/suds_core/services/context.py
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from suds_core.db.models import Buildings, GreenAreas, Streets, Trees
from suds_core.geo.geometry import sql_point_4326


def get_context_metrics_radius(
    session: Session,
    *,
    lat: float,
    lon: float,
    radius_m: float = 300,
) -> dict[str, Any]:
    """
    Aggregated context metrics around a point using PostGIS.

    NOTE:
    - Uses geography casting for meter-accurate buffers.
    - For area computations we transform to EPSG:32635.
    """
    pt = sql_point_4326(lon, lat)

    # Counts
    buildings_count = session.execute(
        select(func.count())
        .select_from(Buildings)
        .where(func.ST_DWithin(Buildings.geom.cast("geography"), pt.cast("geography"), radius_m))
    ).scalar_one()

    trees_count = session.execute(
        select(func.count())
        .select_from(Trees)
        .where(func.ST_DWithin(Trees.geom.cast("geography"), pt.cast("geography"), radius_m))
    ).scalar_one()

    # Green areas total area (m2) within radius (approx by clipping intersection)
    # We:
    # 1) create buffer in 4326
    # 2) transform to 32635 (meters)
    # 3) compute intersection area
    buffer_geom_4326 = func.ST_Buffer(pt.cast("geography"), radius_m).cast("geometry")
    buffer_32635 = func.ST_Transform(buffer_geom_4326, 32635)

    green_area_m2 = session.execute(
        select(
            func.coalesce(
                func.sum(
                    func.ST_Area(
                        func.ST_Intersection(func.ST_Transform(GreenAreas.geom, 32635), buffer_32635)
                    )
                ),
                0.0,
            )
        )
        .select_from(GreenAreas)
        .where(func.ST_Intersects(GreenAreas.geom, buffer_geom_4326))
    ).scalar_one()

    # Street total length (m) within radius
    street_length_m = session.execute(
        select(
            func.coalesce(
                func.sum(
                    func.ST_Length(
                        func.ST_Intersection(func.ST_Transform(Streets.geom, 32635), buffer_32635)
                    )
                ),
                0.0,
            )
        )
        .select_from(Streets)
        .where(func.ST_Intersects(Streets.geom, buffer_geom_4326))
    ).scalar_one()

    return {
        "point": {"lat": lat, "lon": lon},
        "radius_m": radius_m,
        "buildings_count": int(buildings_count or 0),
        "trees_count": int(trees_count or 0),
        "green_area_m2": float(green_area_m2 or 0.0),
        "street_length_m": float(street_length_m or 0.0),
    }