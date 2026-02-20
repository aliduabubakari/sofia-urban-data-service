from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Literal, Tuple

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session

from suds_core.config.settings import get_settings
from suds_core.connectors.overpass import OverpassClient
from suds_core.db.models import OsmMetricsPoint, OsmMetricsBbox

Detail = Literal["basic", "full"]
RegionType = Literal["circle", "bbox"]

MAX_RADIUS_M = 2000
MAX_BBOX_AREA_KM2 = 12.6  # ~ area of a 2000m radius circle
MAX_POLYGONS_FOR_ACCURATE_COVERAGE = 2000


def _round_coord(x: float, precision: int = 5) -> float:
    return round(float(x), precision)


def _round_bbox(minx: float, miny: float, maxx: float, maxy: float, precision: int = 5) -> tuple[float, float, float, float]:
    return (_round_coord(minx, precision), _round_coord(miny, precision), _round_coord(maxx, precision), _round_coord(maxy, precision))


def _bbox_to_overpass(minx: float, miny: float, maxx: float, maxy: float) -> tuple[float, float, float, float]:
    # Overpass bbox order is: south,west,north,east = min_lat,min_lon,max_lat,max_lon
    return (miny, minx, maxy, maxx)


def _region_polygon_3857_circle(lat: float, lon: float, radius_m: float):
    from shapely.geometry import Point
    from shapely.ops import transform
    from pyproj import Transformer

    wgs84_to_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
    pt_3857 = transform(wgs84_to_3857, Point(lon, lat))
    return pt_3857.buffer(float(radius_m))


def _region_polygon_3857_bbox(minx: float, miny: float, maxx: float, maxy: float):
    from shapely.geometry import box
    from shapely.ops import transform
    from pyproj import Transformer

    wgs84_to_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform
    return transform(wgs84_to_3857, box(minx, miny, maxx, maxy))


def _area_km2(poly_3857) -> float:
    return float(poly_3857.area) / 1_000_000.0


# -----------------------
# Cache lookups
# -----------------------
def get_cached_osm_metrics_point(
    session: Session,
    *,
    lat: float,
    lon: float,
    buffer_m: int,
    detail: Detail,
    coord_precision: int = 5,
) -> Optional[dict[str, Any]]:
    settings = get_settings()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.osm_cache_ttl_days)

    lat_r = _round_coord(lat, coord_precision)
    lon_r = _round_coord(lon, coord_precision)

    row = session.execute(
        select(OsmMetricsPoint)
        .where(
            and_(
                OsmMetricsPoint.lat_round == lat_r,
                OsmMetricsPoint.lon_round == lon_r,
                OsmMetricsPoint.buffer_m == buffer_m,
                OsmMetricsPoint.extracted_at >= cutoff,
            )
        )
        .order_by(desc(OsmMetricsPoint.extracted_at))
        .limit(1)
    ).scalar_one_or_none()

    if not row:
        return None

    metrics = row.metrics or {}
    cached_detail = (metrics.get("_meta", {}) or {}).get("detail")

    # If user asked basic and we have full cached, we can return a downgraded view.
    if detail == "basic" and cached_detail == "full":
        return _downgrade_full_to_basic(metrics)

    # If user asked full but cache is basic, do not use it.
    if detail == "full" and cached_detail != "full":
        return None

    return metrics


def get_cached_osm_metrics_bbox(
    session: Session,
    *,
    minx: float,
    miny: float,
    maxx: float,
    maxy: float,
    detail: Detail,
    coord_precision: int = 5,
) -> Optional[dict[str, Any]]:
    settings = get_settings()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.osm_cache_ttl_days)

    minx_r, miny_r, maxx_r, maxy_r = _round_bbox(minx, miny, maxx, maxy, coord_precision)

    row = session.execute(
        select(OsmMetricsBbox)
        .where(
            and_(
                OsmMetricsBbox.minx_round == minx_r,
                OsmMetricsBbox.miny_round == miny_r,
                OsmMetricsBbox.maxx_round == maxx_r,
                OsmMetricsBbox.maxy_round == maxy_r,
                OsmMetricsBbox.extracted_at >= cutoff,
            )
        )
        .order_by(desc(OsmMetricsBbox.extracted_at))
        .limit(1)
    ).scalar_one_or_none()

    if not row:
        return None

    metrics = row.metrics or {}
    cached_detail = (metrics.get("_meta", {}) or {}).get("detail")

    if detail == "basic" and cached_detail == "full":
        return _downgrade_full_to_basic(metrics)

    if detail == "full" and cached_detail != "full":
        return None

    return metrics


def _downgrade_full_to_basic(full: dict[str, Any]) -> dict[str, Any]:
    """
    Keep backward-compatible top-level keys and drop heavier sections.
    """
    keep = {
        "road_total_length_m",
        "road_length_by_class_m",
        "facility_counts",
        "buffer_m",
        "point",
        "bbox",
        "source",
        "cached",
        "region",
        "region_area_m2",
        "_meta",
        "debug",
    }
    out = {k: full.get(k) for k in keep if k in full}
    meta = out.get("_meta", {}) or {}
    meta["detail_returned"] = "basic"
    meta["detail_cached"] = "full"
    out["_meta"] = meta
    return out


# -----------------------
# Compute (Overpass)
# -----------------------
def compute_osm_metrics_region(
    *,
    region_type: RegionType,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_m: Optional[int] = None,
    bbox: Optional[tuple[float, float, float, float]] = None,  # (minx,miny,maxx,maxy)
    detail: Detail = "basic",
    accurate_coverage: bool = False,
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Returns a dict that can be cached as-is in DB.
    """
    if region_type == "circle":
        assert lat is not None and lon is not None and radius_m is not None
        if radius_m > MAX_RADIUS_M:
            raise ValueError(f"radius_m too large (max {MAX_RADIUS_M})")

        region_poly_3857 = _region_polygon_3857_circle(lat, lon, radius_m)
        region_area_m2 = float(region_poly_3857.area)

        region_info = {"type": "circle", "center": {"lat": lat, "lon": lon}, "radius_m": int(radius_m)}
        point_info = {"lat": lat, "lon": lon}
        bbox_info = None
    else:
        assert bbox is not None
        minx, miny, maxx, maxy = bbox
        region_poly_3857 = _region_polygon_3857_bbox(minx, miny, maxx, maxy)
        area_km2 = _area_km2(region_poly_3857)
        if area_km2 > MAX_BBOX_AREA_KM2:
            raise ValueError(f"bbox too large: {area_km2:.2f} km² > {MAX_BBOX_AREA_KM2} km²")

        region_area_m2 = float(region_poly_3857.area)
        region_info = {"type": "bbox", "bbox": {"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy}}
        point_info = None
        bbox_info = {"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy}

    t0 = time.time()
    client = OverpassClient()

    # -------------------
    # Roads (ways with highway)
    # -------------------
    if region_type == "circle":
        roads_query = f"""
        [out:json][timeout:45];
        (
          way["highway"](around:{radius_m},{lat},{lon});
        );
        out geom;
        """
    else:
        south, west, north, east = _bbox_to_overpass(*bbox_info.values())  # type: ignore[arg-type]
        roads_query = f"""
        [out:json][timeout:45];
        (
          way["highway"]({south},{west},{north},{east});
        );
        out geom;
        """

    roads_data = client.query(roads_query)
    roads_metrics = _compute_road_lengths(roads_data, region_poly_3857, top_n=top_n)

    # -------------------
    # Facilities (nwr with tags) - counts + optional nearest distances in full mode
    # -------------------
    if region_type == "circle":
        fac_query = f"""
        [out:json][timeout:45];
        (
          nwr["amenity"](around:{radius_m},{lat},{lon});
          nwr["shop"](around:{radius_m},{lat},{lon});
          nwr["leisure"](around:{radius_m},{lat},{lon});
          nwr["tourism"](around:{radius_m},{lat},{lon});
          nwr["public_transport"](around:{radius_m},{lat},{lon});
          nwr["highway"="bus_stop"](around:{radius_m},{lat},{lon});
          nwr["railway"~"station|stop|halt|tram_stop"](around:{radius_m},{lat},{lon});
        );
        out tags center;
        """
    else:
        south, west, north, east = _bbox_to_overpass(*bbox_info.values())  # type: ignore[arg-type]
        fac_query = f"""
        [out:json][timeout:45];
        (
          nwr["amenity"]({south},{west},{north},{east});
          nwr["shop"]({south},{west},{north},{east});
          nwr["leisure"]({south},{west},{north},{east});
          nwr["tourism"]({south},{west},{north},{east});
          nwr["public_transport"]({south},{west},{north},{east});
          nwr["highway"="bus_stop"]({south},{west},{north},{east});
          nwr["railway"~"station|stop|halt|tram_stop"]({south},{west},{north},{east});
        );
        out tags center;
        """

    fac_data = client.query(fac_query)
    fac_metrics = _compute_facilities(fac_data)

    # -------------------
    # Landuse / green / water proxies (WAYS ONLY) - full mode only
    # -------------------
    landuse_metrics = {}
    if detail == "full":
        if region_type == "circle":
            landuse_query = f"""
            [out:json][timeout:60];
            (
              way["leisure"="park"](around:{radius_m},{lat},{lon});
              way["landuse"="grass"](around:{radius_m},{lat},{lon});
              way["landuse"="forest"](around:{radius_m},{lat},{lon});
              way["natural"="wood"](around:{radius_m},{lat},{lon});
              way["natural"="water"](around:{radius_m},{lat},{lon});
            );
            out geom;
            """
        else:
            south, west, north, east = _bbox_to_overpass(*bbox_info.values())  # type: ignore[arg-type]
            landuse_query = f"""
            [out:json][timeout:60];
            (
              way["leisure"="park"]({south},{west},{north},{east});
              way["landuse"="grass"]({south},{west},{north},{east});
              way["landuse"="forest"]({south},{west},{north},{east});
              way["natural"="wood"]({south},{west},{north},{east});
              way["natural"="water"]({south},{west},{north},{east});
            );
            out geom;
            """

        landuse_data = client.query(landuse_query)
        landuse_metrics = _compute_landuse_areas_ways_only(
            landuse_data,
            region_poly_3857,
            region_area_m2=region_area_m2,
            accurate_coverage=accurate_coverage,
        )

    elapsed = time.time() - t0

    # Build output (keep your existing top-level keys)
    metrics: dict[str, Any] = {}
    metrics.update(roads_metrics)
    metrics.update(fac_metrics)

    metrics["region"] = region_info
    metrics["region_area_m2"] = round(region_area_m2, 2)
    if region_type == "circle":
        metrics["buffer_m"] = int(radius_m)  # keep existing field name
        metrics["point"] = point_info
    else:
        metrics["bbox"] = bbox_info
        metrics["buffer_m"] = 0

    if landuse_metrics:
        metrics["landuse"] = landuse_metrics

    metrics["source"] = "overpass"
    metrics["_meta"] = {
        "detail": detail,
        "accurate_coverage_requested": bool(accurate_coverage),
        "top_n": int(top_n),
        "version": 2,
    }
    metrics["debug"] = {
        "request_duration_s": round(elapsed, 3),
        "note": "OSM metrics are derived from Overpass; large regions may be slow or partial.",
    }

    return metrics


def _compute_road_lengths(roads_data: Optional[dict[str, Any]], region_poly_3857, *, top_n: int = 10) -> dict[str, Any]:
    import geopandas as gpd
    from shapely.geometry import LineString
    from shapely.ops import transform
    from pyproj import Transformer

    if not roads_data or "elements" not in roads_data:
        return {
            "road_total_length_m": 0.0,
            "road_length_by_class_m": {},
            "road_length_by_highway_m_top": [],
        }

    wgs84_to_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform

    lines_3857 = []
    highway_tags = []

    for el in roads_data["elements"]:
        if el.get("type") != "way":
            continue
        tags = el.get("tags", {}) or {}
        hwy = tags.get("highway")
        geom = el.get("geometry")
        if not hwy or not geom:
            continue
        coords = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
        if len(coords) < 2:
            continue

        ls = LineString(coords)
        ls_3857 = transform(wgs84_to_3857, ls)

        clipped = ls_3857.intersection(region_poly_3857)
        if clipped.is_empty:
            continue
        # keep only line results
        if clipped.geom_type == "LineString":
            lines_3857.append(clipped)
            highway_tags.append(str(hwy))
        elif clipped.geom_type == "MultiLineString":
            for part in clipped.geoms:
                lines_3857.append(part)
                highway_tags.append(str(hwy))

    if not lines_3857:
        return {
            "road_total_length_m": 0.0,
            "road_length_by_class_m": {},
            "road_length_by_highway_m_top": [],
        }

    gdf = gpd.GeoDataFrame({"highway": highway_tags}, geometry=lines_3857, crs="EPSG:3857")
    gdf["len_m"] = gdf.geometry.length
    total_len = float(gdf["len_m"].sum())

    # buckets (keep your existing ones)
    buckets = {
        "motorway": {"motorway", "motorway_link", "trunk", "trunk_link"},
        "primary": {"primary", "primary_link"},
        "secondary": {"secondary", "secondary_link"},
        "tertiary": {"tertiary", "tertiary_link"},
        "residential": {"residential", "living_street", "unclassified"},
        "service": {"service"},
        "other": set(),
    }

    by_bucket: dict[str, float] = {}
    by_highway: dict[str, float] = {}

    for h, lm in zip(gdf["highway"], gdf["len_m"]):
        h = str(h)
        lm = float(lm)
        by_highway[h] = by_highway.get(h, 0.0) + lm

        bucket = "other"
        for b, s in buckets.items():
            if b != "other" and h in s:
                bucket = b
                break
        by_bucket[bucket] = by_bucket.get(bucket, 0.0) + lm

    top = sorted(by_highway.items(), key=lambda kv: kv[1], reverse=True)[: int(top_n)]

    return {
        "road_total_length_m": round(total_len, 2),
        "road_length_by_class_m": {k: round(v, 2) for k, v in by_bucket.items()},
        "road_length_by_highway_m_top": [{"highway": k, "length_m": round(v, 2)} for k, v in top],
    }


def _compute_facilities(fac_data: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not fac_data or "elements" not in fac_data:
        return {
            "facility_counts": {
                "amenity": 0,
                "shop": 0,
                "leisure": 0,
                "tourism": 0,
                "public_transport": 0,
                "bus_stop": 0,
                "rail_stop": 0,
            }
        }

    counts: dict[str, int] = {
        "amenity": 0,
        "shop": 0,
        "leisure": 0,
        "tourism": 0,
        "public_transport": 0,
        "bus_stop": 0,
        "rail_stop": 0,
    }

    seen: set[tuple[str, int]] = set()

    for el in fac_data["elements"]:
        el_type = el.get("type")
        el_id = el.get("id")
        if not el_type or el_id is None:
            continue

        key = (str(el_type), int(el_id))
        if key in seen:
            continue
        seen.add(key)

        tags = el.get("tags", {}) or {}

        if "amenity" in tags:
            counts["amenity"] += 1
        if "shop" in tags:
            counts["shop"] += 1
        if "leisure" in tags:
            counts["leisure"] += 1
        if "tourism" in tags:
            counts["tourism"] += 1
        if tags.get("public_transport"):
            counts["public_transport"] += 1
        if tags.get("highway") == "bus_stop":
            counts["bus_stop"] += 1
        if tags.get("railway") in {"station", "stop", "halt", "tram_stop"}:
            counts["rail_stop"] += 1

    return {"facility_counts": counts}


def _compute_landuse_areas_ways_only(
    landuse_data: Optional[dict[str, Any]],
    region_poly_3857,
    *,
    region_area_m2: float,
    accurate_coverage: bool,
) -> dict[str, Any]:
    from shapely.geometry import Polygon
    from shapely.ops import transform, unary_union
    from pyproj import Transformer

    if not landuse_data or "elements" not in landuse_data:
        return {
            "mode": "ways_only",
            "areas_m2_fast": {},
            "green_cover_ratio_fast": 0.0,
            "accurate_coverage": False,
            "areas_m2_accurate": None,
            "green_cover_ratio_accurate": None,
            "note": "No landuse/green ways returned by Overpass.",
        }

    wgs84_to_3857 = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform

    # collect polygons by category
    cats: dict[str, list[Any]] = {"park": [], "grass": [], "forest": [], "wood": [], "water": []}

    for el in landuse_data["elements"]:
        if el.get("type") != "way":
            continue
        tags = el.get("tags", {}) or {}
        geom = el.get("geometry")
        if not geom:
            continue

        coords = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
        if len(coords) < 4:
            continue
        if coords[0] != coords[-1]:
            # not a closed way; skip for area
            continue

        poly = Polygon(coords)
        if not poly.is_valid or poly.is_empty:
            continue

        poly_3857 = transform(wgs84_to_3857, poly)
        clipped = poly_3857.intersection(region_poly_3857)
        if clipped.is_empty:
            continue

        # categorize
        if tags.get("leisure") == "park":
            cats["park"].append(clipped)
        if tags.get("landuse") == "grass":
            cats["grass"].append(clipped)
        if tags.get("landuse") == "forest":
            cats["forest"].append(clipped)
        if tags.get("natural") == "wood":
            cats["wood"].append(clipped)
        if tags.get("natural") == "water":
            cats["water"].append(clipped)

    # fast areas: sum of clipped areas (may overlap)
    areas_fast = {k: float(sum(g.area for g in geoms)) for k, geoms in cats.items()}
    green_fast = areas_fast["park"] + areas_fast["grass"] + areas_fast["forest"] + areas_fast["wood"]
    green_ratio_fast = (green_fast / region_area_m2) if region_area_m2 else 0.0

    out: dict[str, Any] = {
        "mode": "ways_only",
        "areas_m2_fast": {k: round(v, 2) for k, v in areas_fast.items()},
        "green_cover_ratio_fast": round(green_ratio_fast, 6),
        "accurate_coverage": bool(accurate_coverage),
        "areas_m2_accurate": None,
        "green_cover_ratio_accurate": None,
    }

    if not accurate_coverage:
        return out

    # accurate coverage: union per category (cap)
    total_polys = sum(len(v) for v in cats.values())
    if total_polys > MAX_POLYGONS_FOR_ACCURATE_COVERAGE:
        raise ValueError(
            f"accurate_coverage requested but too many polygons ({total_polys}) > {MAX_POLYGONS_FOR_ACCURATE_COVERAGE}. "
            "Reduce bbox/radius or set accurate_coverage=false."
        )

    areas_acc: dict[str, float] = {}
    for k, geoms in cats.items():
        if not geoms:
            areas_acc[k] = 0.0
            continue
        u = unary_union(geoms)
        areas_acc[k] = float(u.area)

    green_acc = areas_acc["park"] + areas_acc["grass"] + areas_acc["forest"] + areas_acc["wood"]
    green_ratio_acc = (green_acc / region_area_m2) if region_area_m2 else 0.0

    out["areas_m2_accurate"] = {k: round(v, 2) for k, v in areas_acc.items()}
    out["green_cover_ratio_accurate"] = round(green_ratio_acc, 6)
    return out


# -----------------------
# Public entry point
# -----------------------
def get_or_compute_osm_metrics(
    session: Session,
    *,
    # circle
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    radius_m: Optional[int] = None,
    # bbox
    bbox: Optional[tuple[float, float, float, float]] = None,
    # behavior
    detail: Detail = "basic",
    accurate_coverage: bool = False,
    top_n: int = 10,
    refresh: bool = False,
    coord_precision: int = 5,
) -> dict[str, Any]:
    """
    Unified function for both circle and bbox OSM metrics.
    Caches results into appropriate cache table.
    """
    if bbox is not None:
        minx, miny, maxx, maxy = bbox

        if not refresh:
            cached = get_cached_osm_metrics_bbox(
                session,
                minx=minx,
                miny=miny,
                maxx=maxx,
                maxy=maxy,
                detail=detail,
                coord_precision=coord_precision,
            )
            if cached:
                return {"cached": True, **cached}

        metrics = compute_osm_metrics_region(
            region_type="bbox",
            bbox=bbox,
            detail=detail,
            accurate_coverage=accurate_coverage,
            top_n=top_n,
        )

        minx_r, miny_r, maxx_r, maxy_r = _round_bbox(minx, miny, maxx, maxy, coord_precision)
        session.add(
            OsmMetricsBbox(
                minx_round=minx_r,
                miny_round=miny_r,
                maxx_round=maxx_r,
                maxy_round=maxy_r,
                extracted_at=dt.datetime.now(dt.timezone.utc),
                metrics=metrics,
            )
        )
        session.flush()
        return {"cached": False, **metrics}

    # circle mode
    if lat is None or lon is None or radius_m is None:
        raise ValueError("Provide either bbox or (lat, lon, radius_m)")

    if radius_m > MAX_RADIUS_M:
        raise ValueError(f"radius_m too large (max {MAX_RADIUS_M})")

    if not refresh:
        cached = get_cached_osm_metrics_point(
            session,
            lat=lat,
            lon=lon,
            buffer_m=int(radius_m),
            detail=detail,
            coord_precision=coord_precision,
        )
        if cached:
            return {"cached": True, **cached}

    metrics = compute_osm_metrics_region(
        region_type="circle",
        lat=lat,
        lon=lon,
        radius_m=int(radius_m),
        detail=detail,
        accurate_coverage=accurate_coverage,
        top_n=top_n,
    )

    lat_r = _round_coord(lat, coord_precision)
    lon_r = _round_coord(lon, coord_precision)
    session.add(
        OsmMetricsPoint(
            lat_round=lat_r,
            lon_round=lon_r,
            buffer_m=int(radius_m),
            extracted_at=dt.datetime.now(dt.timezone.utc),
            metrics=metrics,
        )
    )
    session.flush()
    return {"cached": False, **metrics}