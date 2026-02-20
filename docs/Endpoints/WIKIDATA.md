# Wikidata Integration (Developer Notes)

This document describes the Wikidata integration implemented in SUDS:
- `/wikidata/search` (cached, with optional `type_hint`)
- `/wikidata/entity/{qid}` (cached, with “kindergarten-relevant” extracted properties)

The goal is to support the AQKG (Air-Quality Kindergarten) planning use case by
providing **lightweight, cached, extensible metadata** about neighbourhoods/districts/cities.

---

## 1) Why Wikidata in this project?

Wikidata provides a public, structured knowledge graph that can enrich spatial units with:
- **Population** (P1082) and associated **point in time** qualifier (P585) when available
- **Area** (P2046) (when available)
- **Elevation** (P2044) (often for cities; less common for neighbourhoods)
- Wikipedia links (interpretability / “explainable planning” narrative)

It is **not** the primary source for:
- green space coverage → use municipal `green_areas` + `trees` canopy + OSM landuse
- public transport access → use OSM metrics
- socioeconomic indicators → frequently missing at neighbourhood level (but extensible)

---

## 2) Implementation summary (SUDS internals)

### 2.1 Connector used
SUDS uses the **MediaWiki API** on Wikidata:

- Search:
  - `action=wbsearchentities`
- Entity:
  - `action=wbgetentities`

Base URL (default):
- `https://www.wikidata.org/w/api.php`

### 2.2 Important production detail: avoid proxy interference
Some environments set `HTTP_PROXY/HTTPS_PROXY`. This can cause 403/blocked responses
even when curl works.

To prevent this, the connector uses:
- `requests.Session()`
- `session.trust_env = False` (ignore proxy env vars for Wikidata calls)

### 2.3 User-Agent policy
Wikimedia services prefer an identifying User-Agent string.

SUDS sets:
- `User-Agent: SUDS/0.1 (contact: dev@localhost)` by default
- configurable via `SUDS_WIKIDATA_USER_AGENT`

### 2.4 Caching strategy (Postgres JSONB)
Wikidata calls are cached in Postgres to:
- reduce latency
- avoid rate limiting
- support reproducibility

Tables:
- `wikidata_search_cache`
  - key: `(query_hash, lang, limit)`
  - stores raw search response JSON
- `wikidata_entity_cache`
  - key: `(qid, lang)`
  - stores raw entity response JSON
  - TTL refresh: `SUDS_WIKIDATA_CACHE_TTL_DAYS` (default 30)

### 2.5 Type hint filtering and reranking (`type_hint`)
The Wikidata search API does **not** support type filtering directly.
SUDS implements type filtering/reranking by:

1) Performing a normal search (cached).
2) Bulk fetching candidate entities (`wbgetentities ids=Q...|Q...`) and caching them.
3) Extracting:
   - `P31` (instance of)
   - optionally `P131` (located in the administrative territorial entity)
4) Applying `type_hint`:
   - `type_mode=soft` (default): rerank so best matches come first
   - `type_mode=strict`: filter out non-matches

Supported hints (initial mapping; extend as needed):
- `city` → P31 contains `Q515`
- `neighbourhood` → P31 contains `Q123705` or `Q188509`
- `district` → P31 contains `Q1187811` or `Q13220204`

**Note:** `within_qid` checks only direct P131 membership (not recursive chain). This is an MVP.

---

## 3) Endpoints

### 3.1 `GET /wikidata/search`

Search for entities by label (language-aware), cached.

Query parameters:
- `query` (string, required)
- `lang` (string, default `bg`)
- `limit` (int, default 10, max 50)
- `refresh` (bool, default false) – bypass search cache

Optional filtering/reranking:
- `type_hint` (one of `neighbourhood|district|city`)
- `type_mode` (one of `soft|strict`, default `soft`)
- `within_qid` (string, optional) – constrain/rerank by direct P131 membership

Response fields include:
- `results`: search results with added fields:
  - `type_match`, `within_match`
  - `instance_of` (P31 qids)
  - `located_in` (P131 qids)

---

### 3.2 `GET /wikidata/entity/{qid}`

Fetch a specific entity by QID, cached, and return extracted project-relevant properties.

Query parameters:
- `lang` (default `bg`)
- `refresh` (default false) – bypass TTL cache
- `include_raw` (default false) – return the raw Wikidata entity payload

Extracted properties (for AQKG use case):
- label, description, wikipedia links
- population (P1082) + point in time when present
- area (P2046)
- elevation (P2044)
- computed population density estimate: `population / area_km2` when possible

Important: P1082 is population, not population density. Density is derived if both population and area exist.

---

## 4) cURL tests (developer testing)

Assume local base:
- `http://127.0.0.1:8000`
- and API key header `X-API-Key: dev-key-1`

### 4.1 Basic search (Bulgarian)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/wikidata/search?query=%D0%9B%D0%BE%D0%B7%D0%B5%D0%BD%D0%B5%D1%86&lang=bg&limit=10"
```

### 4.2 Search (English) – useful for debugging ambiguity
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/wikidata/search?query=Lozenets&lang=en&limit=10"
```

### 4.3 Search with `type_hint` (soft rerank; default)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/wikidata/search?query=%D0%9B%D0%BE%D0%B7%D0%B5%D0%BD%D0%B5%D1%86&lang=bg&limit=10&type_hint=neighbourhood"
```

### 4.4 Search with `type_hint` strict filtering
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/wikidata/search?query=%D0%9B%D0%BE%D0%B7%D0%B5%D0%BD%D0%B5%D1%86&lang=bg&limit=10&type_hint=neighbourhood&type_mode=strict"
```

### 4.5 Search constrained within Bulgaria (optional)
Bulgaria QID: `Q219`
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/wikidata/search?query=Lozenets&lang=en&limit=10&type_hint=neighbourhood&within_qid=Q219"
```

### 4.6 Force refresh (bypass cache)
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/wikidata/search?query=Lozenets&lang=en&limit=10&refresh=true"
```

### 4.7 Entity extraction
Use a QID returned from search (example Q4265413 from Lozenets village query):
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/wikidata/entity/Q4265413?lang=en"
```

### 4.8 Entity extraction with raw payload
```bash
curl -H "X-API-Key: dev-key-1" \
"http://127.0.0.1:8000/wikidata/entity/Q4265413?lang=en&include_raw=true"
```

---

## 5) Common issues and troubleshooting

### 5.1 Wikidata returns 403 in SUDS but curl works
Likely proxy environment variables are interfering with Python requests.

Mitigation:
- WikidataClient uses `session.trust_env = False`
- ensure you restarted uvicorn after changes
- check env vars:
  ```bash
  env | grep -i proxy
  ```

### 5.2 Type hints don’t work well for Bulgarian neighbourhood names
Wikidata classification (`P31`) varies across entities. If valid neighbourhoods are not matching:
- inspect returned `instance_of` QIDs
- extend `TYPE_HINT_INSTANCE_OF` mapping in `suds_core.services.wikidata`

### 5.3 `within_qid` strict filtering returns empty list
This is expected when:
- candidates don’t have a direct `P131` referencing the `within_qid`
- or the containment is indirect (neighbourhood → district → Sofia → Bulgaria)

Future improvement: recursive P131 chain or SPARQL `wdt:P131*`.

---

## 6) Extension ideas (future work)

### 6.1 Recursive `within_qid` (P131 chain)
Implement a transitive closure check:
- follow P131 up to N steps
- cache the ancestor set per QID
- allow `within_qid` to match any ancestor in chain

This makes `within_qid=Q219` (Bulgaria) much more effective.

### 6.2 SPARQL-based search with type constraint
Use WDQS to:
- perform entity search
- filter by `P31 / P279*` subclass logic
- filter by `P131*` containment

More accurate but more complex and can be slower/rate-limited.

### 6.3 Project-specific “neighbourhood reconcile” endpoint
Add:
- `POST /wikidata/reconcile/neighbourhoods`
Input:
- list of neighbourhood names (+ optional district)
Output:
- best QID mapping + confidence + reasoning
This would support batch enrichment of all Sofia neighbourhoods.

### 6.4 Add more relevant properties (only when needed)
Potential candidates (availability varies):
- inception/founding (P571)
- official website (P856)
- postal code (P281)
- socioeconomic signals (rare at neighbourhood level)

The entity endpoint can be extended with a query param:
- `properties=P1082,P2046,P2044,...`
to make extraction more generic.

---

## 7) Notes for AQKG (Kindergarten Planning) usage

Recommended workflow:
1) Geocode kindergarten location (Geoapify/HERE).
2) Assign neighbourhood polygon using:
   - `/spatial/lookup/neighbourhood?lat=...&lon=...&max_nearest_distance_m=2000`
3) Use neighbourhood name for Wikidata enrichment:
   - `/wikidata/search?query=<neighbourhood_name>&type_hint=neighbourhood&type_mode=soft&within_qid=Q219`
4) If multiple candidates remain, the UI should allow manual selection.
5) Fetch entity:
   - `/wikidata/entity/{qid}`
6) Use extracted values:
   - population, area, computed density, elevation
for context and interpretability (not as sole ranking inputs).