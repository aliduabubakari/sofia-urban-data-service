from __future__ import annotations

from typing import Any, Optional

from geoalchemy2.types import Geography, Geometry
from sqlalchemy import Float, and_, cast, func, select
from sqlalchemy.orm import Session

from suds_core.db.models import PedestrianNetwork
from suds_core.geo.crs import BBox
from suds_core.geo.geometry import sql_envelope_4326, sql_point_4326
from suds_core.geo.serialization import feature


def _json_text(props_col, key: str):
    return props_col.op("->>")(key)


def _num(props_col, key: str):
    return cast(func.nullif(_json_text(props_col, key), ""), Float)


def pedestrian_stats_bbox(
    session: Session,
    *,
    bbox: BBox,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    include_nearest_geometry: bool = False,
    top_n: int = 10,
) -> dict[str, Any]:
    envelope = sql_envelope_4326(bbox)

    # default reference point = bbox centroid
    if center_lat is None or center_lon is None:
        row = session.execute(
            select(
                func.ST_Y(func.ST_Centroid(envelope)).label("lat"),
                func.ST_X(func.ST_Centroid(envelope)).label("lon"),
            )
        ).one()
        center_lat, center_lon = float(row.lat), float(row.lon)

    pred_intersecting = func.ST_Intersects(PedestrianNetwork.geom, envelope)
    pred_strict = func.ST_ContainsProperly(envelope, PedestrianNetwork.geom)

    return _ped_stats_common(
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


def pedestrian_stats_radius(
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

    pred_intersecting = func.ST_DWithin(cast(PedestrianNetwork.geom, geog), cast(pt, geog), float(radius_m))
    pred_strict = func.ST_ContainsProperly(circle_geom, PedestrianNetwork.geom)

    return _ped_stats_common(
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
    # Clip each segment to the region polygon and keep only line components (dim=2)
    clipped = func.ST_Intersection(PedestrianNetwork.geom, region_geom)
    clipped_lines = func.ST_CollectionExtract(clipped, 2)

    # Length in meters (clipped)
    clipped_len_m = func.ST_Length(func.ST_Transform(clipped_lines, 32635))

    # Numeric props
    seg_len_m = _num(PedestrianNetwork.props, "segment_le")  # meters
    time_raw = _num(PedestrianNetwork.props, "minutes")      # unit unclear; treat as raw cost/time
    slope_perc = _num(PedestrianNetwork.props, "slope_perc")
    slope_abs = func.abs(slope_perc)

    # Time scaled by clipped fraction (avoid div-by-zero)
    time_scaled = time_raw * (clipped_len_m / func.nullif(seg_len_m, 0.0))

    region_area_m2 = session.execute(
        select(func.ST_Area(func.ST_Transform(region_geom, 32635)))
    ).scalar_one() or 0.0

    agg = session.execute(
        select(
            func.count().label("segment_count"),
            func.coalesce(func.sum(clipped_len_m), 0.0).label("total_length_m_in_region"),

            func.sum(time_scaled).label("time_raw_sum_in_region"),
            func.count(time_scaled).label("time_segments_used"),

            # length-weighted mean abs slope
            (
                func.sum(clipped_len_m * slope_abs).filter(slope_abs.isnot(None))
                / func.nullif(func.sum(clipped_len_m).filter(slope_abs.isnot(None)), 0.0)
            ).label("mean_abs_slope_weighted"),

            func.sum(clipped_len_m).filter(slope_abs.isnot(None)).label("slope_length_used_m"),

            # length share above thresholds (5/8/10%)
            (func.sum(clipped_len_m).filter(slope_abs > 5.0) / func.nullif(func.sum(clipped_len_m), 0.0)).label(
                "length_share_slope_gt_5"
            ),
            (func.sum(clipped_len_m).filter(slope_abs > 8.0) / func.nullif(func.sum(clipped_len_m), 0.0)).label(
                "length_share_slope_gt_8"
            ),
            (func.sum(clipped_len_m).filter(slope_abs > 10.0) / func.nullif(func.sum(clipped_len_m), 0.0)).label(
                "length_share_slope_gt_10"
            ),
        )
        .where(and_(pred, func.ST_IsEmpty(clipped_lines) == False))  # noqa: E712
    ).one()

    count = int(agg.segment_count or 0)
    length_m = float(agg.total_length_m_in_region or 0.0)
    density_m_per_km2 = (length_m / (region_area_m2 / 1_000_000.0)) if region_area_m2 else 0.0

    time_raw_sum = float(agg.time_raw_sum_in_region) if agg.time_raw_sum_in_region is not None else None
    time_minutes_if_seconds = (time_raw_sum / 60.0) if time_raw_sum is not None else None

    # Groupings (by clipped length)
    seg_type = _json_text(PedestrianNetwork.props, "type")
    str_class = _json_text(PedestrianNetwork.props, "str_class")

    by_type = session.execute(
        select(
            seg_type.label("type"),
            func.count().label("count"),
            func.coalesce(func.sum(clipped_len_m), 0.0).label("length_m"),
        )
        .where(and_(pred, func.ST_IsEmpty(clipped_lines) == False))  # noqa: E712
        .group_by(seg_type)
        .order_by(func.sum(clipped_len_m).desc())
        .limit(int(top_n))
    ).all()

    by_str_class = session.execute(
        select(
            str_class.label("str_class"),
            func.count().label("count"),
            func.coalesce(func.sum(clipped_len_m), 0.0).label("length_m"),
        )
        .where(and_(pred, func.ST_IsEmpty(clipped_lines) == False))  # noqa: E712
        .group_by(str_class)
        .order_by(func.sum(clipped_len_m).desc())
        .limit(int(top_n))
    ).all()

    # Nearest segment to reference point
    pt = sql_point_4326(ref_lon, ref_lat)
    geog = Geography(geometry_type="GEOMETRY", srid=4326)
    dist_m = func.ST_Distance(cast(PedestrianNetwork.geom, geog), cast(pt, geog)).label("distance_m")

    cols = [PedestrianNetwork.id, PedestrianNetwork.props, dist_m]
    if include_nearest_geometry:
        cols.append(func.ST_AsGeoJSON(PedestrianNetwork.geom).label("geom_geojson"))

    nb = session.execute(
        select(*cols)
        .where(pred)
        .order_by(PedestrianNetwork.geom.op("<->")(pt))
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
        "total_length_m_in_region": length_m,
        "network_density_m_per_km2": float(density_m_per_km2),
        "time": {
            "time_raw_sum_in_region": time_raw_sum,
            "time_minutes_if_seconds_sum_in_region": time_minutes_if_seconds,
            "time_segments_used": int(agg.time_segments_used or 0),
            "note": "time_raw uses props['minutes'] and is scaled by clipped_len/segment_le; unit may not be literal minutes.",
        },
        "slope": {
            "mean_abs_slope_weighted": float(agg.mean_abs_slope_weighted) if agg.mean_abs_slope_weighted is not None else None,
            "slope_length_used_m": float(agg.slope_length_used_m) if agg.slope_length_used_m is not None else 0.0,
            "length_share_slope_gt_5pct": float(agg.length_share_slope_gt_5 or 0.0),
            "length_share_slope_gt_8pct": float(agg.length_share_slope_gt_8 or 0.0),
            "length_share_slope_gt_10pct": float(agg.length_share_slope_gt_10 or 0.0),
        },
        "groupings": {
            "top_n": int(top_n),
            "by_type": [{"type": t, "count": int(c), "length_m": float(l)} for t, c, l in by_type if t is not None],
            "by_str_class": [{"str_class": s, "count": int(c), "length_m": float(l)} for s, c, l in by_str_class if s is not None],
        },
        "nearest_segment": nearest,
    }


def _ped_stats_common(
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
            "segments_touching_boundary_count": max(
                0,
                int(intersecting["segment_count"]) - int(strict["segment_count"]),
            )
        },
    }