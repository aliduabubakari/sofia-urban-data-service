# SUDS API (Internal)

Base URL (local dev): `http://127.0.0.1:8000`

Swagger UI: `http://127.0.0.1:8000/docs`

## Authentication
All endpoints require an API key:

- Header: `X-API-Key: <key>`

The server is configured via `.env`:

- `SUDS_API_KEYS=dev-key-1,dev-key-2`

Example:
```bash
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/health
```

---

## Endpoints

### 1) Health
`GET /health`

Response:
```json
{"status":"ok"}
```

---

### 2) Datasets list
`GET /datasets`

Response:
```json
{"datasets":["buildings","green_areas","neighbourhoods","pois","pedestrian_network","streets","trees"]}
```

---

### 3) Dataset features (GeoJSON)
`GET /datasets/{dataset_name}`

Supported datasets:
- `buildings`, `green_areas`, `neighbourhoods`, `pois`, `pedestrian_network`, `streets`, `trees`

#### Query modes

**A) bbox query (recommended)**
Parameters:
- `bbox=minx,miny,maxx,maxy` (EPSG:4326 lon/lat)
- `limit` (default server-side)
- `offset`
- `simplify_m` (optional; polygons/lines)

Example:
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/streets?bbox=23.30,42.65,23.36,42.71&limit=2000&simplify_m=5"
```

**B) radius query**
Parameters:
- `lat`, `lon`
- `radius_m` (meters)
- `limit`, `offset`

Example:
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/pois?lat=42.69&lon=23.32&radius_m=300&limit=2000"
```

Response format:
- GeoJSON FeatureCollection

---

### 4) OSM metrics (roads + facilities) with caching
`GET /osm/metrics`

Parameters:
- `lat`, `lon`
- `radius_m` (default 300)
- `refresh` (boolean; forces recompute via Overpass)

Example:
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/osm/metrics?lat=42.69&lon=23.32&radius_m=300"
```

Response contains:
- `cached: true|false`
- road length metrics
- facility counts

Caching:
- Stored in Postgres (`osm_metrics_point`)
- TTL controlled by `SUDS_OSM_CACHE_TTL_DAYS`

---

### 5) Weather daily (Open-Meteo) with caching
`GET /weather/daily`

Parameters:
- `lat`, `lon`
- `start=YYYY-MM-DD`
- `end=YYYY-MM-DD`

Example:
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/weather/daily?lat=42.69&lon=23.32&start=2024-08-01&end=2024-08-07"
```

Response includes daily series plus:
- `elevation_m`
- `windspeed_10m_max`
- `winddirection_10m_dominant`
- `windgusts_10m_max` (if enabled)

Caching:
- Stored in Postgres (`weather_daily_point`)
- TTL controlled by `SUDS_WEATHER_CACHE_TTL_DAYS`

---

### 6) Enrichment (combined)
`GET /enrich/point`

Returns (in one response):
- OSM metrics (cached)
- weather daily (cached)
- optional dataset geometries (bbox and/or radius)

Parameters:
- `lat`, `lon`, `radius_m`
- `start`, `end` (dates for weather)
- `datasets=streets,pois,green_areas` (optional)
- `mode=bbox|radius|both|none` (default: both)
- `limit` (per-dataset; server caps apply)
- `simplify_m` (optional)

Example:
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/enrich/point?lat=42.69&lon=23.32&radius_m=300&start=2024-08-01&end=2024-08-07&datasets=streets,pois,green_areas&mode=both&limit=2000&simplify_m=5"
```

---

## Error codes
- `401` invalid/missing API key
- `400` invalid parameters
- `500` unexpected server errors (check logs)