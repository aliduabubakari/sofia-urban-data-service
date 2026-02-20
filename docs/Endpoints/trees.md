# Trees (`trees`) — Geometry + Stats

Trees are point features representing individual urban trees. In addition to geometry, the dataset contains crown/height/elevation and 3D visualization metadata (e.g., GLB model name and scale).

**Dataset name:** `trees`  
**Geometry type:** `POINT` (EPSG:4326)  
**Table:** `trees` (PostGIS)  
**Primary use cases:**
- canopy/shade proxy (via crown area)
- vertical structure proxy (via height)
- 3D rendering metadata (model/model_scale)
- local vegetation density around stations/POIs

---

## Authentication
All endpoints require:

- Header: `X-API-Key: <key>`

Example:
```bash
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/health
```

---

# 1) Trees geometries: `GET /datasets/trees`

Returns a GeoJSON FeatureCollection of tree points.

## Supported query modes
- **BBox query** (map-friendly, predictable)
- **Radius query** (around a point; **enabled** with guardrails)

## Input parameters

| Parameter | Type | Description |
|---|---|---|
| `bbox` | string | Bounding box: `min_lon,min_lat,max_lon,max_lat` (EPSG:4326). |
| `lat` | float | Center latitude (for radius query). |
| `lon` | float | Center longitude (for radius query). |
| `radius_m` | integer/float | Radius in meters (for radius query). **Max = 500** for trees geometry endpoint. |
| `limit` | integer | Max features returned (capped server-side). |
| `offset` | integer | Pagination offset. |
| `include_boundary` | bool | If `true` include boundary-touching trees; if `false` exclude boundary-touching trees (strict). |
| `order_by` | string | `id` or `distance`. Default: bbox → `id`, radius → `distance`. |
| `include_distance` | bool | If `true`, adds `distance_m` to properties when ordering by distance. |

### Notes
- Trees do **not** support `clip=true` (clipping has no meaning for points).
- For `order_by=distance`, `lat` and `lon` must be provided.
- If `bbox` is provided, bbox query takes precedence.

---

## 1.1 BBox query curl examples

### A) BBox query (default)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees?bbox=23.3200,42.6950,23.3250,42.6975&limit=2000&offset=0"
```

### B) BBox query (strict inside bbox; exclude boundary-touching trees)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees?bbox=23.3200,42.6950,23.3250,42.6975&include_boundary=false&limit=2000"
```

### C) BBox query ordered by distance to a reference point (requires lat+lon)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees?bbox=23.3200,42.6950,23.3250,42.6975&lat=42.6962&lon=23.3223&order_by=distance&limit=2000&include_distance=true"
```

### D) BBox query ordered by distance + strict inside bbox
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees?bbox=23.3200,42.6950,23.3250,42.6975&lat=42.6962&lon=23.3223&order_by=distance&include_boundary=false&limit=2000&include_distance=true"
```

---

## 1.2 Radius query curl examples (enabled; max 500m)

### E) Radius query (default = nearest-first)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees?lat=42.6970&lon=23.3220&radius_m=300&limit=2000"
```

### F) Radius query (strict inside circle; exclude boundary-touching trees)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees?lat=42.6970&lon=23.3220&radius_m=300&include_boundary=false&limit=2000"
```

### G) Radius query (explicit nearest-first + include distance)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees?lat=42.6970&lon=23.3220&radius_m=300&order_by=distance&limit=2000&include_distance=true"
```

### H) Radius query too large (should fail; max 500 for geometry endpoint)
```bash
curl -i -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees?lat=42.6970&lon=23.3220&radius_m=600&limit=1000"
```

### I) Nearest tree only (limit=1)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees?lat=42.6970&lon=23.3220&radius_m=300&limit=1&order_by=distance&include_distance=true"
```

---

## Output structure (geometry endpoint)
GeoJSON FeatureCollection of `Point` features:

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 43843,
      "geometry": { "type": "Point", "coordinates": [23.324720561, 42.695051328] },
      "properties": {
        "height_calc": 18.0,
        "crown_diam": 12.0,
        "crown_area": 113.1,
        "z_position": 547.04,
        "leaf_type_": "неопределено",
        "model": "types_round.glb",
        "model_scale": 1.22,
        "source_id": "4062254",
        "distance_m": 42.5
      }
    }
  ],
  "crs": { "type": "name", "properties": { "name": "EPSG:4326" } }
}
```

---

# 2) Trees stats: `GET /datasets/trees/stats`

Returns aggregated tree metrics for the region, **and includes both**:
- `intersecting_stats` (boundary included)
- `strict_stats` (boundary excluded)

Stats supports both bbox and radius.

## Input parameters

| Parameter | Type | Description |
|---|---|---|
| `bbox` | string | `min_lon,min_lat,max_lon,max_lat` (EPSG:4326). |
| `lat` | float | Center latitude (radius mode). |
| `lon` | float | Center longitude (radius mode). |
| `radius_m` | integer/float | Radius in meters (radius mode). **Max = 1000** for trees stats endpoint. |
| `accurate_coverage` | bool | If `true`, computes canopy cover using union of canopy circles (no overlap double-counting). Slower. |
| `top_n` | integer | Top-N categories returned for `leaf_type_` and `model` (default 10). |
| `include_nearest_geometry` | bool | If true, includes GeoJSON feature for nearest tree. |
| `center_lat`, `center_lon` | float | (bbox mode only) Reference point for nearest tree. If omitted, bbox centroid is used. |

---

## 2.1 Stats bbox curl examples

### J) Stats (bbox; fast canopy coverage)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?bbox=23.3200,42.6950,23.3250,42.6975&top_n=10"
```

### K) Stats (bbox; accurate canopy coverage)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?bbox=23.3200,42.6950,23.3250,42.6975&accurate_coverage=true&top_n=10"
```

### L) Stats (bbox) + nearest tree geometry (uses bbox centroid unless center_lat/lon provided)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?bbox=23.3200,42.6950,23.3250,42.6975&include_nearest_geometry=true&top_n=10"
```

### M) Stats (bbox) + explicit reference point for nearest tree
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223&top_n=10"
```

### N) Stats (bbox) + explicit reference point + accurate coverage + nearest geometry
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?bbox=23.3200,42.6950,23.3250,42.6975&center_lat=42.6962&center_lon=23.3223&accurate_coverage=true&include_nearest_geometry=true&top_n=10"
```

---

## 2.2 Stats radius curl examples (max 1000m)

### O) Stats (radius; fast canopy coverage)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?lat=42.6970&lon=23.3220&radius_m=300&top_n=10"
```

### P) Stats (radius; accurate canopy coverage)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?lat=42.6970&lon=23.3220&radius_m=300&accurate_coverage=true&top_n=10"
```

### Q) Stats (radius) + nearest geometry
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?lat=42.6970&lon=23.3220&radius_m=300&include_nearest_geometry=true&top_n=10"
```

### R) Stats radius too large (should fail; max 1000)
```bash
curl -i -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?lat=42.6970&lon=23.3220&radius_m=1500&top_n=10"
```

### S) Stats accurate coverage safety guard (may fail if too many trees)
Accurate canopy union is limited to a maximum number of trees with usable canopy data (default: 5000). If exceeded, you’ll get HTTP 400 and should reduce region size or set `accurate_coverage=false`.

```bash
curl -i -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/datasets/trees/stats?lat=42.6970&lon=23.3220&radius_m=1000&accurate_coverage=true&top_n=10"
```

---

# Developer notes (Trees calculations)

These notes describe how each trees metric is computed in `suds_core/services/trees_stats.py`.

## A) Region geometry
Two query kinds exist:

### 1) BBox region
- Region polygon: `R = ST_MakeEnvelope(minx, miny, maxx, maxy, 4326)`

### 2) Radius region
- Center point: `P = ST_SetSRID(ST_MakePoint(lon, lat), 4326)`
- Circle polygon (accurate meters):  
  `R = ST_Buffer(P::geography, radius_m)::geometry`

## B) Intersecting vs strict selection
Stats always return both:

### Intersecting selection
- BBox: `ST_Intersects(tree.geom, R)`
- Radius: `ST_DWithin(tree.geom::geography, P::geography, radius_m)`  
  (distance <= radius)

### Strict selection
- BBox: `ST_ContainsProperly(R, tree.geom)`  
  (excludes boundary points)
- Radius: `ST_Distance(tree.geom::geography, P::geography) < radius_m`  
  (strictly inside circle; excludes boundary points)

## C) Area and density
Region area is computed in meters using EPSG:32635:

- `region_area_m2 = ST_Area(ST_Transform(R, 32635))`
- `tree_density_per_km2 = tree_count / (region_area_m2 / 1,000,000)`

## D) Height statistics
Using property field: `height_calc` (meters)

- mean/median/p90/min/max computed over non-null heights.

## E) Canopy cover (fast)
Primary fields:
- `crown_area` (m²) if present
- fallback estimate from `crown_diam` (meters):  
  `crown_area_est = π * (crown_diam / 2)^2`

Used canopy area per tree:
- `crown_area_used = COALESCE(crown_area, crown_area_est)`

Then:
- `sum_canopy_area_fast_m2 = Σ crown_area_used`
- `canopy_cover_ratio_fast = sum_canopy_area_fast_m2 / region_area_m2`

**Note:** This can overcount when canopies overlap.

## F) Canopy cover (accurate)
Enabled when `accurate_coverage=true`.

For each tree with usable canopy radius:
- Determine crown radius (meters):
  - `r = crown_diam / 2` if `crown_diam` exists
  - else `r = sqrt(crown_area / π)` if `crown_area` exists
- Construct canopy circle polygon:
  - `C = ST_Buffer(tree.geom::geography, r)::geometry`
- Clip to region:
  - `C_in = ST_Intersection(C, R)`
  - keep polygon components: `ST_CollectionExtract(C_in, 3)`
- Union all clipped canopies:
  - `U = ST_UnaryUnion(ST_Collect(C_in))`
- Area:
  - `sum_canopy_area_accurate_m2 = ST_Area(ST_Transform(U, 32635))`
- Ratio:
  - `canopy_cover_ratio_accurate = sum_canopy_area_accurate_m2 / region_area_m2`

**Safeguard:** If more than 5000 trees have usable canopy radius within the region, accurate coverage is rejected with HTTP 400 to avoid heavy union work.

## G) Nearest tree
Nearest tree is computed relative to:
- bbox centroid (default) or `center_lat/center_lon`
- radius center point

Distance is computed in meters via geography:
- `distance_m = ST_Distance(tree.geom::geography, ref_point::geography)`

Nearest ordering uses KNN:
- `ORDER BY tree.geom <-> ref_point`

## H) Top-N categorical breakdowns
Two categorical distributions are returned (top-N by count):
- `leaf_type_`
- `model`

Returned as:
- `[{leaf_type/model, count}, ...]`

## I) 3D metadata statistics
`model_scale` stats are returned (mean/median/p90) over non-null values.

`z_position` elevation stats are returned (mean/min/max/p10/p90) over non-null values.

---

## Operational notes
- Trees geometry radius endpoint is capped at **500m** to prevent huge responses.
- Trees stats radius endpoint is capped at **1000m** because it returns numbers rather than full point geometries.
- For large areas, prefer bbox queries and paginate (`offset`) for geometry endpoints.
- For canopy coverage, prefer `accurate_coverage=false` unless you need exact union-based coverage.
```