from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.orm import Session
import datetime as dt

from suds_core.config.settings import get_settings
from suds_core.connectors.overpass import OverpassClient
from suds_core.db.models import OsmMetricsPoint


def _round_coord(x: float, precision: int = 5) -> float:
    # OSM is more local; tighter rounding is OK
    return round(float(x), precision)


def get_cached_osm_metrics_point(
    session: Session,
    *,
    lat: float,
    lon: float,
    buffer_m: int = 300,
    coord_precision: int = 5,
) -> Optional[dict[str, Any]]:
    settings = get_settings()
    lat_r = _round_coord(lat, coord_precision)
    lon_r = _round_coord(lon, coord_precision)
    
    # Calculate TTL cutoff time
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.osm_cache_ttl_days)

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

    return row.metrics if row else None


def compute_osm_metrics_point(
    *,
    lat: float,
    lon: float,
    buffer_m: int = 300,
) -> dict[str, Any]:
    """
    Compute:
      - road_total_length_m + by highway class (basic buckets)
      - facility counts by key categories (amenity, shop, leisure, tourism, public_transport)
    """
    client = OverpassClient()

    # ROADS query (ways with highway)
    roads_query = f"""
    [out:json][timeout:30];
    (
      way["highway"](around:{buffer_m},{lat},{lon});
    );
    out geom;
    """

    roads_data = client.query(roads_query)
    road_len_by_class: dict[str, float] = {}

    if roads_data and "elements" in roads_data:
        # Build length by class in a simple way by summing segment lengths in EPSG:4326 approx -> better to compute in PostGIS,
        # but here we do quick shapely length in meters by projecting to 3857.
        import geopandas as gpd
        from shapely.geometry import LineString

        lines = []
        classes = []
        for el in roads_data["elements"]:
            if el.get("type") != "way":
                continue
            tags = el.get("tags", {})
            hwy = tags.get("highway")
            geom = el.get("geometry")
            if not hwy or not geom:
                continue
            coords = [(p["lon"], p["lat"]) for p in geom if "lon" in p and "lat" in p]
            if len(coords) < 2:
                continue
            lines.append(LineString(coords))
            classes.append(str(hwy))

        if lines:
            gdf = gpd.GeoDataFrame({"highway": classes}, geometry=lines, crs="EPSG:4326").to_crs("EPSG:3857")
            gdf["len_m"] = gdf.geometry.length
            total_len = float(gdf["len_m"].sum())
            # basic buckets
            buckets = {
                "motorway": {"motorway", "motorway_link", "trunk", "trunk_link"},
                "primary": {"primary", "primary_link"},
                "secondary": {"secondary", "secondary_link"},
                "tertiary": {"tertiary", "tertiary_link"},
                "residential": {"residential", "living_street", "unclassified"},
                "service": {"service"},
                "other": set(),
            }

            for h, lm in zip(gdf["highway"], gdf["len_m"]):
                h = str(h)
                bucket = "other"
                for b, s in buckets.items():
                    if b != "other" and h in s:
                        bucket = b
                        break
                road_len_by_class[bucket] = road_len_by_class.get(bucket, 0.0) + float(lm)

            metrics: dict[str, Any] = {
                "road_total_length_m": round(total_len, 2),
                "road_length_by_class_m": {k: round(v, 2) for k, v in road_len_by_class.items()},
            }
        else:
            metrics = {"road_total_length_m": 0.0, "road_length_by_class_m": {}}
    else:
        metrics = {"road_total_length_m": 0.0, "road_length_by_class_m": {}}

    # FACILITIES query (nodes+ways+relations with common tags)
    facilities_query = f"""
    [out:json][timeout:30];
    (
      node["amenity"](around:{buffer_m},{lat},{lon});
      way["amenity"](around:{buffer_m},{lat},{lon});
      node["shop"](around:{buffer_m},{lat},{lon});
      way["shop"](around:{buffer_m},{lat},{lon});
      node["leisure"](around:{buffer_m},{lat},{lon});
      way["leisure"](around:{buffer_m},{lat},{lon});
      node["tourism"](around:{buffer_m},{lat},{lon});
      way["tourism"](around:{buffer_m},{lat},{lon});
      node["public_transport"](around:{buffer_m},{lat},{lon});
      node["highway"="bus_stop"](around:{buffer_m},{lat},{lon});
      node["railway"~"station|stop|halt|tram_stop"](around:{buffer_m},{lat},{lon});
    );
    out tags center;
    """

    fac_data = client.query(facilities_query)
    counts: dict[str, int] = {
        "amenity": 0,
        "shop": 0,
        "leisure": 0,
        "tourism": 0,
        "public_transport": 0,
        "bus_stop": 0,
        "rail_stop": 0,
    }

    if fac_data and "elements" in fac_data:
        for el in fac_data["elements"]:
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

    metrics["facility_counts"] = counts
    metrics["buffer_m"] = buffer_m
    metrics["point"] = {"lat": lat, "lon": lon}
    metrics["source"] = "overpass"

    return metrics


def get_or_compute_osm_metrics_point(
    session: Session,
    *,
    lat: float,
    lon: float,
    buffer_m: int = 300,
    force_refresh: bool = False,
    coord_precision: int = 5,
) -> dict[str, Any]:
    settings = get_settings()
    lat_r = _round_coord(lat, coord_precision)
    lon_r = _round_coord(lon, coord_precision)

    if not force_refresh:
        cached = get_cached_osm_metrics_point(session, lat=lat, lon=lon, buffer_m=buffer_m, coord_precision=coord_precision)
        if cached:
            return {"cached": True, **cached}

    metrics = compute_osm_metrics_point(lat=lat, lon=lon, buffer_m=buffer_m)

    session.add(
        OsmMetricsPoint(
            lat_round=lat_r,
            lon_round=lon_r,
            buffer_m=buffer_m,
            extracted_at=dt.datetime.now(dt.timezone.utc),
            metrics=metrics,
        )
    )
    session.flush()
    return {"cached": False, **metrics}