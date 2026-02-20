from __future__ import annotations

from typing import Any, Optional

from geoalchemy2.types import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from suds_core.db.models import Neighbourhoods


def _extract_neighbourhood_fields(props: dict[str, Any]) -> dict[str, Any]:
    """
    Be defensive: neighbourhood datasets often have inconsistent naming.
    Return best-effort normalized fields while keeping full props.
    """
    # Common candidates; adjust if your props use different keys
    name = (
        props.get("regname")
        or props.get("name")
        or props.get("REGNAME")
        or props.get("neighbourhood")
        or props.get("neighborhood")
    )
    rajon = props.get("rajon") or props.get("RAJON") or props.get("district") or props.get("region")

    return {
        "name": name,
        "rajon": rajon,
    }


def lookup_neighbourhood_for_point(
    session: Session,
    *,
    lat: float,
    lon: float,
    include_boundary: bool = True,
    fallback_nearest: bool = True,
    max_nearest_distance_m: Optional[float] = None,
    include_geometry: bool = False,
) -> dict[str, Any]:
    """
    Returns the neighbourhood polygon containing the point, with optional fallback to nearest.

    Boundary semantics:
      - include_boundary=True  -> uses ST_Covers (point on boundary included)
      - include_boundary=False -> uses ST_ContainsProperly (strict inside)

    Fallback:
      - if no containing polygon found, returns nearest polygon with distance (meters)
        unless max_nearest_distance_m is set and exceeded.
    """
    pt = func.ST_SetSRID(func.ST_MakePoint(float(lon), float(lat)), 4326)

    # containment predicate
    if include_boundary:
        pred = func.ST_Covers(Neighbourhoods.geom, pt)
        method = "covers"
    else:
        pred = func.ST_ContainsProperly(Neighbourhoods.geom, pt)
        method = "contains_properly"

    # If multiple polygons match, choose smallest area (most specific)
    area_m2 = func.ST_Area(func.ST_Transform(Neighbourhoods.geom, 32635)).label("area_m2")

    cols = [
        Neighbourhoods.id.label("id"),
        Neighbourhoods.props.label("props"),
        area_m2,
    ]
    if include_geometry:
        cols.append(func.ST_AsGeoJSON(Neighbourhoods.geom).label("geom_geojson"))

    row = session.execute(
        select(*cols)
        .where(pred)
        .order_by(area_m2.asc())
        .limit(1)
    ).first()

    if row:
        props = dict(row.props or {})
        extracted = _extract_neighbourhood_fields(props)
        match: dict[str, Any] = {
            "id": int(row.id),
            "props": props,
            "area_m2": float(row.area_m2) if row.area_m2 is not None else None,
            **extracted,
        }
        if include_geometry and hasattr(row, "geom_geojson"):
            match["geometry"] = row.geom_geojson

        return {
            "query": {"lat": lat, "lon": lon},
            "matched": True,
            "match_method": method,
            "distance_m": 0.0,
            "neighbourhood": match,
        }

    # No polygon contains point -> optional nearest fallback
    if not fallback_nearest:
        return {
            "query": {"lat": lat, "lon": lon},
            "matched": False,
            "match_method": "none",
            "distance_m": None,
            "neighbourhood": None,
        }

    geog = Geography(geometry_type="GEOMETRY", srid=4326)
    dist_m = func.ST_Distance(cast(Neighbourhoods.geom, geog), cast(pt, geog)).label("distance_m")

    cols2 = [
        Neighbourhoods.id.label("id"),
        Neighbourhoods.props.label("props"),
        area_m2,
        dist_m,
    ]
    if include_geometry:
        cols2.append(func.ST_AsGeoJSON(Neighbourhoods.geom).label("geom_geojson"))

    nearest = session.execute(
        select(*cols2)
        .order_by(Neighbourhoods.geom.op("<->")(pt))
        .limit(1)
    ).first()

    if nearest is None:
        return {
            "query": {"lat": lat, "lon": lon},
            "matched": False,
            "match_method": "none",
            "distance_m": None,
            "neighbourhood": None,
        }

    distance_m = float(nearest.distance_m) if nearest.distance_m is not None else None
    if max_nearest_distance_m is not None and distance_m is not None and distance_m > float(max_nearest_distance_m):
        return {
            "query": {"lat": lat, "lon": lon},
            "matched": False,
            "match_method": "nearest_too_far",
            "distance_m": distance_m,
            "neighbourhood": None,
        }

    props = dict(nearest.props or {})
    extracted = _extract_neighbourhood_fields(props)

    match2: dict[str, Any] = {
        "id": int(nearest.id),
        "props": props,
        "area_m2": float(nearest.area_m2) if nearest.area_m2 is not None else None,
        **extracted,
    }
    if include_geometry and hasattr(nearest, "geom_geojson"):
        match2["geometry"] = nearest.geom_geojson

    return {
        "query": {"lat": lat, "lon": lon},
        "matched": True,
        "match_method": "nearest",
        "distance_m": distance_m,
        "neighbourhood": match2,
    }