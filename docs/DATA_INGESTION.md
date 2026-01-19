# Data Ingestion (PostGIS)

This guide explains how to ingest the Sofia datasets into PostGIS.
After ingestion, users query everything via the API and do not need raw files locally.

---

## Prerequisites

- Complete `docs/SETUP.md` first:
  - `make db-up`
  - `make install-dev`
  - `make create-tables`

- Your `.env` must point to your running DB:
  ```env
  SUDS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/suds
  ```

---

## Raw data location

Recommended local layout (gitignored):
```
data/
  raw/
    Buildings/
    Green areas/
    Neighbourhoods/
    Pedestrian_network_enriched/
    POIs/
    Street network enriched/
    Vegetation/
```

Do not commit raw data. Add to `.gitignore`:
```gitignore
data/
```

---

## Inspect a dataset before ingesting (required)

Before ingesting any dataset, inspect it to confirm:
- CRS
- geometry type
- column names
- layer names (for GeoPackage)

Examples:

### Neighbourhoods (GeoJSON)
```bash
python scripts/ops/inspect_sources.py \
  --path "data/raw/Neighbourhoods/ge_26_sofpr_20200616.geojson"
```

### Trees (GPKG; may have multiple layers)
```bash
python scripts/ops/inspect_sources.py \
  --path "data/raw/Vegetation/sofia_trees_municipality_dtm_city.gpkg"
```

### Pedestrian network (GPKG)
```bash
python scripts/ops/inspect_sources.py \
  --path "data/raw/Pedestrian_network_enriched/pedestrian_network_26_2020_eniched.gpkg"
```

---

## Ingestion order (recommended)

1) Neighbourhoods
2) Green areas
3) Pedestrian network
4) Streets
5) Buildings (large)
6) Trees (very large)
7) POIs

Why this order:
- You validate end-to-end quickly with smaller layers.
- Big ingests (buildings/trees) happen after your pipeline is proven.

---

## Ingest commands

All scripts support `--truncate` to delete existing rows before inserting.

### 1) Neighbourhoods
```bash
python scripts/ingest/ingest_neighbourhoods.py \
  --path "data/raw/Neighbourhoods/ge_26_sofpr_20200616.geojson" \
  --truncate
```

### 2) Green areas
```bash
python scripts/ingest/ingest_green_areas.py \
  --path "data/raw/Green areas/green_areas_26_sofp_20200518.geojson" \
  --truncate
```

### 3) Pedestrian network (choose a layer)
List layers first via `inspect_sources.py`, then ingest:

```bash
python scripts/ingest/ingest_pedestrian_network.py \
  --path "data/raw/Pedestrian_network_enriched/pedestrian_network_26_2020_eniched.gpkg" \
  --layer "pedestrian_with_adj_pois" \
  --truncate
```

(Use the exact layer name from inspection output.)

### 4) Streets
```bash
python scripts/ingest/ingest_streets.py \
  --path "data/raw/Street network enriched/street_network_with_limit_and_lanes.geojson" \
  --truncate
```

Optional: store a stable source id column (if present in file):
```bash
python scripts/ingest/ingest_streets.py \
  --path "data/raw/Street network enriched/street_network_with_limit_and_lanes.geojson" \
  --truncate \
  --source-id-col "NewSegId"
```

### 5) Buildings (large; chunked)
```bash
python scripts/ingest/ingest_buildings.py \
  --path "data/raw/Buildings/buildings_so_2025_enriched_20250916.gpkg" \
  --truncate \
  --chunk-size 50000
```

Optional:
```bash
python scripts/ingest/ingest_buildings.py \
  --path "data/raw/Buildings/buildings_so_2025_enriched_20250916.gpkg" \
  --truncate \
  --chunk-size 50000 \
  --source-id-col "cadnum"
```

### 6) Trees (very large; chunked; slowest)
```bash
python scripts/ingest/ingest_trees.py \
  --path "data/raw/Vegetation/sofia_trees_municipality_dtm_city.gpkg" \
  --truncate \
  --chunk-size 50000
```

Notes:
- Trees are stored as POINT in EPSG:4326.
- Z/elevation attributes remain in `props` (JSONB).

### 7) POIs
```bash
python scripts/ingest/ingest_pois.py \
  --path "data/raw/POIs/pois/all_pos.shp" \
  --truncate
```

Optional:
```bash
python scripts/ingest/ingest_pois.py \
  --path "data/raw/POIs/pois/all_pos.shp" \
  --truncate \
  --source-id-col "guid"
```

---

## Verify ingestion

Check counts quickly:

```bash
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM neighbourhoods;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM green_areas;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM pedestrian_network;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM streets;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM buildings;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM trees;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM pois;"
```

Run full validation (SRID/extent/invalid geometries, etc.):

```bash
make validate-db
```

Run analyze for performance:

```bash
make analyze-db
```

---

## Common ingestion issues

### 1) JSONB “NaN” errors
Some source datasets contain NaN/Infinity values.
Your ingestion utilities sanitize values before inserting into JSONB. If you see this again, confirm you are using `gdf_to_mappings()` and the current `sanitize_json_value()`.

### 2) CRS missing
If `inspect_sources.py` shows CRS is missing, ingestion will fail.
Fix the source file CRS (preferred) or add an override in ingestion (not currently implemented by default).

### 3) Memory issues during large ingests
Use chunked scripts (`trees`, `buildings`) and keep chunk size reasonable (e.g., 50k).

---

## After ingestion: API usage

Once data is ingested, start the API:

```bash
make api-run
```

Then query e.g.:

```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/streets?bbox=23.30,42.65,23.36,42.71&limit=2000&simplify_m=5"
```

---

## Notes about GATE stations/measurements
GATE endpoints may require API keys or may be temporarily unavailable from some networks.
The system currently supports point-based enrichment without stations:
- `/osm/metrics`
- `/weather/daily`
- `/enrich/point`