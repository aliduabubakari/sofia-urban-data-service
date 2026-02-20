from __future__ import annotations

from typing import Any, Optional

from geoalchemy2.types import Geography, Geometry
from sqlalchemy import Float, Integer, cast, func, select
from sqlalchemy.orm import Session

from suds_core.db.models import Buildings
from suds_core.geo.crs import BBox
from suds_core.geo.geometry import sql_envelope_4326, sql_point_4326
from suds_core.geo.serialization import feature


def _json_text(props_col, key: str):
    # props->>'key'
    return props_col.op("->>")(key)


def buildings_stats_bbox(
    session: Session,
    *,
    bbox: BBox,
    include_boundary: bool = True,
    center_lat: Optional[float] = None,
    center_lon: Optional[float] = None,
    include_nearest_geometry: bool = False,
    top_n_functype: int = 10,
) -> dict[str, Any]:
    envelope = sql_envelope_4326(bbox)

    if include_boundary:
        pred = func.ST_Intersects(Buildings.geom, envelope)
    else:
        pred = func.ST_ContainsProperly(envelope, Buildings.geom)

    return _buildings_stats_common(
        session,
        pred=pred,
        region_geom=envelope,
        center_lat=center_lat,
        center_lon=center_lon,
        include_nearest_geometry=include_nearest_geometry,
        top_n_functype=top_n_functype,
        query_kind="bbox",
        query_params={"bbox": bbox.as_tuple(), "include_boundary": include_boundary},
    )


def buildings_stats_radius(
    session: Session,
    *,
    lat: float,
    lon: float,
    radius_m: float = 300,
    include_boundary: bool = True,
    include_nearest_geometry: bool = False,
    top_n_functype: int = 10,
) -> dict[str, Any]:
    pt = sql_point_4326(lon, lat)
    geog = Geography(geometry_type="GEOMETRY", srid=4326)

    within = func.ST_DWithin(cast(Buildings.geom, geog), cast(pt, geog), float(radius_m))

    circle_geom = cast(
        func.ST_Buffer(cast(pt, geog), float(radius_m)),
        Geometry(geometry_type="POLYGON", srid=4326),
    )

    if include_boundary:
        pred = within
    else:
        # strict inside circle
        pred = func.ST_ContainsProperly(circle_geom, Buildings.geom)

    return _buildings_stats_common(
        session,
        pred=pred,
        region_geom=circle_geom,
        center_lat=lat,
        center_lon=lon,
        include_nearest_geometry=include_nearest_geometry,
        top_n_functype=top_n_functype,
        query_kind="radius",
        query_params={"lat": lat, "lon": lon, "radius_m": radius_m, "include_boundary": include_boundary},
    )


def _buildings_stats_common(
    session: Session,
    *,
    pred,
    region_geom,
    center_lat: Optional[float],
    center_lon: Optional[float],
    include_nearest_geometry: bool,
    top_n_functype: int,
    query_kind: str,
    query_params: dict[str, Any],
) -> dict[str, Any]:
    # Project to meters for reliable areas/perimeters
    geom_m = func.ST_Transform(Buildings.geom, 32635)
    area_m2 = func.ST_Area(geom_m)
    perim_m = func.ST_Perimeter(geom_m)

    # Compactness expression PER ROW (do NOT select it directly; only aggregate it)
    compactness_expr = (4.0 * func.pi() * area_m2 / func.nullif(perim_m * perim_m, 0.0))

    # clipped area inside region (coverage)
    clipped = func.ST_Intersection(Buildings.geom, region_geom)
    clipped_poly = func.ST_CollectionExtract(clipped, 3)  # polygons only
    clipped_area_m2 = func.ST_Area(func.ST_Transform(clipped_poly, 32635))

    # properties fields
    flrcount = cast(func.nullif(_json_text(Buildings.props, "flrcount"), ""), Float)
    year_built = cast(func.nullif(_json_text(Buildings.props, "nsi2011_year_built"), ""), Float)
    functype = _json_text(Buildings.props, "functype")

    # aggregates ONLY (no raw geom-derived columns)
    stmt = (
        select(
            func.count().label("building_count"),
            func.coalesce(func.sum(area_m2), 0.0).label("sum_building_area_m2"),
            func.coalesce(func.sum(clipped_area_m2), 0.0).label("sum_building_area_clipped_m2"),

            func.avg(area_m2).label("mean_area_m2"),
            func.percentile_cont(0.5).within_group(area_m2).label("median_area_m2"),
            func.percentile_cont(0.9).within_group(area_m2).label("p90_area_m2"),

            func.avg(perim_m).label("mean_perimeter_m"),
            func.percentile_cont(0.5).within_group(perim_m).label("median_perimeter_m"),

            func.avg(compactness_expr).label("mean_compactness"),
            func.percentile_cont(0.5).within_group(compactness_expr).label("median_compactness"),

            func.avg(flrcount).filter(flrcount.isnot(None)).label("mean_flrcount"),
            func.percentile_cont(0.5).within_group(flrcount).filter(flrcount.isnot(None)).label("median_flrcount"),
            func.percentile_cont(0.9).within_group(flrcount).filter(flrcount.isnot(None)).label("p90_flrcount"),

            func.coalesce(func.sum(area_m2 * flrcount).filter(flrcount.isnot(None)), 0.0).label("sum_gfa_est_m2"),

            func.count(year_built).label("year_built_known_count"),
            func.avg(year_built).filter(year_built.isnot(None)).label("mean_year_built"),
            func.percentile_cont(0.5).within_group(year_built).filter(year_built.isnot(None)).label("median_year_built"),
        )
        .where(pred)
    )

    row = session.execute(stmt).one()

    # region area (m2)
    region_area_m2 = session.execute(
        select(func.ST_Area(func.ST_Transform(region_geom, 32635)))
    ).scalar_one() or 0.0

    count = int(row.building_count or 0)
    density_per_km2 = (count / (region_area_m2 / 1_000_000.0)) if region_area_m2 else 0.0
    coverage = (float(row.sum_building_area_clipped_m2) / region_area_m2) if region_area_m2 else 0.0

    # functype distribution (top N)
    functype_rows = session.execute(
        select(functype.label("functype"), func.count().label("count"))
        .where(pred)
        .group_by(functype)
        .order_by(func.count().desc())
        .limit(int(top_n_functype))
    ).all()

    functype_counts = [{"functype": ft, "count": int(c)} for ft, c in functype_rows if ft is not None]

    # nearest building (optional; requires center point)
    nearest = None
    if center_lat is not None and center_lon is not None:
        pt = sql_point_4326(center_lon, center_lat)
        geog = Geography(geometry_type="GEOMETRY", srid=4326)
        dist_m = func.ST_Distance(cast(Buildings.geom, geog), cast(pt, geog)).label("distance_m")

        cols = [Buildings.id, Buildings.props, dist_m]
        if include_nearest_geometry:
            cols.append(func.ST_AsGeoJSON(Buildings.geom).label("geom_geojson"))

        nb = session.execute(
            select(*cols)
            .where(pred)
            .order_by(Buildings.geom.op("<->")(pt))
            .limit(1)
        ).first()

        if nb:
            nearest_props = dict(nb.props or {})
            nearest = {
                "id": int(nb.id),
                "distance_m": float(nb.distance_m) if nb.distance_m is not None else None,
                "properties": nearest_props,
            }
            if include_nearest_geometry and hasattr(nb, "geom_geojson"):
                nearest["feature"] = feature(nb.geom_geojson, nearest_props, fid=int(nb.id))

    return {
        "query": {"kind": query_kind, **query_params},
        "region_area_m2": float(region_area_m2),
        "building_count": count,
        "building_density_per_km2": float(density_per_km2),
        "coverage_ratio": float(coverage),
        "stats": {
            "sum_building_area_m2": float(row.sum_building_area_m2 or 0.0),
            "sum_building_area_clipped_m2": float(row.sum_building_area_clipped_m2 or 0.0),
            "mean_area_m2": float(row.mean_area_m2) if row.mean_area_m2 is not None else None,
            "median_area_m2": float(row.median_area_m2) if row.median_area_m2 is not None else None,
            "p90_area_m2": float(row.p90_area_m2) if row.p90_area_m2 is not None else None,
            "mean_perimeter_m": float(row.mean_perimeter_m) if row.mean_perimeter_m is not None else None,
            "median_perimeter_m": float(row.median_perimeter_m) if row.median_perimeter_m is not None else None,
            "mean_compactness": float(row.mean_compactness) if row.mean_compactness is not None else None,
            "median_compactness": float(row.median_compactness) if row.median_compactness is not None else None,
            "mean_flrcount": float(row.mean_flrcount) if row.mean_flrcount is not None else None,
            "median_flrcount": float(row.median_flrcount) if row.median_flrcount is not None else None,
            "p90_flrcount": float(row.p90_flrcount) if row.p90_flrcount is not None else None,
            "sum_gfa_est_m2": float(row.sum_gfa_est_m2 or 0.0),
            "year_built_known_count": int(row.year_built_known_count or 0),
            "mean_year_built": float(row.mean_year_built) if row.mean_year_built is not None else None,
            "median_year_built": float(row.median_year_built) if row.median_year_built is not None else None,
            "functype_top": functype_counts,
        },
        "nearest_building": nearest,
    }