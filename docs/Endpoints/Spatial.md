# Spatial Endpoints (Developer Notes)

This document describes the **Spatial Lookup** endpoint introduced in SUDS, why it exists, how to use it, and how to extend it safely.

---

## Overview

### Endpoint
`GET /spatial/lookup/neighbourhood`

### Purpose
Given a **latitude/longitude point**, return the **neighbourhood polygon** (and district/rajon) that contains that point.

This endpoint is primarily intended to support workflows where you geocode a place (e.g., a kindergarten) and need to:

- validate that the result is **in Sofia**
- assign the geocoded point to an **administrative area**
- detect geocoding errors early (wrong district / wrong location)
- support consistent joins and aggregation (neighbourhood-level reporting)

---

## Why this endpoint is important

### 1) Quality assurance for geocoding
Geocoding returns a point, but it can be wrong due to:
- ambiguous names
- misspellings or inconsistent Bulgarian formatting
- multiple matches across cities/regions
- low confidence results

By snapping the point into the **neighbourhood polygons**, you can verify:
- it falls within the expected administrative area
- it matches the expected `rajon` from the dataset (if present)

This is a very effective and explainable QA step for the AQKG (kindergarten planning) pipeline.

### 2) Enables stable joins and aggregation
Once a point is assigned a neighbourhood ID, you can:
- aggregate demand (kindergarten counts) by neighbourhood
- aggregate exposure metrics by neighbourhood
- build consistent reports and dashboards

### 3) Avoids repeating spatial logic in applications
Instead of implementing PostGIS “point-in-polygon” logic in every client (Streamlit, notebooks), the logic is centralized in SUDS and remains consistent across environments.

---

## Behavior

### Primary match (containment)
The endpoint attempts to find the neighbourhood polygon that contains the point.

### Boundary handling
Points can lie exactly on a polygon border. This can happen due to:
- rounding
- geocoding returning a point on a road boundary between polygons
- dataset boundary geometry precision

The endpoint supports boundary semantics via `include_boundary`:

- `include_boundary=true` (default): uses `ST_Covers(poly, point)`
  - points on boundary are considered inside
  - better UX for geocoding validation

- `include_boundary=false`: uses `ST_ContainsProperly(poly, point)`
  - strict inside only
  - useful for strict analytics/testing

### Fallback behavior (nearest polygon)
If no polygon contains the point, the endpoint can return the **nearest neighbourhood polygon**, controlled by:

- `fallback_nearest=true` (default)
- `max_nearest_distance_m` optional guard (recommended)

This is extremely useful to detect wrong geocodes:
- if the nearest neighbourhood is many kilometers away, the geocode is likely wrong

---

## Request Parameters

| Parameter | Type | Default | Description |
|---|---|---:|---|
| `lat` | float | required | Latitude (EPSG:4326). |
| `lon` | float | required | Longitude (EPSG:4326). |
| `include_boundary` | bool | `true` | If true, includes boundary points (`ST_Covers`). If false, strict inside (`ST_ContainsProperly`). |
| `fallback_nearest` | bool | `true` | If no containing polygon exists, return nearest neighbourhood polygon. |
| `max_nearest_distance_m` | float \| null | `null` | When set, only return nearest fallback if within this distance (meters). Useful for QA. |
| `include_geometry` | bool | `false` | If true, include neighbourhood polygon geometry (GeoJSON). Heavier response. |

---

## Response shape (typical)

```json
{
  "query": { "lat": 42.6970, "lon": 23.3220 },
  "matched": true,
  "match_method": "covers",
  "distance_m": 0.0,
  "neighbourhood": {
    "id": 123,
    "name": "Лозенец",
    "rajon": "Лозенец",
    "area_m2": 1532912.5,
    "props": { "...": "..." }
  }
}
```

### Field meanings
- `matched`
  - `true` if a polygon was matched (either containing or nearest)
  - `false` if nothing matched (or nearest was too far and rejected)
- `match_method`
  - `"covers"`: match from boundary-inclusive containment
  - `"contains_properly"`: match from strict containment
  - `"nearest"`: no containment match; nearest polygon returned
  - `"nearest_too_far"`: nearest exists but exceeds `max_nearest_distance_m`
  - `"none"`: no polygons at all (should not happen if neighbourhoods exist)
- `distance_m`
  - `0.0` for containment match
  - distance from point to polygon boundary for nearest match (meters)
- `neighbourhood`
  - contains normalized convenience fields (`name`, `rajon`) plus raw `props`
  - `geometry` included only when `include_geometry=true`

---

## Curl examples (testing)

### A) Standard lookup (boundary included, nearest fallback on)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/spatial/lookup/neighbourhood?lat=42.6970&lon=23.3220"
```

### B) Strict containment (exclude boundary points)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/spatial/lookup/neighbourhood?lat=42.6970&lon=23.3220&include_boundary=false"
```

### C) Disable nearest fallback (return matched=false if point outside all polygons)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/spatial/lookup/neighbourhood?lat=42.6970&lon=23.3220&fallback_nearest=false"
```

### D) Nearest fallback only if within 2km (recommended QA setting)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/spatial/lookup/neighbourhood?lat=42.6970&lon=23.3220&max_nearest_distance_m=2000"
```

### E) Include neighbourhood geometry (GeoJSON; heavy response)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/spatial/lookup/neighbourhood?lat=42.6970&lon=23.3220&include_geometry=true"
```

---

## Recommended usage pattern (AQKG / geocoding QA)

After geocoding a kindergarten:

1) Call neighbourhood lookup:
   - `max_nearest_distance_m=2000` (or similar)
2) Extract:
   - `neighbourhood.rajon`
3) Compare against expected district/rajon from the dataset
4) Flag mismatches

### Suggested QA logic
- If `matched=false` → **hard fail** (likely wrong geocode)
- If `match_method="nearest"` and `distance_m` is large (> 1000–2000m) → **hard fail**
- If `neighbourhood.rajon != expected_rajon` → **warning** (manual review)

This gives a consistent and explainable QA gate.

---

## Performance notes

- The containment query uses PostGIS spatial predicates and should be fast if the neighbourhood geometry column has a GiST index.
- Nearest fallback uses KNN (`geom <-> point`) ordering; also fast with GiST index.

If performance is slow, confirm neighbourhoods table has:
- `GIST(geom)` index

---

## Extension ideas (future work)

### 1) Add lookup for other polygon datasets
For example:
- `GET /spatial/lookup/green_area` (nearest green polygon, distance)
- `GET /spatial/lookup/district` (if you add a district polygons table)
- `GET /spatial/lookup/admin` (generic: dataset name + point)

If you generalize, keep safeguards:
- restrict dataset names to an allowlist
- validate geometry type is polygon/multipolygon

### 2) Add “which datasets contain this point?”
A developer-friendly endpoint could return a bundle:

`GET /spatial/lookup/context?lat=...&lon=...`

Returning:
- neighbourhood
- closest station (airquality/noise)
- nearest green area
- tree density summary (small radius)
- etc.

This would reduce round-trips for applications.

### 3) Add batch point lookup
For geocoding workflows, batch is useful:

`POST /spatial/lookup/neighbourhood/batch`
```json
{"points":[{"lat":..., "lon":...}, ...]}
```

Safeguards:
- max batch size (e.g. 200)
- return per-point results aligned to inputs

### 4) Add stronger normalization fields
If `Neighbourhoods.props` fields are stable, extend the response to include:
- canonical neighbourhood name
- district code
- stable external IDs (if present)
- normalized `rajon_norm` (lowercase, trimmed)

This makes client comparisons more robust.

### 5) Add fallback to "nearest within Sofia bbox"
If users might geocode outside Sofia frequently, you can add a “Sofia bounding box quick reject”:
- if point outside Sofia bounding extent → return matched=false immediately
- avoids misleading nearest matches far away

---

## Implementation notes (developer)

- Containment uses:
  - `ST_Covers` (include boundary)
  - `ST_ContainsProperly` (strict)
- Nearest fallback uses geography distance for meters and KNN ordering for speed.
- When multiple polygons match (rare but possible), the endpoint picks the **smallest area polygon** as the most specific match.

---

## Related endpoints
- `/geocode/search` and `/geocode/search/batch` (Geoapify caching geocode)
- `/datasets/neighbourhoods` (raw neighbourhood geometries)
- `/airquality/*` (stations and exposure)
- `/enrich/point` (context bundling)