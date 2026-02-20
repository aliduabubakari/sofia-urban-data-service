# Geocoding (Geoapify) — Developer Notes

This document describes the **Geocoding module** in SUDS, built on **Geoapify**, including:
- supported endpoints
- request/response conventions
- caching behavior
- example curl commands for testing
- operational notes (rate limits, privacy)
- potential future extensions

Base URL (local dev): `http://127.0.0.1:8000`  
Swagger UI: `http://127.0.0.1:8000/docs`

All endpoints require:
- `X-API-Key: <key>`

Example:
```bash
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/health
```

---

## 1) Overview

The geocoding module provides:
- **Forward geocoding** (text → candidates / lat/lon)
- **Reverse geocoding** (lat/lon → address)
- **Batch forward geocoding** (multiple texts in one request)

### Provider
- Geoapify API

### Caching
We cache **only**:
- `/geocode/search`
- `/geocode/reverse`

We do **not** cache autocomplete results (not implemented) to avoid stale UI suggestions.

Cache is stored in Postgres (`geocode_cache` table). This provides:
- reproducibility
- shared caching across users
- reduced external API cost and rate-limit issues

### Privacy considerations
- Do **not** geocode child-level addresses.
- The intended use is geocoding **facility addresses** (e.g., kindergartens, schools) or other public places.

---

## 2) Environment variables

In `.env`:

```env
SUDS_GEOAPIFY_API_KEY=...
SUDS_GEOAPIFY_BASE_URL=https://api.geoapify.com/v1/geocode

SUDS_GEOCODE_RATE_LIMIT_PER_MIN=60
SUDS_GEOCODE_BATCH_MAX_SIZE=100

# Optional (disabled by default):
SUDS_GEOAPIFY_USE_BATCH_API=false
SUDS_GEOAPIFY_BATCH_MIN_SIZE=25
SUDS_GEOAPIFY_BATCH_TIMEOUT_S=60
SUDS_GEOAPIFY_BATCH_POLL_S=1.0
```

Notes:
- `SUDS_GEOAPIFY_API_KEY` is required for geocoding endpoints to work.
- Rate limit is implemented as a simple delay; caching should reduce external requests significantly.

---

## 3) Database model (cache table)

Table: `geocode_cache`

Fields (conceptual):
- `provider` (e.g., `"geoapify"`)
- `kind` (`"search"` | `"reverse"`)
- `query_hash` (sha256 of normalized query + options)
- `query_text` (normalized query)
- `best_lat`, `best_lon`, `best_formatted`, `best_confidence`
- `result` (raw JSON response stored as JSONB)
- `created_at`, `updated_at`

Uniqueness:
- `(provider, kind, query_hash)` is unique (one cache row per normalized query).

---

## 4) Endpoints

### 4.1 `GET /geocode/search`
Forward geocoding: address/name text → coordinate candidates.

#### Query Parameters

| Parameter | Type | Required | Description |
|---|---:|---:|---|
| `text` | `string` | Yes | Search string (address or place name). |
| `limit` | `int` | No | Max results (default 5, max 20). |
| `lang` | `string` | No | Language (default `"bg"`). |
| `refresh` | `bool` | No | If `true`, bypasses DB cache and fetches from Geoapify. |

#### Response (shape)
```json
{
  "cached": true,
  "provider": "geoapify",
  "kind": "search",
  "query": "ДГ 93 Чуден свят, София",
  "query_norm": "ДГ 93 Чуден свят, София",
  "best": {
    "lat": 42.69,
    "lon": 23.32,
    "formatted": "…",
    "confidence": 0.8
  },
  "result": { "... raw geoapify payload ..." }
}
```

`best` values may be `null` if no result.

---

### 4.2 `GET /geocode/reverse`
Reverse geocoding: coordinate → best matching formatted address.

#### Query Parameters

| Parameter | Type | Required | Description |
|---|---:|---:|---|
| `lat` | `float` | Yes | Latitude |
| `lon` | `float` | Yes | Longitude |
| `limit` | `int` | No | Max results (default 1, max 5) |
| `lang` | `string` | No | Language (default `"bg"`) |
| `refresh` | `bool` | No | If `true`, bypasses DB cache and fetches from Geoapify |

#### Response (shape)
```json
{
  "cached": false,
  "provider": "geoapify",
  "kind": "reverse",
  "query": { "lat": 42.697, "lon": 23.322 },
  "query_norm": "42.697,23.322",
  "best": {
    "lat": 42.697,
    "lon": 23.322,
    "formatted": "…",
    "confidence": 0.9
  },
  "result": { "... raw geoapify payload ..." }
}
```

---

### 4.3 `POST /geocode/search/batch`
Batch forward geocoding: multiple text queries → results aligned to the input list.

#### Request body
```json
{
  "queries": [
    "ДГ 93 Чуден свят, София",
    "ДГ 1, София, Лозенец"
  ],
  "limit": 3,
  "lang": "bg",
  "refresh": false
}
```

Constraints:
- Max `queries` length is controlled by `SUDS_GEOCODE_BATCH_MAX_SIZE` (default 100).

#### Response (shape)
```json
{
  "count": 2,
  "cached_hits": 1,
  "fetched": 1,
  "results": [
    {
      "index": 0,
      "query": "ДГ 93 Чуден свят, София",
      "cached": true,
      "best": { "lat": 42.69, "lon": 23.32, "formatted": "...", "confidence": 0.8 },
      "result": { "...raw..." }
    },
    {
      "index": 1,
      "query": "ДГ 1, София, Лозенец",
      "cached": false,
      "best": { "lat": 42.68, "lon": 23.33, "formatted": "...", "confidence": 0.7 },
      "result": { "...raw..." }
    }
  ]
}
```

Notes:
- Results preserve the original ordering by returning an `index`.
- The system is cache-first; only cache misses trigger external calls.
- By default, misses are fetched sequentially (safe and robust).
- Optional Geoapify Batch API support can be enabled (see Extensions).

---

## 5) Curl commands (testing and examples)

### 5.1 Forward search (basic)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/geocode/search?text=%D0%94%D0%93%2093%20%D0%A7%D1%83%D0%B4%D0%B5%D0%BD%20%D1%81%D0%B2%D1%8F%D1%82%2C%20%D0%A1%D0%BE%D1%84%D0%B8%D1%8F&limit=5&lang=bg"
```

### 5.2 Forward search (force refresh)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/geocode/search?text=%D0%94%D0%93%2093%20%D0%A7%D1%83%D0%B4%D0%B5%D0%BD%20%D1%81%D0%B2%D1%8F%D1%82%2C%20%D0%A1%D0%BE%D1%84%D0%B8%D1%8F&limit=5&lang=bg&refresh=true"
```

### 5.3 Reverse geocode (basic)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/geocode/reverse?lat=42.6970&lon=23.3220&lang=bg"
```

### 5.4 Reverse geocode (force refresh)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/geocode/reverse?lat=42.6970&lon=23.3220&lang=bg&refresh=true"
```

### 5.5 Batch search (POST)
```bash
curl -H "X-API-Key: dev-key-1" \
     -H "Content-Type: application/json" \
     -d '{
       "queries": [
         "ДГ 93 Чуден свят, София",
         "ДГ 1, София, Лозенец",
         "Детска градина 10 София"
       ],
       "limit": 3,
       "lang": "bg",
       "refresh": false
     }' \
"http://127.0.0.1:8000/geocode/search/batch"
```

### 5.6 Batch search (force refresh all)
```bash
curl -H "X-API-Key: dev-key-1" \
     -H "Content-Type: application/json" \
     -d '{
       "queries": [
         "ДГ 93 Чуден свят, София",
         "ДГ 1, София, Лозенец"
       ],
       "limit": 3,
       "lang": "bg",
       "refresh": true
     }' \
"http://127.0.0.1:8000/geocode/search/batch"
```

---

## 6) Operational notes

### 6.1 Rate limiting
The implementation uses a simple delay:
- sleep = `60 / SUDS_GEOCODE_RATE_LIMIT_PER_MIN` seconds per external request

Because of DB caching, repeated calls should be fast and not hit Geoapify often.

If you need stronger rate limiting (shared across multiple API workers), implement:
- Redis-based token bucket
- or database row-based locks with timestamps

### 6.2 Cache invalidation
There is no TTL by default. Geocoding results usually remain stable.
If needed, implement:
- `refresh=true` for manual refresh (already supported)
- scheduled cleanup of cache entries older than X months (optional)
- “soft refresh” if entry older than X days

### 6.3 Determinism and QA
For critical workflows (kindergarten siting), recommended QA steps:
- after geocoding, call SUDS neighbourhood lookup:
  - `/spatial/lookup/neighbourhood?lat=...&lon=...`
- validate district/rajon consistency with dataset-provided district fields
- flag mismatches for manual review

---

## 7) Potential extensions

### 7.1 Enable Geoapify batch job API (server-side)
Geoapify provides asynchronous batch processing:
- `POST /v1/batch/geocode/search`
- `GET /v1/batch/geocode/search?id=JOB_ID...`

SUDS already contains a feature-flag design for this:
- `SUDS_GEOAPIFY_USE_BATCH_API=true`
- `SUDS_GEOAPIFY_BATCH_MIN_SIZE=25`

Notes:
- Requires confirming Geoapify plan support and actual returned result shape.
- Still keep DB caching: batch job is only for cache misses.

### 7.2 Add autocomplete endpoint (no caching)
If a UI needs it:
- `GET /geocode/autocomplete?text=...&lang=...&limit=...`

Do not cache autocomplete by default.

### 7.3 Add geocode normalization / scoring
Add a SUDS utility to normalize Bulgarian queries:
- expand abbreviations (ул., бул., ж.к.)
- normalize quotes, hyphens
- strip trailing punctuation
- optionally attach a fixed city constraint (`"София, България"`) if missing

### 7.4 Add a “validate/geocode” endpoint
A domain-friendly endpoint that:
- geocodes the query
- returns neighbourhood/district match
- returns confidence flags and suggestions

Example:
- `POST /geocode/validate_facility`
  - input: facility name + expected district/rajon
  - output: geocode + spatial join + mismatch warnings

### 7.5 Add “Tavily-assisted address hints” (fallback)
Only for public institution names (no personal addresses):
- `POST /search/tavily/address_hint`
- returns candidate addresses and URLs
- then feed to `/geocode/search` for deterministic lat/lon

This should be rate-limited and clearly labeled as “experimental”.

### 7.6 Add caching analytics endpoints (internal)
Useful for ops:
- `GET /geocode/cache/stats` (hit rate, entries count)
- `POST /geocode/cache/purge?older_than_days=...`

---

## 8) Developer checklist (quick)

1) Add `.env` keys:
   - `SUDS_GEOAPIFY_API_KEY`
2) Create DB tables:
   ```bash
   make create-tables
   ```
3) Run API and test:
   ```bash
   make api-run
   curl -H "X-API-Key: dev-key-1" "http://127.0.0.1:8000/geocode/search?text=..."
   ```
4) Verify caching:
   - run the same request twice
   - second response should show `"cached": true`

---