```md
# OSM Metrics (Developer Notes) — `osm.md`

This document describes the **OSM Metrics endpoint** in SUDS, including:
- current behavior (`v1`)
- the expanded design (`v2`)
- caching strategy (point + bbox)
- important curl calls for testing
- known limitations and recommended extensions

This file is intentionally **developer-focused** (implementation notes + future work), not end-user marketing docs.

---

## Endpoint

### `GET /osm/metrics`

Returns a **statistical summary** of OpenStreetMap (OSM) data within a region, using the Overpass API.

Supports **two region modes**:

1) **Circle (point + radius)**
- `lat`, `lon`, `radius_m`

2) **BBox rectangle**
- `bbox=minx,miny,maxx,maxy` (EPSG:4326)

---

## Authentication

All requests require:

- Header: `X-API-Key: <key>`

Example:
```bash
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/health
```

---

## Request parameters

### Region selection (choose exactly one)

**Circle region**
| Param | Type | Required | Notes |
|---|---|---:|---|
| `lat` | float | yes | Latitude |
| `lon` | float | yes | Longitude |
| `radius_m` | int | yes | Buffer radius in meters |

**BBox region**
| Param | Type | Required | Notes |
|---|---|---:|---|
| `bbox` | string | yes | `minx,miny,maxx,maxy` in lon/lat (EPSG:4326) |

### Behavior flags
| Param | Type | Default | Notes |
|---|---|---:|---|
| `detail` | string | `basic` | `basic` or `full` |
| `accurate_coverage` | bool | `false` | Only relevant for `detail=full` (landuse polygon union) |
| `top_n` | int | `10` | Used for “top categories” outputs |
| `refresh` | bool | `false` | If true, bypass DB cache and re-query Overpass |

---

## Safeguards (hard limits)

The core service enforces:
- `radius_m <= 2000` (circle mode)
- `bbox area <= ~12.6 km²` (equivalent of circle radius 2000m)
- `accurate_coverage` polygon union cap: if too many polygons (default cap 2000), request fails with 400

These are meant to reduce Overpass timeouts/429s and keep the API responsive.

---

## Output schema

### Common top-level fields (both detail levels)

- `cached: true|false`
- `source: "overpass"`
- region descriptors:
  - circle: `point`, `buffer_m`, and `region`
  - bbox: `bbox`, and `region`
- `road_total_length_m`
- `road_length_by_class_m`
- `facility_counts`

### v2 metadata keys (present after refresh under the new v2 implementation)
- `region_area_m2`
- `_meta` (detail/version/top_n)
- `debug` (request time, warnings)

### `detail=full` additional sections
- `road_length_by_highway_m_top` (top N exact OSM highway tags by clipped length)
- `landuse` (ways-only, clipped to region polygon)
  - `areas_m2_fast`
  - `green_cover_ratio_fast`
  - optionally `areas_m2_accurate` and `green_cover_ratio_accurate`

---

## Caching behavior

### Circle caching
- cached in Postgres table: `osm_metrics_point`
- key is based on:
  - rounded `lat/lon` (precision=5)
  - `buffer_m`
- TTL: `SUDS_OSM_CACHE_TTL_DAYS` (default in settings; configurable)

### BBox caching (v2)
- cached in Postgres table: `osm_metrics_bbox`
- key is based on rounded bbox coordinates:
  - minx/miny/maxx/maxy rounded to precision=5
- TTL: `SUDS_OSM_CACHE_TTL_DAYS`

### Detail-level caching rules
- If cache contains `full` and user requests `basic`, we can return a downgraded basic view.
- If cache contains `basic` and user requests `full`, the service recomputes.

---

## Important curl calls (testing)

Assume local dev:
- base URL: `http://127.0.0.1:8000`
- API key: `dev-key-1`

### 1) Circle mode — basic (default)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300"
```

### 2) Circle mode — force refresh (recompute and re-cache)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300&refresh=true"
```

### 3) Circle mode — basic explicitly
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300&detail=basic"
```

### 4) Circle mode — full
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300&detail=full"
```

### 5) Circle mode — full + accurate coverage (polygon union)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300&detail=full&accurate_coverage=true"
```

### 6) Circle mode — full + accurate coverage + refresh
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300&detail=full&accurate_coverage=true&refresh=true"
```

### 7) Circle mode — custom top N
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300&detail=full&top_n=20"
```

### 8) Circle mode — invalid radius (should fail)
```bash
curl -i -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=3000"
```

---

### 9) BBox mode — basic
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?bbox=23.3200,42.6950,23.3250,42.6975"
```

### 10) BBox mode — basic + refresh
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?bbox=23.3200,42.6950,23.3250,42.6975&refresh=true"
```

### 11) BBox mode — full
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?bbox=23.3200,42.6950,23.3250,42.6975&detail=full"
```

### 12) BBox mode — full + accurate coverage
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?bbox=23.3200,42.6950,23.3250,42.6975&detail=full&accurate_coverage=true"
```

### 13) BBox mode — full + accurate coverage + refresh
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?bbox=23.3200,42.6950,23.3250,42.6975&detail=full&accurate_coverage=true&refresh=true"
```

### 14) BBox mode — invalid bbox format (should fail)
```bash
curl -i -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?bbox=23.32,42.69,23.33"
```

### 15) BBox mode — bbox too large (should fail)
(Example bbox likely too large; adjust as needed.)
```bash
curl -i -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/osm/metrics?bbox=23.0,42.5,23.8,42.9&detail=full"
```

---

## v2 design notes (developer-facing)

### Region handling
- For circle mode:
  - query Overpass with `around:radius,lat,lon`
  - compute a circle polygon (EPSG:3857 buffer) for clipping lengths/areas

- For bbox mode:
  - query Overpass with bbox `(south,west,north,east)`
  - compute a bbox polygon (EPSG:3857) for clipping lengths/areas

### Road length computation
- Query: `way["highway"](...) out geom;`
- Convert ways into LineStrings
- Project to EPSG:3857
- Intersect each line with region polygon
- Sum clipped line lengths:
  - `road_total_length_m`
  - bucketed classes (existing)
  - top exact highway tags (v2 `full`)

### Facility counts
- Query: `nwr[...] out tags center;`
- Deduplicate using `(type,id)`
- Count tags into categories:
  - current v1 categories: amenity/shop/leisure/tourism/public_transport/bus_stop/rail_stop

### Landuse / green / water (v1 ways-only)
- Query only WAYS:
  - parks: `way["leisure"="park"]`
  - grass: `way["landuse"="grass"]`
  - forest: `way["landuse"="forest"]`
  - wood: `way["natural"="wood"]`
  - water: `way["natural"="water"]`
- Treat only closed rings as polygons
- Project to EPSG:3857 and clip to region
- Compute:
  - fast sum areas (may overlap)
  - accurate union areas (optional)
- Enforce polygon cap when `accurate_coverage=true`

---

## Known limitations

1) **Landuse relations are not included (v1)**
Large parks/forests are often relations; v1 only supports ways (quick and useful, but incomplete).

2) **Overpass is a shared public service**
Timeouts/429/504 can happen, especially for large regions.

3) **Facility counting can include non-point POIs**
Because we query `nwr`, POIs may come from ways/relations and are counted equally after dedupe.

4) **No routing graph here**
This endpoint returns *metrics*, not a routable network.

---

## Suggested future extensions (v3+)

### Facility taxonomy + nearest distances
In `detail=full`, add:
- counts by category (education, health, food, finance, public services, leisure)
- density per km²
- nearest distances from reference point:
  - nearest pharmacy/school/supermarket/bus_stop/park

### Active mobility infrastructure lengths
Add length totals for:
- `highway=footway|path|steps|pedestrian`
- `cycleway=*` and `highway=cycleway`
This can complement/validate the municipal pedestrian network.

### Intersection density proxy
Approximate:
- unique road nodes
- nodes with degree >=3
- intersection density per km²

### Relation support for landuse polygons
Support multipolygon relations by fetching member ways and assembling polygons (more work, but improves coverage).

### Cache purge job
You already have `scripts/ops/purge_cache.py`.
Extend it to clear bbox OSM cache rows too if needed.

---

## Operational checks

### Verify cache table counts
```bash
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM osm_metrics_point;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM osm_metrics_bbox;"
```

### Purge cache (if enabled)
```bash
make purge-cache
```
(Ensure purge script includes bbox table if you want it cleaned as well.)
```