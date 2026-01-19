# Setup (Local Development)

This guide sets up SUDS locally on any computer with Docker + Python.
It covers:
- PostGIS (Docker)
- Python virtualenv + editable installs (suds-core + suds-api)
- Creating tables
- Running the API
- Verifying the system

---

## Prerequisites

1) **Docker Desktop**
- Install Docker Desktop and ensure it is running.
- Verify:
  ```bash
  docker --version
  docker compose version
  ```

2) **Python 3.10+**
- Verify:
  ```bash
  python3 --version
  ```

---

## Repo bootstrap

From repo root:

1) Create your local environment file:
```bash
cp .env.example .env
```

2) Edit `.env` (minimum required):
```env
SUDS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/suds
SUDS_API_KEYS=dev-key-1
```

Notes:
- Do **not** commit `.env`.
- `SUDS_API_KEYS` is comma-separated; any value is fine for local dev.

---

## Start PostGIS

Start the DB:
```bash
make db-up
```

Check it is healthy:
```bash
docker ps
docker logs -f suds-postgis
```

Optional: check PostGIS version:
```bash
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT PostGIS_Version();"
```

---

## Create Python environment + install packages

Install everything (editable + dev tools):
```bash
make install-dev
```

This creates `.venv/` and installs:
- `suds-core` (models, services, ingestion, connectors)
- `suds-api` (FastAPI app)

Sanity check:
```bash
. .venv/bin/activate
python -c "import suds_core, suds_api; print('ok', suds_core.__version__)"
```

---

## Create tables

Create the DB tables:
```bash
make create-tables
```

Validate DB (counts and geometry checks; should run even before ingestion):
```bash
make validate-db
```

---

## Run the API

Run FastAPI locally:
```bash
make api-run
```

Then test (new terminal):
```bash
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/health
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/datasets
```

Swagger UI:
- http://127.0.0.1:8000/docs

---

## Optional: Analyze DB (performance stats)

After large ingests, run:
```bash
make analyze-db
```

Notes:
- This runs VACUUM/ANALYZE and can take time.
- Docker DB service should have `shm_size` configured (e.g., `1gb`) to avoid shared memory errors during VACUUM.

---

## Cache maintenance (optional)

Purge old cached rows (OSM/weather point caches):
```bash
make purge-cache
```

---

## Common issues

### 1) `connection refused` when creating tables
- DB container is not running.
- Run:
  ```bash
  make db-up
  ```

### 2) Port 5432 already in use
- You may have local Postgres running.
- Either stop it or change Docker port mapping in `docker/compose.yml` to `5433:5432` and update `.env`.

### 3) API key errors (401)
- Ensure `.env` has:
  ```env
  SUDS_API_KEYS=dev-key-1
  ```
- Use the header:
  ```bash
  curl -H "X-API-Key: dev-key-1" ...
  ```

### 4) “No space left on device” during VACUUM
- Increase docker PostGIS `shm_size` in compose and restart DB:
  ```bash
  make db-down
  make db-up
  ```
- Or run ANALYZE only (manual fallback):
  ```bash
  docker exec -it suds-postgis psql -U postgres -d suds -c "ANALYZE buildings;"
  ```

---

## Resetting everything (dangerous)

This deletes the DB volume (all ingested data):
```bash
make db-reset
make create-tables
```