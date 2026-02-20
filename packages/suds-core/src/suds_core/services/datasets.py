from __future__ import annotations

from typing import Any, Optional, Type

from geoalchemy2.types import Geography, Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from suds_core.config.settings import get_settings
from suds_core.geo.crs import BBox
from suds_core.geo.geometry import sql_envelope_4326, sql_geom_simplify_m, sql_point_4326
from suds_core.geo.serialization import feature, feature_collection



def _apply_limit(limit: Optional[int]) -> int:
    settings = get_settings()
    if limit is None:
        limit = settings.default_page_size
    return min(int(limit), int(settings.max_page_size))


def get_features_bbox(
    session: Session,
    *,
    model: Type[Any],
    bbox: BBox,
    limit: int | None = None,
    offset: int = 0,
    simplify_m: float | None = None,
    include_source_id: bool = True,
    include_boundary: bool = True,
    order_by: str = "id",  # "id" | "distance"
    order_point: tuple[float, float] | None = None,  # (lon, lat) if order_by="distance"
    include_distance: bool = False,
    # --- clipping support ---
    clip_to_region: bool = False,
    clip_dim: int | None = None,  # for lines use 2, polygons use 3
    include_clipped_length_m: bool = False,
) -> dict[str, Any]:
    """
    Generic bbox query returning GeoJSON FeatureCollection.

    Boundary semantics:
      - include_boundary=True  -> ST_Intersects(geom, envelope)
      - include_boundary=False -> ST_ContainsProperly(envelope, geom) (strict inside)

    Ordering:
      - order_by="id" (stable)
      - order_by="distance" requires order_point=(lon,lat)

    Clipping:
      - clip_to_region=True returns geometry clipped to bbox polygon via ST_Intersection.
      - clip_dim controls which dimension to keep from intersections:
          2 -> lines, 3 -> polygons
      - include_clipped_length_m returns clipped_length_m (meters) in properties (requires clip_to_region for meaning).
    """
    limit_n = _apply_limit(limit)
    envelope = sql_envelope_4326(bbox)

    cols = [
        model.id.label("id"),
        model.props.label("props"),
    ]

    has_source_id = hasattr(model, "source_id")
    if include_source_id and has_source_id:
        cols.append(model.source_id.label("source_id"))

    # Geometry expression (optionally clipped)
    base_geom_expr = model.geom
    if clip_to_region:
        base_geom_expr = func.ST_Intersection(model.geom, envelope)
        if clip_dim is not None:
            base_geom_expr = func.ST_CollectionExtract(base_geom_expr, clip_dim)

    geom_expr = sql_geom_simplify_m(base_geom_expr, simplify_m)
    cols.append(func.ST_AsGeoJSON(geom_expr).label("geom_geojson"))

    # Optional clipped length (meters) - compute from UNSIMPLIFIED clipped geometry
    if include_clipped_length_m:
        cols.append(
            func.ST_Length(func.ST_Transform(base_geom_expr, 32635)).label("clipped_length_m")
        )

    # Spatial predicate
    if include_boundary:
        spatial_pred = func.ST_Intersects(model.geom, envelope)
    else:
        spatial_pred = func.ST_ContainsProperly(envelope, model.geom)

    geog = Geography(geometry_type="GEOMETRY", srid=4326)

    # Ordering
    if order_by not in {"id", "distance"}:
        raise ValueError("order_by must be 'id' or 'distance'")

    if order_by == "distance":
        if order_point is None:
            raise ValueError("order_point=(lon,lat) is required when order_by='distance'")
        pt = sql_point_4326(order_point[0], order_point[1])

        # exact distance in meters (geography)
        cols.append(func.ST_Distance(cast(model.geom, geog), cast(pt, geog)).label("distance_m"))
        # fast KNN ordering (uses GiST index on model.geom)
        order_expr = model.geom.op("<->")(pt)
    else:
        order_expr = model.id

    stmt = (
        select(*cols)
        .where(spatial_pred)
        .order_by(order_expr)
        .limit(limit_n)
        .offset(int(offset))
    )

    # If clipping, remove empty results (touch-only intersections become empty after CollectionExtract)
    if clip_to_region:
        stmt = stmt.where(func.ST_IsEmpty(base_geom_expr) == False)  # noqa: E712

    rows = session.execute(stmt).all()

    feats = []
    for r in rows:
        props = dict(r.props or {})

        if include_source_id and hasattr(r, "source_id") and getattr(r, "source_id") is not None:
            props["source_id"] = r.source_id

        # include distance if computed
        if hasattr(r, "distance_m") and (include_distance or order_by == "distance"):
            props["distance_m"] = float(r.distance_m) if r.distance_m is not None else None

        # include clipped length if computed
        if hasattr(r, "clipped_length_m"):
            props["clipped_length_m"] = float(r.clipped_length_m) if r.clipped_length_m is not None else None

        feats.append(feature(r.geom_geojson, props, fid=r.id))

    return feature_collection(feats)


def get_features_radius(
    session: Session,
    *,
    model: Type[Any],
    lat: float,
    lon: float,
    radius_m: float = 300,
    limit: int | None = None,
    offset: int = 0,
    simplify_m: float | None = None,
    include_source_id: bool = True,
    include_boundary: bool = True,
    order_by: str = "distance",  # "id" | "distance"
    include_distance: bool = False,
    # --- clipping support ---
    clip_to_region: bool = False,
    clip_dim: int | None = None,
    include_clipped_length_m: bool = False,
) -> dict[str, Any]:
    """
    Generic radius query around a point.

    Boundary semantics:
      - include_boundary=True  -> ST_DWithin(geom::geography, pt::geography, r) (touch/intersect circle)
      - include_boundary=False -> strict inside circle polygon (ST_ContainsProperly(circle, geom))

    Ordering:
      - order_by="distance" (default) orders nearest-first
      - order_by="id" orders stable by id

    Clipping:
      - clip_to_region=True clips returned geometry to the circle polygon.
      - For line clipping, pass clip_dim=2.
      - include_clipped_length_m adds clipped length (meters) into properties.
    """
    limit_n = _apply_limit(limit)
    pt = sql_point_4326(lon, lat)

    cols = [
        model.id.label("id"),
        model.props.label("props"),
    ]

    has_source_id = hasattr(model, "source_id")
    if include_source_id and has_source_id:
        cols.append(model.source_id.label("source_id"))

    geog = Geography(geometry_type="GEOMETRY", srid=4326)

    # Circle polygon (needed for strict containment and/or clipping)
    circle_geom = cast(
        func.ST_Buffer(cast(pt, geog), float(radius_m)),
        Geometry(geometry_type="POLYGON", srid=4326),
    )

    # Fast prefilter using ST_DWithin (index-friendly)
    within_or_touching = func.ST_DWithin(
        cast(model.geom, geog),
        cast(pt, geog),
        float(radius_m),
    )

    stmt = select(*cols).where(within_or_touching)

    if not include_boundary:
        stmt = stmt.where(func.ST_ContainsProperly(circle_geom, model.geom))

    # Geometry expression (optionally clipped to circle)
    base_geom_expr = model.geom
    if clip_to_region:
        base_geom_expr = func.ST_Intersection(model.geom, circle_geom)
        if clip_dim is not None:
            base_geom_expr = func.ST_CollectionExtract(base_geom_expr, clip_dim)

    geom_expr = sql_geom_simplify_m(base_geom_expr, simplify_m)
    stmt = stmt.add_columns(func.ST_AsGeoJSON(geom_expr).label("geom_geojson"))

    if include_clipped_length_m:
        stmt = stmt.add_columns(
            func.ST_Length(func.ST_Transform(base_geom_expr, 32635)).label("clipped_length_m")
        )

    # Ordering
    if order_by not in {"id", "distance"}:
        raise ValueError("order_by must be 'id' or 'distance'")

    if order_by == "distance":
        stmt = stmt.add_columns(func.ST_Distance(cast(model.geom, geog), cast(pt, geog)).label("distance_m"))
        stmt = stmt.order_by(model.geom.op("<->")(pt))
    else:
        stmt = stmt.order_by(model.id)

    stmt = stmt.limit(limit_n).offset(int(offset))

    # If clipping, remove empty results
    if clip_to_region:
        stmt = stmt.where(func.ST_IsEmpty(base_geom_expr) == False)  # noqa: E712

    rows = session.execute(stmt).all()

    feats = []
    for r in rows:
        props = dict(r.props or {})

        if include_source_id and hasattr(r, "source_id") and getattr(r, "source_id") is not None:
            props["source_id"] = r.source_id

        if hasattr(r, "distance_m") and (include_distance or order_by == "distance"):
            props["distance_m"] = float(r.distance_m) if r.distance_m is not None else None

        if hasattr(r, "clipped_length_m"):
            props["clipped_length_m"] = float(r.clipped_length_m) if r.clipped_length_m is not None else None

        feats.append(feature(r.geom_geojson, props, fid=r.id))

    return feature_collection(feats)