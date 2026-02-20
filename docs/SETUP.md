# Setup (Local Development)

This guide sets up SUDS locally on any computer with Docker + Python.

---

## What you get vs what requires data

There are three tiers depending on what you have access to:

**Tier 1 — repo only (no data needed)**
Anyone who clones the repo can run a fully structured database and working API.
Dataset endpoints return empty GeoJSON, but OSM metrics and weather endpoints
work immediately since they pull from external sources.

**Tier 2 — raw data files**
If you have access to the Sofia raw GIS files, place them under `data/raw/`
and run `make ingest-all` to populate the database.

**Tier 3 — full database dump**
If someone shares a `suds_full.dump` file with you, you can restore a
fully populated database in one command without any raw files.

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

## Quickstart (Tier 1 — repo only)

```bash
# 1. Copy the env file and configure it
cp .env.example .env
# Edit .env — minimum required:
#   SUDS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/suds
#   SUDS_API_KEYS=dev-key-1

# 2. Start PostGIS (schema is applied automatically from docker/db-init/)
make db-up

# 3. Install Python packages
make install-dev

# 4. Verify tables exist
docker exec -it suds-postgis psql -U postgres -d suds -c "\dt"

# 5. Start the API
make api-run
```

Test it in a new terminal:
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

The `docker/db-init/` directory contains two SQL files that Docker runs automatically
in alphabetical order the first time the container starts with a fresh volume:

- `01_postgis.sql` — enables the PostGIS and topology extensions
- `02_schema.sql` — creates all application tables and indexes

This means `make db-up` on a fresh volume gives you a fully structured database
with no extra steps required. If you already have a `suds_pgdata` volume from a
previous run, these init scripts will not re-run — use `make db-reset` first to
get a clean slate.

If the schema didn't apply (check with `docker exec -it suds-postgis psql -U postgres -d suds -c "\dt"`),
apply it manually:
```bash
docker exec -i suds-postgis psql -U postgres -d suds < docker/db-init/02_schema.sql
```

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

Then ingest in recommended order (small datasets first):

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

Verify row counts:
```bash
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM neighbourhoods;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM green_areas;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM pedestrian_network;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM streets;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM buildings;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM trees;"
docker exec -it suds-postgis psql -U postgres -d suds -c "SELECT COUNT(*) FROM pois;"
```

Then run validate and analyze:
```bash
make validate-db
make analyze-db
```

See `docs/DATA_INGESTION.md` for the full ingestion reference.

---

## Tier 3 — restore from a database dump

If you have been given a `suds_full.dump` file, you can restore a fully populated
database without needing any raw data files.

```bash
# 1. Start a fresh DB
make db-up

# 2. Restore (default looks for suds_full.dump in the repo root)
make db-restore

# Or specify a different path:
make db-restore DUMP=path/to/suds_20260220.dump

# 3. Verify
make validate-db
```

The restore will print the last few lines of pg_restore output. Some `pg_restore`
warnings about existing objects are harmless if the schema was already applied by
the init scripts — all data will still be loaded correctly.

---

## Creating a database dump (for sharing)

If you have a populated database and want to share it:

```bash
make db-dump
# Creates suds_full.dump in the repo root (gitignored)

# Or with a custom filename:
make db-dump DUMP=exports/suds_20260220.dump
```

Share the resulting `.dump` file with collaborators. It contains the full schema
and all data and can be restored with `make db-restore`.

---

## Regenerating the schema init file

If you change SQLAlchemy models and want to update `docker/db-init/02_schema.sql`
so new clones pick up the changes automatically:

```bash
# 1. Apply your model changes to the running DB
make create-tables

# 2. Regenerate the schema dump
make schema-dump

# 3. Commit it
git add docker/db-init/02_schema.sql
git commit -m "update db schema"
```

---

## Important: running scripts directly vs via `make`

All `make` targets call the venv Python automatically via `.venv/bin/python`.
If you run ingestion scripts directly with `python scripts/...`, you must
activate the venv first:

```bash
source .venv/bin/activate
python scripts/ingest/ingest_neighbourhoods.py --path "..." --truncate
```

Using `make ingest-*` targets avoids this entirely.

---

## Common issues

**`connection refused` when creating tables**
The DB is not ready yet. Wait ~10s after `make db-up`, or check:
```bash
docker logs suds-postgis | tail -20
```

**`\dt` shows only PostGIS system tables (no application tables)**
The init scripts didn't run — either the volume already existed, or the container
started before PostGIS finished initialising. Apply the schema manually:
```bash
docker exec -i suds-postgis psql -U postgres -d suds < docker/db-init/02_schema.sql
```

**`ModuleNotFoundError: No module named 'suds_core'`**
You're calling `python scripts/...` without the venv active. Either:
```bash
source .venv/bin/activate && python scripts/ingest/ingest_green_areas.py ...
```
Or use the make target: `make ingest-green-areas`

**Port 5432 already in use**
A local Postgres instance is running. Change the port mapping in `docker/compose.yml`
from `5432:5432` to `5433:5432` and update `.env`:
```env
SUDS_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/suds
```

**API key errors (401)**
Ensure `.env` has a real value (not the placeholder `changeme`):
```env
SUDS_API_KEYS=dev-key-1
```

**Resetting everything (dangerous — deletes all data)**
```bash
make db-reset    # stops container, removes volume, starts fresh
# schema is reapplied automatically from docker/db-init/
# then re-ingest or restore from dump as needed
```