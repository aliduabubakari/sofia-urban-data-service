# Weather Endpoints (Open‑Meteo) — Developer Notes

This document describes the SUDS weather endpoints:
- `GET /weather/daily` (backwards compatible daily series)
- `GET /weather/timeseries` (daily/hourly + archive/forecast)
- `GET /weather/stats` (summary metrics over the returned timeseries)

Weather data is retrieved from Open‑Meteo and cached in Postgres for reproducibility and shared caching across internal users.

---

## 1) High-level design decisions

### 1.1 Providers / Sources
We support two sources:

- `source=archive`
  - Uses: `https://archive-api.open-meteo.com/v1/archive`
  - Intended for historical (stable) values
  - Cached with long TTL (days)

- `source=forecast`
  - Uses: `https://api.open-meteo.com/v1/forecast`
  - Intended for future (mutable) values
  - Cached with short TTL (hours)

**Provider labels stored in DB:**
- `openmeteo_archive`
- `openmeteo_forecast`

### 1.2 Granularity
We support:
- `granularity=daily`
- `granularity=hourly`

**Important note:** For simplicity and consistency, both daily and hourly endpoints use `start` and `end` as **dates** (`YYYY-MM-DD`). Hourly returns all hours in the requested date range.

### 1.3 Coordinate rounding (cache key)
We round coordinates before caching to reduce cache fragmentation:

- `lat_round = round(lat, 4)`
- `lon_round = round(lon, 4)`

This is ~10–11 meters at mid-latitudes, which is acceptable for weather caching.

### 1.4 Timezone choice
- Hourly is requested in `timezone=UTC` (default) to avoid DST (23/25-hour days).
- Daily also defaults to UTC.
- If needed later, we can support `timezone=Europe/Sofia` as an option, but that complicates hourly ranges.

### 1.5 DB-backed caching vs HTTP caching
We intentionally cache results in Postgres instead of using `requests_cache`:
- shared cache for all users
- durable across restarts
- easier auditability and reproducibility

### 1.6 Forecast refresh policy
Forecast data can change. We implement:
- `SUDS_WEATHER_FORECAST_CACHE_TTL_HOURS` (default: 6)

If cached forecast rows are older than `now - TTL`, the service refetches and upserts.

---

## 2) Database schema (cache tables)

### 2.1 Daily cache
Table: `weather_daily_point`

Key fields:
- `lat_round`, `lon_round`
- `date` (DATE)
- `provider` (`openmeteo_archive` or `openmeteo_forecast`)
- `values` (JSONB payload)

Unique constraint:
- `(lat_round, lon_round, date, provider)`

### 2.2 Hourly cache
Table: `weather_hourly_point`

Key fields:
- `lat_round`, `lon_round`
- `timestamp` (`timestamp with time zone`)
- `provider`
- `values` (JSONB payload)

Unique constraint:
- `(lat_round, lon_round, timestamp, provider)`

### 2.3 Upsert implementation note (important)
The JSONB column is named `values`. When using SQLAlchemy insert upserts, always reference:
- `stmt.excluded["values"]` (NOT `stmt.excluded.values`)
to avoid a Python method-name collision.

---

## 3) Open‑Meteo variables requested

### 3.1 Daily variables
We request:
- `temperature_2m_max`
- `temperature_2m_min`
- `apparent_temperature_max`
- `apparent_temperature_min`
- `precipitation_sum`
- `daylight_duration`
- `windspeed_10m_max`
- `winddirection_10m_dominant`
- `windgusts_10m_max`
- `relative_humidity_2m_max`
- `relative_humidity_2m_min`

We also attach:
- `elevation_m` from the top-level Open‑Meteo response

**Derived fields added per day:**
- `temperature_2m_mean = (temperature_2m_max + temperature_2m_min)/2`
- `relative_humidity_2m_mean = (rh_max + rh_min)/2`

### 3.2 Hourly variables
We request:
- `temperature_2m`
- `relative_humidity_2m`
- `precipitation`
- `windspeed_10m`
- `winddirection_10m`
- `windgusts_10m`

We also attach:
- `elevation_m`

---

## 4) Endpoints

All endpoints require:
- header: `X-API-Key: <key>`

---

### 4.1 `GET /weather/daily`
Backwards-compatible daily endpoint.

#### Query parameters
- `lat` (float) — required
- `lon` (float) — required
- `start` (date) — required
- `end` (date) — required
- `source` (`archive` | `forecast`) — optional (default: `archive`)

#### Response shape
```json
{
  "lat": 42.69,
  "lon": 23.32,
  "granularity": "daily",
  "source": "archive",
  "start": "2024-08-01",
  "end": "2024-08-07",
  "rows": [
    {
      "date": "2024-08-01",
      "elevation_m": 559.0,
      "temperature_2m_max": ...,
      "temperature_2m_min": ...,
      "temperature_2m_mean": ...,
      "windspeed_10m_max": ...,
      "winddirection_10m_dominant": ...,
      "precipitation_sum": ...
    }
  ]
}
```

---

### 4.2 `GET /weather/timeseries`
Unified timeseries endpoint.

#### Query parameters
- `lat`, `lon` — required
- `start`, `end` — required (date)
- `granularity` (`daily` | `hourly`) — default: `daily`
- `source` (`archive` | `forecast`) — default: `archive`

#### Guardrails
- Hourly requests are capped by a server-side maximum range length (default: 14 days) to prevent huge payloads.

#### Response shape
Same as `/weather/daily`, but:
- `granularity` can be `"hourly"`
- hourly rows have `timestamp` instead of `date`

---

### 4.3 `GET /weather/stats`
Computes summary statistics over the time series returned by `/weather/timeseries`.

#### Query parameters
Same as `/weather/timeseries`:
- `lat`, `lon`, `start`, `end`
- `granularity` (`daily`|`hourly`)
- `source` (`archive`|`forecast`)

#### Returned stats (daily)
- `min/max/mean` for:
  - `temperature_2m_max`
  - `temperature_2m_min`
  - `temperature_2m_mean`
  - `windspeed_10m_max`
- `precipitation_sum_total` (sum across days)
- `winddirection_10m_dominant_circular_mean`:
  - circular mean over degrees (not arithmetic mean)

#### Returned stats (hourly)
- `min/max/mean` for:
  - `temperature_2m`
  - `windspeed_10m`
- `precipitation_total` (sum across hours)
- `winddirection_10m_circular_mean`

---

## 5) Calculation details (developer notes)

### 5.1 Circular mean for wind direction
Wind direction is an angle; naive averaging breaks across the 0/360 boundary.

We compute circular mean:
- convert each degree θ to unit vector (cos θ, sin θ)
- average vectors
- convert back to angle via atan2
- normalize to [0, 360)

If all vectors cancel out (sum ~ 0), circular mean is undefined -> null.

### 5.2 Forecast staleness check
For forecast cache rows:
- if newest `updated_at` is older than `(now - SUDS_WEATHER_FORECAST_CACHE_TTL_HOURS)`, we refresh.

Archive data is assumed stable; no staleness refresh unless missing.

### 5.3 Data quality / missing values
Stats computations ignore non-numeric values and NaNs.
`precipitation_sum_total` and `precipitation_total` treat missing as 0.

---

## 6) Common error modes

### 6.1 “Hourly range too large”
Hourly requests are capped (default: 14 days). If exceeded, you’ll get HTTP 400.

Solution:
- request fewer days
- or increase server cap (not recommended for public endpoints)

### 6.2 Open‑Meteo errors / downtime
Transient errors can occur. Because we cache in DB, failures affect only cache misses.

---

## 7) Configuration

Add/confirm these in `.env`:

```env
SUDS_OPENMETEO_ARCHIVE_URL=https://archive-api.open-meteo.com/v1/archive
SUDS_OPENMETEO_FORECAST_URL=https://api.open-meteo.com/v1/forecast

SUDS_WEATHER_CACHE_TTL_DAYS=90
SUDS_WEATHER_FORECAST_CACHE_TTL_HOURS=6
```

---

# 8) Complete curl call list (testing + documentation)

All calls assume:
- API base URL: `http://127.0.0.1:8000`
- API key: `dev-key-1`

---

## 8.1 Daily endpoint: `/weather/daily`

### A) Daily archive (historical)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/daily?lat=42.69&lon=23.32&start=2024-08-01&end=2024-08-07&source=archive"
```

### B) Daily forecast (future)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/daily?lat=42.69&lon=23.32&start=2026-01-25&end=2026-02-01&source=forecast"
```

---

## 8.2 Timeseries endpoint: `/weather/timeseries`

### C) Timeseries daily archive (equivalent to /weather/daily)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/timeseries?lat=42.69&lon=23.32&granularity=daily&source=archive&start=2024-08-01&end=2024-08-07"
```

### D) Timeseries daily forecast
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/timeseries?lat=42.69&lon=23.32&granularity=daily&source=forecast&start=2026-01-25&end=2026-02-01"
```

### E) Timeseries hourly archive (1 day)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/timeseries?lat=42.69&lon=23.32&granularity=hourly&source=archive&start=2024-08-01&end=2024-08-01"
```

### F) Timeseries hourly archive (2 days)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/timeseries?lat=42.69&lon=23.32&granularity=hourly&source=archive&start=2024-08-01&end=2024-08-02"
```

### G) Timeseries hourly forecast (future; 1 day)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/timeseries?lat=42.69&lon=23.32&granularity=hourly&source=forecast&start=2026-01-25&end=2026-01-25"
```

### H) Timeseries hourly forecast (future; 2 days)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/timeseries?lat=42.69&lon=23.32&granularity=hourly&source=forecast&start=2026-01-25&end=2026-01-26"
```

### I) Hourly range too large (expected to fail; default cap 14 days)
```bash
curl -i -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/timeseries?lat=42.69&lon=23.32&granularity=hourly&source=archive&start=2024-08-01&end=2024-09-01"
```

---

## 8.3 Stats endpoint: `/weather/stats`

### J) Stats daily archive (month window)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/stats?lat=42.69&lon=23.32&granularity=daily&source=archive&start=2024-08-01&end=2024-08-31"
```

### K) Stats daily forecast (future window)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/stats?lat=42.69&lon=23.32&granularity=daily&source=forecast&start=2026-01-25&end=2026-02-01"
```

### L) Stats hourly archive (1–2 days)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/stats?lat=42.69&lon=23.32&granularity=hourly&source=archive&start=2024-08-01&end=2024-08-02"
```

### M) Stats hourly forecast (future 1 day)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/weather/stats?lat=42.69&lon=23.32&granularity=hourly&source=forecast&start=2026-01-25&end=2026-01-25"
```

---

## 8.4 Cache verification (optional, DB-level)

### N) Check daily cache rows (archive)
```bash
docker exec -it suds-postgis psql -U postgres -d suds -c \
"SELECT COUNT(*) FROM weather_daily_point WHERE provider='openmeteo_archive';"
```

### O) Check daily cache rows (forecast)
```bash
docker exec -it suds-postgis psql -U postgres -d suds -c \
"SELECT COUNT(*) FROM weather_daily_point WHERE provider='openmeteo_forecast';"
```

### P) Check hourly cache rows (archive)
```bash
docker exec -it suds-postgis psql -U postgres -d suds -c \
"SELECT COUNT(*) FROM weather_hourly_point WHERE provider='openmeteo_archive';"
```

### Q) Check hourly cache rows (forecast)
```bash
docker exec -it suds-postgis psql -U postgres -d suds -c \
"SELECT COUNT(*) FROM weather_hourly_point WHERE provider='openmeteo_forecast';"
```

---
```

---

## Notes / small optional improvements you may want to add later
- Add `variables=` selection (whitelisted variables) so users can choose which fields to fetch.
- Add `timezone=` parameter (default UTC) if analysts need local-time series.
- Add `source=auto` later (split archive+forecast and merge when range crosses “today”).