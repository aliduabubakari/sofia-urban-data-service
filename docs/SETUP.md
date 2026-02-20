# Setup (Local Development)

This guide sets up SUDS locally on any computer with Docker + Python.

---

## What you get vs what requires data

There are three tiers depending on what you have access to:

| Tier | What you need | What you get |
|------|--------------|--------------|
| 1 — repo only | Just the repo | Working API, empty dataset endpoints, OSM metrics + weather fully functional |
| 2 — raw data files | Repo + Sofia GIS files | Fully populated API via `make ingest-all` |
| 3 — database dump | Repo + `suds_full.dump` | Fully populated API via `make db-restore`, no raw files needed |

---

## Prerequisites

1. **Docker Desktop** — install and ensure it is running:
   ```bash
   docker --version
   docker compose version
   ```

2. **Python 3.10+**:
   ```bash
   python3 --version
   ```

---

## Environment file

Copy and configure your local env file before doing anything else:

```bash
cp .env.example .env
```

Minimum required values in `.env`:
```env
SUDS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/suds
SUDS_API_KEYS=dev-key-1
```

Do not commit `.env`. It is gitignored.

---

## Quickstart (Tier 1 — repo only)

Four commands, in order:

```bash
make db-up          # start PostGIS, wait until ready
make install-dev    # create .venv, install all packages
make create-tables  # apply schema (idempotent — safe to re-run)
make api-run        # start API on http://127.0.0.1:8000
```

Test in a new terminal:
```bash
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/health
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/datasets
```

Swagger UI: http://127.0.0.1:8000/docs

> **Apple Silicon note:** The warning `requested image's platform (linux/amd64) does not
> match detected host platform (linux/arm64/v8)` is harmless — PostGIS works correctly
> under Docker's emulation.

---

## How the database schema is applied

`docker/db-init/` contains two SQL files Docker runs automatically in alphabetical
order the first time a container starts with a fresh volume:

- `01_postgis.sql` — enables PostGIS and topology extensions
- `02_schema.sql` — creates all application tables and indexes

`make db-up` waits until PostGIS is genuinely ready before returning, so init
scripts have time to complete. `make create-tables` then applies the schema
idempotently via SQLAlchemy (`checkfirst=True`), so it is safe to run even if
the init scripts already created the tables.

> **Important:** Init scripts only run on a **fresh volume**. If you already have
> a `suds_pgdata` volume from a previous run, use `make db-reset` first to get a
> clean slate — this removes the volume and recreates it.

---

## Tier 2 — populating with raw data

Raw data files are gitignored and must be obtained separately.
Place them under `data/raw/` following this layout:

```
data/raw/
  Buildings/
  Green_areas/
  Neighbourhoods/
  Pedestrian_network_enriched/
  POIs/pois/
  Street_network_enriched/
  Vegetation/
```

Ingest in recommended order (small datasets first):

```bash
make ingest-neighbourhoods   # ~564 rows,    fast
make ingest-green-areas      # ~65k rows,    fast
make ingest-pedestrian       # ~403 rows,    fast
make ingest-streets          # ~98k rows,    fast
make ingest-buildings        # ~266k rows,   a few minutes
make ingest-trees            # ~637k rows,   slowest
make ingest-pois             # ~28k rows,    fast
```

Or all at once:
```bash
make ingest-all
```

Verify row counts after ingestion:
```bash
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM neighbourhoods;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM green_areas;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM pedestrian_network;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM streets;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM buildings;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM trees;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM pois;"
```

Then validate and optimise for query performance:
```bash
make validate-db
make analyze-db
```

See `docs/DATA_INGESTION.md` for the full ingestion reference.

---

## Tier 3 — restore from a database dump

If you have been given a `suds_full.dump` file:

```bash
make db-up
make db-restore
# or with a custom path:
make db-restore DUMP=path/to/suds_20260220.dump

make validate-db
```

The restore prints the last few lines of pg_restore output. Any warnings about
existing objects are harmless if the schema was already applied by the init
scripts — all data will be loaded correctly.

---

## Creating a database dump (for sharing)

If you have a populated database and want to share it:

```bash
make db-dump
# creates suds_full.dump in the repo root (gitignored)

# or with a custom filename:
make db-dump DUMP=exports/suds_20260220.dump
```

Dump files can be large (buildings + trees = ~1M rows). Share via a file transfer
service rather than git.

---

## Regenerating the schema init file

If you change SQLAlchemy models, update `docker/db-init/02_schema.sql` so new
clones pick up the changes automatically on first boot:

```bash
make create-tables   # apply your model changes to the running DB
make schema-dump     # regenerate 02_schema.sql
git add docker/db-init/02_schema.sql
git commit -m "update db schema"
```

---

## Important: running scripts directly vs via `make`

All `make` targets call `.venv/bin/python` automatically — no activation needed.

If you run ingestion scripts directly with `python scripts/...`, activate the
venv first or Python won't find `suds_core`:

```bash
source .venv/bin/activate
python scripts/ingest/ingest_neighbourhoods.py --path "..." --truncate
```

Using `make ingest-*` targets avoids this entirely.

---

## Common issues

**`\dt` shows only PostGIS system tables after `make db-up`**
The init scripts may not have finished before you checked. Run `make create-tables`
which applies the schema idempotently regardless:
```bash
make create-tables
docker exec -it suds-postgis psql -U postgres -d suds -c "\dt"
```

**`connection refused` errors**
PostGIS is not ready yet. `make db-up` polls `pg_isready` and should handle this,
but if you see it check the container logs:
```bash
make db-logs
```

**`ModuleNotFoundError: No module named 'suds_core'`**
You are calling `python scripts/...` without the venv active:
```bash
source .venv/bin/activate
# or just use the make target:
make ingest-green-areas
```

**Port 8000 already in use**
A previous `make api-run` is still running. Kill it:
```bash
lsof -ti :8000 | xargs kill -9
make api-run
```

**Port 5432 already in use**
A local Postgres instance is running. Change the port mapping in
`docker/compose.yml` from `5432:5432` to `5433:5432` and update `.env`:
```env
SUDS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/suds
```

**API key errors (401)**
Ensure `.env` has a real value (not the placeholder `changeme`):
```env
SUDS_API_KEYS=dev-key-1
```

---

## Resetting everything

```bash
make db-reset        # removes volume + restarts DB (init scripts re-run)
make create-tables   # re-apply schema idempotently
# then re-ingest or restore from dump
make ingest-all
# or
make db-restore
```