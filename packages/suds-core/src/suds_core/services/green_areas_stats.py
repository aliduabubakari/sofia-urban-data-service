from __future__ import annotations

from typing import Any, Optional

from geoalchemy2.types import Geography, Geometry
from sqlalchemy import Float, cast, func, select
from sqlalchemy.orm import Session

from suds_core.db.models import GreenAreas
from suds_core.geo.crs import BBox
from suds_core.geo.geometry import sql_envelope_4326, sql_point_4326
from suds_core.geo.serialization import feature


def green_areas_stats_bbox(
    session: Session,
    *,
    bbox: BBox,
    include_boundary: bool = True,
    accurate_coverage: bool = False,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    include_nearest_geometry: bool = False,
) -> dict[str, Any]:
    envelope = sql_envelope_4326(bbox)

    # Default reference point = bbox centroid (unless user provides one)
    if center_lat is None or center_lon is None:
        row = session.execute(
            select(
                func.ST_Y(func.ST_Centroid(envelope)).label("lat"),
                func.ST_X(func.ST_Centroid(envelope)).label("lon"),
            )
        ).one()
        center_lat, center_lon = float(row.lat), float(row.lon)

    pred = func.ST_Intersects(GreenAreas.geom, envelope) if include_boundary else func.ST_ContainsProperly(envelope, GreenAreas.geom)

    return _green_areas_stats_common(
        session,
        pred=pred,
        region_geom=envelope,
        ref_lat=center_lat,
        ref_lon=center_lon,
        include_nearest_geometry=include_nearest_geometry,
        accurate_coverage=accurate_coverage,
        query_kind="bbox",
        query_params={"bbox": bbox.as_tuple(), "include_boundary": include_boundary, "accurate_coverage": accurate_coverage},
    )


def green_areas_stats_radius(
    session: Session,
    *,
    lat: float,
    lon: float,
    radius_m: float = 300,
    include_boundary: bool = True,
    accurate_coverage: bool = False,
    include_nearest_geometry: bool = False,
) -> dict[str, Any]:
    pt = sql_point_4326(lon, lat)
    geog = Geography(geometry_type="GEOMETRY", srid=4326)

    circle_geom = cast(
        func.ST_Buffer(cast(pt, geog), float(radius_m)),
        Geometry(geometry_type="POLYGON", srid=4326),
    )

    if include_boundary:
        pred = func.ST_DWithin(cast(GreenAreas.geom, geog), cast(pt, geog), float(radius_m))
    else:
        pred = func.ST_ContainsProperly(circle_geom, GreenAreas.geom)

    return _green_areas_stats_common(
        session,
        pred=pred,
        region_geom=circle_geom,
        ref_lat=lat,
        ref_lon=lon,
        include_nearest_geometry=include_nearest_geometry,
        accurate_coverage=accurate_coverage,
        query_kind="radius",
        query_params={"lat": lat, "lon": lon, "radius_m": radius_m, "include_boundary": include_boundary, "accurate_coverage": accurate_coverage},
    )


def _green_areas_stats_common(
    session: Session,
    *,
    pred,
    region_geom,
    ref_lat: float,
    ref_lon: float,
    include_nearest_geometry: bool,
    accurate_coverage: bool,
    query_kind: str,
    query_params: dict[str, Any],
) -> dict[str, Any]:
    # Full green polygon areas (meters)
    geom_m = func.ST_Transform(GreenAreas.geom, 32635)
    area_m2 = func.ST_Area(geom_m)

    # Clipped green inside region (coverage). Use polygon-only intersections.
    clipped = func.ST_Intersection(GreenAreas.geom, region_geom)
    clipped_poly = func.ST_CollectionExtract(clipped, 3)
    clipped_area_m2 = func.ST_Area(func.ST_Transform(clipped_poly, 32635))

    # Base aggregates (fast)
    agg = session.execute(
        select(
            func.count().label("green_area_count"),
            func.coalesce(func.sum(area_m2), 0.0).label("sum_green_area_m2"),
            func.coalesce(func.sum(clipped_area_m2), 0.0).label("sum_green_area_clipped_m2"),
            func.avg(area_m2).label("mean_area_m2"),
            func.percentile_cont(0.5).within_group(area_m2).label("median_area_m2"),
            func.percentile_cont(0.9).within_group(area_m2).label("p90_area_m2"),
        ).where(pred)
    ).one()

    region_area_m2 = session.execute(
        select(func.ST_Area(func.ST_Transform(region_geom, 32635)))
    ).scalar_one() or 0.0

    # Accurate coverage (no overlap double-counting) – computed only if requested
    union_clipped_area_m2 = None
    if accurate_coverage:
        union_geom = func.ST_UnaryUnion(func.ST_Collect(clipped_poly))
        union_clipped_area_m2 = session.execute(
            select(func.coalesce(func.ST_Area(func.ST_Transform(union_geom, 32635)), 0.0)).where(pred)
        ).scalar_one()

    count = int(agg.green_area_count or 0)
    has_green = count > 0
    density_per_km2 = (count / (region_area_m2 / 1_000_000.0)) if region_area_m2 else 0.0

    clipped_area_used = float(union_clipped_area_m2) if (accurate_coverage and union_clipped_area_m2 is not None) else float(agg.sum_green_area_clipped_m2 or 0.0)
    coverage_ratio = (clipped_area_used / region_area_m2) if region_area_m2 else 0.0

    # Nearest green area (within the same selection pred)
    pt = sql_point_4326(ref_lon, ref_lat)
    geog = Geography(geometry_type="GEOMETRY", srid=4326)
    dist_m = func.ST_Distance(cast(GreenAreas.geom, geog), cast(pt, geog)).label("distance_m")

    cols = [GreenAreas.id, GreenAreas.props, dist_m]
    if include_nearest_geometry:
        cols.append(func.ST_AsGeoJSON(GreenAreas.geom).label("geom_geojson"))

    nb = session.execute(
        select(*cols)
        .where(pred)
        .order_by(GreenAreas.geom.op("<->")(pt))
        .limit(1)
    ).first()

    nearest = None
    if nb:
        props = dict(nb.props or {})
        nearest = {
            "id": int(nb.id),
            "distance_m": float(nb.distance_m) if nb.distance_m is not None else None,
            "properties": props,
        }
        if include_nearest_geometry and hasattr(nb, "geom_geojson"):
            nearest["feature"] = feature(nb.geom_geojson, props, fid=int(nb.id))

    return {
        "query": {"kind": query_kind, **query_params},
        "reference_point": {"lat": ref_lat, "lon": ref_lon},
        "region_area_m2": float(region_area_m2),
        "green_area_count": count,
        "has_green_area": bool(has_green),
        "green_area_density_per_km2": float(density_per_km2),
        "coverage": {
            "accurate_coverage": bool(accurate_coverage),
            "sum_green_area_clipped_m2_fast": float(agg.sum_green_area_clipped_m2 or 0.0),
            "sum_green_area_clipped_m2_accurate": float(union_clipped_area_m2) if union_clipped_area_m2 is not None else None,
            "sum_green_area_clipped_m2_used": float(clipped_area_used),
            "coverage_ratio": float(coverage_ratio),
        },
        "stats": {
            "sum_green_area_m2": float(agg.sum_green_area_m2 or 0.0),
            "mean_area_m2": float(agg.mean_area_m2) if agg.mean_area_m2 is not None else None,
            "median_area_m2": float(agg.median_area_m2) if agg.median_area_m2 is not None else None,
            "p90_area_m2": float(agg.p90_area_m2) if agg.p90_area_m2 is not None else None,
        },
        "nearest_green_area": nearest,
    }