from __future__ import annotations

from typing import Any, Optional

from geoalchemy2.types import Geography, Geometry
from sqlalchemy import Float, and_, cast, func, select
from sqlalchemy.orm import Session

from suds_core.db.models import Streets
from suds_core.geo.crs import BBox
from suds_core.geo.geometry import sql_envelope_4326, sql_point_4326
from suds_core.geo.serialization import feature


def _json_text(props_col, key: str):
    return props_col.op("->>")(key)


def _num_key(props_col, key: str):
    return cast(func.nullif(_json_text(props_col, key), ""), Float)


def _num_any(props_col, keys: list[str]):
    exprs = [_num_key(props_col, k) for k in keys]
    return func.coalesce(*exprs)


def streets_stats_bbox(
    session: Session,
    *,
    bbox: BBox,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    include_nearest_geometry: bool = False,
    top_n: int = 10,
) -> dict[str, Any]:
    envelope = sql_envelope_4326(bbox)

    if center_lat is None or center_lon is None:
        row = session.execute(
            select(
                func.ST_Y(func.ST_Centroid(envelope)).label("lat"),
                func.ST_X(func.ST_Centroid(envelope)).label("lon"),
            )
        ).one()
        center_lat, center_lon = float(row.lat), float(row.lon)

    pred_intersecting = func.ST_Intersects(Streets.geom, envelope)
    pred_strict = func.ST_ContainsProperly(envelope, Streets.geom)

    return _streets_stats_common(
        session,
        region_geom=envelope,
        ref_lat=float(center_lat),
        ref_lon=float(center_lon),
        pred_intersecting=pred_intersecting,
        pred_strict=pred_strict,
        include_nearest_geometry=include_nearest_geometry,
        top_n=top_n,
        query_kind="bbox",
        query_params={"bbox": bbox.as_tuple()},
    )


def streets_stats_radius(
    session: Session,
    *,
    lat: float,
    lon: float,
    radius_m: float = 300,
    include_nearest_geometry: bool = False,
    top_n: int = 10,
) -> dict[str, Any]:
    pt = sql_point_4326(lon, lat)
    geog = Geography(geometry_type="GEOMETRY", srid=4326)

    circle_geom = cast(
        func.ST_Buffer(cast(pt, geog), float(radius_m)),
        Geometry(geometry_type="POLYGON", srid=4326),
    )

    pred_intersecting = func.ST_DWithin(cast(Streets.geom, geog), cast(pt, geog), float(radius_m))
    pred_strict = func.ST_ContainsProperly(circle_geom, Streets.geom)

    return _streets_stats_common(
        session,
        region_geom=circle_geom,
        ref_lat=float(lat),
        ref_lon=float(lon),
        pred_intersecting=pred_intersecting,
        pred_strict=pred_strict,
        include_nearest_geometry=include_nearest_geometry,
        top_n=top_n,
        query_kind="radius",
        query_params={"lat": lat, "lon": lon, "radius_m": radius_m},
    )


def _variant_stats(
    session: Session,
    *,
    region_geom,
    pred,
    ref_lat: float,
    ref_lon: float,
    include_nearest_geometry: bool,
    top_n: int,
) -> dict[str, Any]:
    clipped = func.ST_Intersection(Streets.geom, region_geom)
    clipped_lines = func.ST_CollectionExtract(clipped, 2)
    clipped_len_m = func.ST_Length(func.ST_Transform(clipped_lines, 32635))

    speed_kmh = _num_any(Streets.props, ["SpeedLimit", "max_speed", "speed_limit"])
    lanes = _num_any(Streets.props, ["lanes", "lane_count"])
    frc = _num_any(Streets.props, ["FRC", "frc"])
    street_name = func.coalesce(_json_text(Streets.props, "StreetName"), _json_text(Streets.props, "street_name"))

    # seconds = meters * 3.6 / kmh
    travel_time_s = (clipped_len_m * 3.6) / func.nullif(speed_kmh, 0.0)
    travel_time_min = travel_time_s / 60.0

    region_area_m2 = session.execute(select(func.ST_Area(func.ST_Transform(region_geom, 32635)))).scalar_one() or 0.0

    agg = session.execute(
        select(
            func.count().label("segment_count"),
            func.coalesce(func.sum(clipped_len_m), 0.0).label("total_length_m_in_region"),

            (
                func.sum(clipped_len_m * speed_kmh).filter(speed_kmh.isnot(None))
                / func.nullif(func.sum(clipped_len_m).filter(speed_kmh.isnot(None)), 0.0)
            ).label("mean_speed_kmh_weighted"),
            func.sum(clipped_len_m).filter(speed_kmh.isnot(None)).label("speed_length_used_m"),

            (
                func.sum(clipped_len_m * lanes).filter(lanes.isnot(None))
                / func.nullif(func.sum(clipped_len_m).filter(lanes.isnot(None)), 0.0)
            ).label("mean_lanes_weighted"),
            func.sum(clipped_len_m).filter(lanes.isnot(None)).label("lanes_length_used_m"),

            func.sum(travel_time_min).label("travel_time_minutes_sum"),
            func.count(travel_time_min).label("travel_time_segments_used"),

            (func.sum(clipped_len_m).filter(speed_kmh >= 50.0) / func.nullif(func.sum(clipped_len_m), 0.0)).label(
                "length_share_speed_ge_50"
            ),
            (func.sum(clipped_len_m).filter(speed_kmh >= 80.0) / func.nullif(func.sum(clipped_len_m), 0.0)).label(
                "length_share_speed_ge_80"
            ),
        )
        .where(and_(pred, func.ST_IsEmpty(clipped_lines) == False))  # noqa: E712
    ).one()

    count = int(agg.segment_count or 0)
    total_len = float(agg.total_length_m_in_region or 0.0)
    density_m_per_km2 = (total_len / (region_area_m2 / 1_000_000.0)) if region_area_m2 else 0.0

    by_frc = session.execute(
        select(
            frc.label("frc"),
            func.count().label("count"),
            func.coalesce(func.sum(clipped_len_m), 0.0).label("length_m"),
        )
        .where(and_(pred, func.ST_IsEmpty(clipped_lines) == False))  # noqa: E712
        .group_by(frc)
        .order_by(func.sum(clipped_len_m).desc())
        .limit(int(top_n))
    ).all()

    by_lanes = session.execute(
        select(
            lanes.label("lanes"),
            func.count().label("count"),
            func.coalesce(func.sum(clipped_len_m), 0.0).label("length_m"),
        )
        .where(and_(pred, func.ST_IsEmpty(clipped_lines) == False))  # noqa: E712
        .group_by(lanes)
        .order_by(func.sum(clipped_len_m).desc())
        .limit(int(top_n))
    ).all()

    by_street_name = session.execute(
        select(
            street_name.label("street_name"),
            func.count().label("count"),
            func.coalesce(func.sum(clipped_len_m), 0.0).label("length_m"),
        )
        .where(and_(pred, func.ST_IsEmpty(clipped_lines) == False))  # noqa: E712
        .group_by(street_name)
        .order_by(func.sum(clipped_len_m).desc())
        .limit(int(top_n))
    ).all()

    # nearest segment
    pt = sql_point_4326(ref_lon, ref_lat)
    geog = Geography(geometry_type="GEOMETRY", srid=4326)
    dist_m = func.ST_Distance(cast(Streets.geom, geog), cast(pt, geog)).label("distance_m")

    cols = [Streets.id, Streets.props, dist_m]
    if include_nearest_geometry:
        cols.append(func.ST_AsGeoJSON(Streets.geom).label("geom_geojson"))

    nb = session.execute(
        select(*cols)
        .where(pred)
        .order_by(Streets.geom.op("<->")(pt))
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
        "segment_count": count,
        "region_area_m2": float(region_area_m2),
        "total_length_m_in_region": total_len,
        "road_density_m_per_km2": float(density_m_per_km2),
        "speed": {
            "mean_speed_kmh_weighted": float(agg.mean_speed_kmh_weighted) if agg.mean_speed_kmh_weighted is not None else None,
            "speed_length_used_m": float(agg.speed_length_used_m) if agg.speed_length_used_m is not None else 0.0,
            "length_share_speed_ge_50": float(agg.length_share_speed_ge_50 or 0.0),
            "length_share_speed_ge_80": float(agg.length_share_speed_ge_80 or 0.0),
        },
        "lanes": {
            "mean_lanes_weighted": float(agg.mean_lanes_weighted) if agg.mean_lanes_weighted is not None else None,
            "lanes_length_used_m": float(agg.lanes_length_used_m) if agg.lanes_length_used_m is not None else 0.0,
        },
        "travel_time": {
            "travel_time_minutes_sum": float(agg.travel_time_minutes_sum) if agg.travel_time_minutes_sum is not None else None,
            "travel_time_segments_used": int(agg.travel_time_segments_used or 0),
            "note": "Estimated from speed limit and clipped length; no junction delays/turn penalties.",
        },
        "groupings": {
            "top_n": int(top_n),
            "by_frc": [{"frc": v, "count": int(c), "length_m": float(l)} for v, c, l in by_frc if v is not None],
            "by_lanes": [{"lanes": v, "count": int(c), "length_m": float(l)} for v, c, l in by_lanes if v is not None],
            "by_street_name": [{"street_name": v, "count": int(c), "length_m": float(l)} for v, c, l in by_street_name if v is not None],
        },
        "nearest_segment": nearest,
    }


def _streets_stats_common(
    session: Session,
    *,
    region_geom,
    ref_lat: float,
    ref_lon: float,
    pred_intersecting,
    pred_strict,
    include_nearest_geometry: bool,
    top_n: int,
    query_kind: str,
    query_params: dict[str, Any],
) -> dict[str, Any]:
    intersecting = _variant_stats(
        session,
        region_geom=region_geom,
        pred=pred_intersecting,
        ref_lat=ref_lat,
        ref_lon=ref_lon,
        include_nearest_geometry=include_nearest_geometry,
        top_n=top_n,
    )

    strict = _variant_stats(
        session,
        region_geom=region_geom,
        pred=pred_strict,
        ref_lat=ref_lat,
        ref_lon=ref_lon,
        include_nearest_geometry=include_nearest_geometry,
        top_n=top_n,
    )

    return {
        "query": {"kind": query_kind, **query_params},
        "reference_point": {"lat": ref_lat, "lon": ref_lon},
        "intersecting_stats": intersecting,
        "strict_stats": strict,
        "boundary_effects": {
            "segments_touching_boundary_count": max(0, int(intersecting["segment_count"]) - int(strict["segment_count"]))
        },
    }