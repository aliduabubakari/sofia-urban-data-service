from __future__ import annotations

from typing import Any, Optional

from geoalchemy2.types import Geography, Geometry
from sqlalchemy import Float, and_, cast, func, select
from sqlalchemy.orm import Session

from suds_core.db.models import Trees
from suds_core.geo.crs import BBox
from suds_core.geo.geometry import sql_envelope_4326, sql_point_4326
from suds_core.geo.serialization import feature


MAX_TREES_FOR_ACCURATE_CANOPY = 5000


def _json_text(props_col, key: str):
    return props_col.op("->>")(key)


def _num(props_col, key: str):
    return cast(func.nullif(_json_text(props_col, key), ""), Float)


def trees_stats_bbox(
    session: Session,
    *,
    bbox: BBox,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    include_nearest_geometry: bool = False,
    top_n: int = 10,
    accurate_coverage: bool = False,
) -> dict[str, Any]:
    envelope = sql_envelope_4326(bbox)

    # Default reference point = bbox centroid
    if center_lat is None or center_lon is None:
        row = session.execute(
            select(
                func.ST_Y(func.ST_Centroid(envelope)).label("lat"),
                func.ST_X(func.ST_Centroid(envelope)).label("lon"),
            )
        ).one()
        center_lat, center_lon = float(row.lat), float(row.lon)

    pred_intersecting = func.ST_Intersects(Trees.geom, envelope)
    pred_strict = func.ST_ContainsProperly(envelope, Trees.geom)

    return _trees_stats_common(
        session,
        region_geom=envelope,
        ref_lat=float(center_lat),
        ref_lon=float(center_lon),
        pred_intersecting=pred_intersecting,
        pred_strict=pred_strict,
        include_nearest_geometry=include_nearest_geometry,
        top_n=top_n,
        accurate_coverage=accurate_coverage,
        query_kind="bbox",
        query_params={"bbox": bbox.as_tuple()},
    )


def trees_stats_radius(
    session: Session,
    *,
    lat: float,
    lon: float,
    radius_m: float = 300,
    include_nearest_geometry: bool = False,
    top_n: int = 10,
    accurate_coverage: bool = False,
) -> dict[str, Any]:
    pt = sql_point_4326(lon, lat)
    geog = Geography(geometry_type="GEOMETRY", srid=4326)

    circle_geom = cast(
        func.ST_Buffer(cast(pt, geog), float(radius_m)),
        Geometry(geometry_type="POLYGON", srid=4326),
    )

    pred_intersecting = func.ST_DWithin(cast(Trees.geom, geog), cast(pt, geog), float(radius_m))
    # strict for points: distance < radius (excludes boundary)
    pred_strict = func.ST_Distance(cast(Trees.geom, geog), cast(pt, geog)) < float(radius_m)

    return _trees_stats_common(
        session,
        region_geom=circle_geom,
        ref_lat=float(lat),
        ref_lon=float(lon),
        pred_intersecting=pred_intersecting,
        pred_strict=pred_strict,
        include_nearest_geometry=include_nearest_geometry,
        top_n=top_n,
        accurate_coverage=accurate_coverage,
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
    geog = Geography(geometry_type="GEOMETRY", srid=4326)

    # numeric props
    height_m = _num(Trees.props, "height_calc")
    crown_diam_m = _num(Trees.props, "crown_diam")
    crown_area_m2 = _num(Trees.props, "crown_area")
    z_position_m = _num(Trees.props, "z_position")
    model_scale = _num(Trees.props, "model_scale")

    # crown area fallback if crown_area missing
    crown_area_est = func.pi() * func.pow(crown_diam_m / 2.0, 2.0)
    crown_area_used = func.coalesce(crown_area_m2, crown_area_est)

    # region area
    region_area_m2 = session.execute(
        select(func.ST_Area(func.ST_Transform(region_geom, 32635)))
    ).scalar_one() or 0.0

    agg = session.execute(
        select(
            func.count().label("tree_count"),

            # height stats
            func.avg(height_m).filter(height_m.isnot(None)).label("mean_height_m"),
            func.percentile_cont(0.5).within_group(height_m).filter(height_m.isnot(None)).label("median_height_m"),
            func.percentile_cont(0.9).within_group(height_m).filter(height_m.isnot(None)).label("p90_height_m"),
            func.min(height_m).filter(height_m.isnot(None)).label("min_height_m"),
            func.max(height_m).filter(height_m.isnot(None)).label("max_height_m"),
            func.count(height_m).label("height_known_count"),

            # canopy (fast)
            func.coalesce(func.sum(crown_area_used).filter(crown_area_used.isnot(None)), 0.0).label("sum_canopy_area_fast_m2"),
            func.count(crown_area_m2).label("crown_area_known_count"),
            func.count(crown_diam_m).label("crown_diam_known_count"),

            # z_position stats
            func.avg(z_position_m).filter(z_position_m.isnot(None)).label("mean_z_m"),
            func.min(z_position_m).filter(z_position_m.isnot(None)).label("min_z_m"),
            func.max(z_position_m).filter(z_position_m.isnot(None)).label("max_z_m"),
            func.percentile_cont(0.1).within_group(z_position_m).filter(z_position_m.isnot(None)).label("p10_z_m"),
            func.percentile_cont(0.9).within_group(z_position_m).filter(z_position_m.isnot(None)).label("p90_z_m"),
            func.count(z_position_m).label("z_known_count"),

            # model scale stats
            func.avg(model_scale).filter(model_scale.isnot(None)).label("mean_model_scale"),
            func.percentile_cont(0.5).within_group(model_scale).filter(model_scale.isnot(None)).label("median_model_scale"),
            func.percentile_cont(0.9).within_group(model_scale).filter(model_scale.isnot(None)).label("p90_model_scale"),
            func.count(model_scale).label("model_scale_known_count"),
        ).where(pred)
    ).one()

    count = int(agg.tree_count or 0)
    density_per_km2 = (count / (region_area_m2 / 1_000_000.0)) if region_area_m2 else 0.0

    canopy_fast = float(agg.sum_canopy_area_fast_m2 or 0.0)
    canopy_ratio_fast = (canopy_fast / region_area_m2) if region_area_m2 else 0.0

    # categorical top-N
    leaf_type = _json_text(Trees.props, "leaf_type_")
    model_name = _json_text(Trees.props, "model")

    by_leaf = session.execute(
        select(leaf_type.label("leaf_type"), func.count().label("count"))
        .where(pred)
        .group_by(leaf_type)
        .order_by(func.count().desc())
        .limit(int(top_n))
    ).all()

    by_model = session.execute(
        select(model_name.label("model"), func.count().label("count"))
        .where(pred)
        .group_by(model_name)
        .order_by(func.count().desc())
        .limit(int(top_n))
    ).all()

    # nearest tree
    pt = sql_point_4326(ref_lon, ref_lat)
    dist_m = func.ST_Distance(cast(Trees.geom, geog), cast(pt, geog)).label("distance_m")

    cols = [Trees.id, Trees.props, dist_m]
    if include_nearest_geometry:
        cols.append(func.ST_AsGeoJSON(Trees.geom).label("geom_geojson"))

    nb = session.execute(
        select(*cols)
        .where(pred)
        .order_by(Trees.geom.op("<->")(pt))
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
        "tree_count": count,
        "region_area_m2": float(region_area_m2),
        "tree_density_per_km2": float(density_per_km2),
        "height": {
            "height_known_count": int(agg.height_known_count or 0),
            "mean_height_m": float(agg.mean_height_m) if agg.mean_height_m is not None else None,
            "median_height_m": float(agg.median_height_m) if agg.median_height_m is not None else None,
            "p90_height_m": float(agg.p90_height_m) if agg.p90_height_m is not None else None,
            "min_height_m": float(agg.min_height_m) if agg.min_height_m is not None else None,
            "max_height_m": float(agg.max_height_m) if agg.max_height_m is not None else None,
        },
        "canopy": {
            "sum_canopy_area_fast_m2": canopy_fast,
            "canopy_cover_ratio_fast": float(canopy_ratio_fast),
            "crown_area_known_count": int(agg.crown_area_known_count or 0),
            "crown_diam_known_count": int(agg.crown_diam_known_count or 0),
        },
        "elevation": {
            "z_known_count": int(agg.z_known_count or 0),
            "mean_z_m": float(agg.mean_z_m) if agg.mean_z_m is not None else None,
            "min_z_m": float(agg.min_z_m) if agg.min_z_m is not None else None,
            "max_z_m": float(agg.max_z_m) if agg.max_z_m is not None else None,
            "p10_z_m": float(agg.p10_z_m) if agg.p10_z_m is not None else None,
            "p90_z_m": float(agg.p90_z_m) if agg.p90_z_m is not None else None,
        },
        "model": {
            "model_scale_known_count": int(agg.model_scale_known_count or 0),
            "mean_model_scale": float(agg.mean_model_scale) if agg.mean_model_scale is not None else None,
            "median_model_scale": float(agg.median_model_scale) if agg.median_model_scale is not None else None,
            "p90_model_scale": float(agg.p90_model_scale) if agg.p90_model_scale is not None else None,
            "top_leaf_types": [{"leaf_type": v, "count": int(c)} for v, c in by_leaf if v is not None],
            "top_models": [{"model": v, "count": int(c)} for v, c in by_model if v is not None],
            "top_n": int(top_n),
        },
        "nearest_tree": nearest,
    }


def _compute_canopy_union_area_m2(
    session: Session,
    *,
    region_geom,
    pred,
) -> float:
    """
    Accurate canopy cover: build canopy circles from crown radius, intersect with region,
    union them, and compute union area (m2). This avoids overlap double-counting.

    Safeguard: fails if too many trees.
    """
    geog = Geography(geometry_type="GEOMETRY", srid=4326)

    crown_diam_m = _num(Trees.props, "crown_diam")
    crown_area_m2 = _num(Trees.props, "crown_area")

    # radius from diam, or infer from crown_area (r = sqrt(area/pi))
    crown_r_m = func.coalesce(
        crown_diam_m / 2.0,
        func.sqrt(crown_area_m2 / func.nullif(func.pi(), 0.0)),
    )

    # Only trees with a usable crown radius
    usable_pred = and_(pred, crown_r_m.isnot(None), crown_r_m > 0.0)

    usable_count = session.execute(select(func.count()).select_from(Trees).where(usable_pred)).scalar_one()
    if int(usable_count) > MAX_TREES_FOR_ACCURATE_CANOPY:
        raise ValueError(
            f"accurate_coverage requested but too many trees with canopy data ({usable_count}) "
            f"> {MAX_TREES_FOR_ACCURATE_CANOPY}. Use accurate_coverage=false or reduce region/limit."
        )

    canopy_geom = cast(
        func.ST_Buffer(cast(Trees.geom, geog), crown_r_m),
        Geometry(geometry_type="POLYGON", srid=4326),
    )

    canopy_in_region = func.ST_Intersection(canopy_geom, region_geom)
    canopy_poly = func.ST_CollectionExtract(canopy_in_region, 3)

    union_geom = func.ST_UnaryUnion(func.ST_Collect(canopy_poly))

    area = session.execute(
        select(func.coalesce(func.ST_Area(func.ST_Transform(union_geom, 32635)), 0.0)).where(usable_pred)
    ).scalar_one()

    return float(area or 0.0)


def _trees_stats_common(
    session: Session,
    *,
    region_geom,
    ref_lat: float,
    ref_lon: float,
    pred_intersecting,
    pred_strict,
    include_nearest_geometry: bool,
    top_n: int,
    accurate_coverage: bool,
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

    # Accurate canopy coverage (computed once using intersecting predicate; reused for strict)
    canopy_union_area_m2 = None
    canopy_union_ratio = None
    reused_for_strict = None

    if accurate_coverage:
        canopy_union_area_m2 = _compute_canopy_union_area_m2(session, region_geom=region_geom, pred=pred_intersecting)
        region_area_m2 = intersecting["region_area_m2"]
        canopy_union_ratio = (canopy_union_area_m2 / region_area_m2) if region_area_m2 else 0.0
        reused_for_strict = True

        # attach to both variants for convenience
        intersecting["canopy"]["sum_canopy_area_accurate_m2"] = canopy_union_area_m2
        intersecting["canopy"]["canopy_cover_ratio_accurate"] = float(canopy_union_ratio)
        strict["canopy"]["sum_canopy_area_accurate_m2"] = canopy_union_area_m2
        strict["canopy"]["canopy_cover_ratio_accurate"] = float(canopy_union_ratio)
        strict["canopy"]["accurate_coverage_reused_from_intersecting"] = True

    return {
        "query": {"kind": query_kind, **query_params},
        "reference_point": {"lat": ref_lat, "lon": ref_lon},
        "accurate_coverage": bool(accurate_coverage),
        "intersecting_stats": intersecting,
        "strict_stats": strict,
        "boundary_effects": {
            "points_on_boundary_count_est": max(0, int(intersecting["tree_count"]) - int(strict["tree_count"]))
        },
        "coverage_notes": {
            "fast": "Fast canopy cover uses sum of crown areas (may overcount overlaps).",
            "accurate": "Accurate canopy cover unions canopy circles (no overlap double-counting).",
            "accurate_union_reused_for_strict": reused_for_strict,
        },
    }