<div align="center">

# Sofia Urban Data Service (SUDS)

**A spatial data API for urban analysis of Sofia, Bulgaria.**

SUDS ingests and serves high-resolution GIS datasets — buildings, streets, trees,
green areas, pedestrian networks, points of interest, and neighbourhoods — through
a unified REST API backed by PostGIS. It also integrates live OpenStreetMap metrics
and historical weather data for point-based urban enrichment.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![PostGIS](https://img.shields.io/badge/PostGIS-16--3.4-blue.svg)](https://postgis.net/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## What is this?

SUDS is a local spatial data service designed for urban researchers, planners, and
developers working with Sofia city data. It provides:

- A **PostGIS database** storing 7 spatial datasets covering the entire Sofia municipality
- A **FastAPI REST API** returning GeoJSON for map rendering, spatial queries, and analysis
- **Built-in caching** for external data sources (OpenStreetMap Overpass, Open-Meteo weather)
- A **combined enrichment endpoint** that returns OSM metrics, weather, and spatial features
  for any point in a single request

---

## Datasets

| Dataset | Type | Rows | Description |
|---------|------|------|-------------|
| Buildings | Polygon | ~266k | Cadastral building footprints with address, function, floor count, year built |
| Green Areas | Polygon | ~65k | Parks, gardens, and urban green spaces |
| Neighbourhoods | Polygon | ~564 | Administrative districts and planning zones |
| Streets | LineString | ~98k | Vehicle road network with speed limits and lane counts |
| Pedestrian Network | LineString | ~403 | Walkable network with slope, width, and travel time |
| Trees | Point | ~637k | Individual urban trees with height, crown diameter, and 3D model metadata |
| POIs | Point | ~28k | Points of interest grouped by category and sub-category |

All datasets cover **Sofia, Bulgaria** and are stored in **EPSG:4326** (WGS84).

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Client / curl                     │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP + X-API-Key
┌──────────────────────▼──────────────────────────────┐
│              FastAPI  (suds-api)                     │
│   /datasets/*   /osm/metrics   /weather/daily        │
│   /enrich/point   /health   /datasets                │
└──────┬───────────────┬──────────────────────────────┘
       │               │
┌──────▼──────┐  ┌─────▼──────────────────────────────┐
│   PostGIS   │  │  External APIs (cached in PostGIS)  │
│  (Docker)   │  │  - Overpass (OSM)                   │
│  suds-core  │  │  - Open-Meteo (weather)             │
└─────────────┘  └────────────────────────────────────┘
```

---

## Getting started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (running)
- Python 3.10+
- Git

### 1. Clone the repo

```bash
git clone https://github.com/aliduabubakari/sofia-urban-data-service.git
cd sofia-urban-data-service
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and set at minimum:
```env
SUDS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/suds
SUDS_API_KEYS=dev-key-1
```

### 3. Start the database

```bash
make db-up
```

This starts PostGIS in Docker, waits until it is ready, and automatically applies
the database schema from `docker/db-init/`. No manual SQL steps required.

### 4. Install Python packages

```bash
make install-dev
```

Creates `.venv/` and installs `suds-core` and `suds-api` in editable mode.

### 5. Apply schema

```bash
make create-tables
```

Idempotent — safe to re-run at any time.

### 6. Start the API

```bash
make api-run
```

The API is now running at **http://127.0.0.1:8000**.

---

## Verify it works

In a new terminal:

```bash
# Health check
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/health

# List datasets
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/datasets
```

**Expected responses:**
```json
{"status":"ok"}
{"datasets":["buildings","green_areas","neighbourhoods","pedestrian_network","pois","streets","trees"]}
```

Browse the interactive API docs at **http://127.0.0.1:8000/docs**.

---

## Querying data

All dataset endpoints return **GeoJSON FeatureCollections**. Authentication is via
the `X-API-Key` header.

### Bounding box query

```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/streets?bbox=23.30,42.65,23.36,42.71&limit=100&simplify_m=5"
```

### Radius query

```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/datasets/green_areas?lat=42.6970&lon=23.3220&radius_m=300&limit=50"
```

### OSM metrics for a point

```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/osm/metrics?lat=42.6970&lon=23.3220&radius_m=300"
```

### Historical weather

```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/weather/daily?lat=42.6970&lon=23.3220&start=2024-08-01&end=2024-08-07"
```

### Combined enrichment (all-in-one)

```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/enrich/point?lat=42.6970&lon=23.3220&radius_m=300&start=2024-08-01&end=2024-08-07&datasets=streets,pois,green_areas&mode=both&limit=500&simplify_m=5"
```

### Common query parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `bbox` | Bounding box `minLon,minLat,maxLon,maxLat` | `23.30,42.65,23.36,42.71` |
| `lat` / `lon` | Center point for radius queries | `42.6970` / `23.3220` |
| `radius_m` | Search radius in meters | `300` |
| `limit` | Max features to return | `1000` |
| `simplify_m` | Geometry simplification tolerance (meters) | `5` |

> **Test coordinates (central Sofia):** `lat=42.6970`, `lon=23.3220`
> 
> Use https://boundingbox.klokantech.com/ to find bbox values for any area.

---

## Populating with data

The API works out of the box with empty datasets. To populate it you have two options:

### Option A — restore from a database dump

If you have been given a `suds_full.dump` file, place it in the repo root and run:

```bash
make db-restore
# or with a custom path:
make db-restore DUMP=path/to/suds_20260220.dump
```

Then verify:
```bash
make validate-db
```

### Option B — ingest from raw GIS files

If you have the raw Sofia GIS files, place them under `data/raw/` and run:

```bash
make ingest-all
```

Or dataset by dataset:
```bash
make ingest-neighbourhoods
make ingest-green-areas
make ingest-pedestrian
make ingest-streets
make ingest-buildings    # ~266k rows, chunked
make ingest-trees        # ~637k rows, slowest
make ingest-pois
```

See [docs/DATA_INGESTION.md](docs/DATA_INGESTION.md) for the full ingestion reference
including inspection commands and troubleshooting.

---

## Project structure

```
sofia-urban-data-service/
├── docker/
│   ├── compose.yml              # PostGIS service
│   └── db-init/
│       ├── 01_postgis.sql       # enables PostGIS extensions
│       └── 02_schema.sql        # all application tables and indexes
├── packages/
│   ├── suds-core/               # models, services, ingestion utilities
│   ├── suds-api/                # FastAPI application and routers
│   └── suds-ui/                 # Streamlit UI (optional)
├── scripts/
│   ├── ingest/                  # per-dataset ingestion scripts
│   └── ops/                     # create-tables, validate, analyze, inspect
├── docs/
│   ├── SETUP.md                 # full setup guide
│   ├── DATA_INGESTION.md        # ingestion reference
│   ├── API.md                   # API reference
│   └── EXAMPLES.md              # curl examples for all endpoints
├── data/raw/                    # gitignored — place raw GIS files here
├── .env.example                 # copy to .env and configure
└── Makefile                     # all common workflows
```

---

## Make targets reference

```
make db-up             Start PostGIS (waits until ready)
make db-down           Stop services
make db-reset          Wipe DB volume and restart (destructive)
make install-dev       Create venv + install all packages
make create-tables     Apply schema (idempotent)
make validate-db       Run geometry and SRID validation checks
make analyze-db        VACUUM/ANALYZE for query performance
make schema-dump       Regenerate docker/db-init/02_schema.sql
make db-dump           Dump full DB to suds_full.dump
make db-restore        Restore DB from suds_full.dump
make ingest-all        Ingest all datasets
make api-run           Start FastAPI on port 8000
make ui-run            Start Streamlit UI
```

---

## Documentation

| Doc | Description |
|-----|-------------|
| [docs/SETUP.md](docs/SETUP.md) | Full setup guide including all three data tiers |
| [docs/DATA_INGESTION.md](docs/DATA_INGESTION.md) | Ingestion commands, inspection, and troubleshooting |
| [docs/API.md](docs/API.md) | API endpoint reference |
| [docs/EXAMPLES.md](docs/EXAMPLES.md) | curl examples for every endpoint |
| http://127.0.0.1:8000/docs | Interactive Swagger UI (when API is running) |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'suds_core'` when running scripts directly**
Activate the venv first: `source .venv/bin/activate`, or use `make ingest-*` targets
which handle this automatically.

**`\dt` shows no application tables after `make db-up`**
Run `make create-tables` — it applies the schema idempotently regardless of init
script state.

**Port 8000 already in use**
Kill the existing process: `lsof -ti :8000 | xargs kill -9`

**Port 5432 already in use**
Change the port in `docker/compose.yml` to `5433:5432` and update `.env` accordingly.

For a full list of common issues and fixes see [docs/SETUP.md](docs/SETUP.md).

---

## License

MIT — see [LICENSE](LICENSE).