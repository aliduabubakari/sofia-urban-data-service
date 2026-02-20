SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON := python3
VENV := .venv
PIP := $(VENV)/bin/python -m pip
UVICORN := $(VENV)/bin/python -m uvicorn

# Use the venv Python directly for all script calls.
# This avoids needing to `source .venv/bin/activate` manually.
RUN := $(VENV)/bin/python

COMPOSE := docker compose -f docker/compose.yml

# Path for pg_dump/pg_restore data dump (override with DUMP=yourfile.dump)
DUMP ?= suds_full.dump

.PHONY: help
help:
	@echo "SUDS - common targets"
	@echo ""
	@echo "Bootstrap:"
	@echo "  make venv              Create virtualenv"
	@echo "  make install-dev       Install suds-core + suds-api in editable mode (+ dev extras)"
	@echo ""
	@echo "Database:"
	@echo "  make db-up             Start PostGIS"
	@echo "  make db-down           Stop services"
	@echo "  make db-reset          Stop + remove volumes (DANGEROUS: deletes DB data)"
	@echo "  make db-logs           Tail DB logs"
	@echo "  make create-tables     Create tables (SQLAlchemy create_all)"
	@echo "  make validate-db       Run DB validation checks"
	@echo "  make analyze-db        VACUUM/ANALYZE"
	@echo "  make schema-dump       Regenerate docker/db-init/02_schema.sql from running DB"
	@echo "  make db-dump           Dump full DB to DUMP file (default: suds_full.dump)"
	@echo "  make db-restore        Restore full DB from DUMP file (default: suds_full.dump)"
	@echo "                         Override: make db-restore DUMP=path/to/file.dump"
	@echo ""
	@echo "Ingestion:"
	@echo "  make ingest-all        Ingest all datasets in recommended order"
	@echo "  make ingest-neighbourhoods"
	@echo "  make ingest-green-areas"
	@echo "  make ingest-pedestrian"
	@echo "  make ingest-streets"
	@echo "  make ingest-buildings"
	@echo "  make ingest-trees"
	@echo "  make ingest-pois"
	@echo ""
	@echo "API:"
	@echo "  make api-run           Run FastAPI locally (reload)"
	@echo ""
	@echo "UI:"
	@echo "  make install-ui        Install suds-ui in editable mode"
	@echo "  make ui-run            Run Streamlit UI"
	@echo ""
	@echo "Ops:"
	@echo "  make purge-cache       Remove old cache rows"
	@echo ""

.PHONY: venv
venv:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(PIP) install -U pip

.PHONY: install-core
install-core: venv
	@$(PIP) install -e packages/suds-core

.PHONY: install-api
install-api: venv
	@$(PIP) install -e packages/suds-api

.PHONY: install-dev
install-dev: venv
	@$(PIP) install -e "packages/suds-core[dev]"
	@$(PIP) install -e "packages/suds-api[dev]"

.PHONY: install-ui
install-ui: venv
	@$(PIP) install -e packages/suds-ui

# -----------------------
# Database
# -----------------------
.PHONY: db-up
db-up:
	@$(COMPOSE) up -d db
	@echo "Waiting for PostGIS to be ready..."
	@until docker exec suds-postgis pg_isready -U postgres -d suds -q; do sleep 1; done
	@echo "PostGIS is ready."

.PHONY: db-down
db-down:
	@$(COMPOSE) down

.PHONY: db-reset
db-reset:
	@$(COMPOSE) down -v
	@$(COMPOSE) up -d db

.PHONY: db-logs
db-logs:
	@docker logs -f suds-postgis

.PHONY: create-tables
create-tables: install-core
	@$(RUN) scripts/ops/create_tables.py

.PHONY: validate-db
validate-db: install-core
	@$(RUN) scripts/ops/validate_db.py

.PHONY: analyze-db
analyze-db: install-core
	@$(RUN) scripts/ops/analyze_db.py

.PHONY: purge-cache
purge-cache: install-core
	@$(RUN) scripts/ops/purge_cache.py

# Regenerate the schema-only init file from the running DB.
# The topology schema is excluded because it is created by 01_postgis.sql already.
# Run this after any model changes and commit the result.
.PHONY: schema-dump
schema-dump:
	@echo "Dumping schema from running DB -> docker/db-init/02_schema.sql ..."
	@docker exec suds-postgis pg_dump \
		-U postgres \
		-d suds \
		--schema-only \
		--no-owner \
		--no-acl \
		--exclude-schema=topology \
		> docker/db-init/02_schema.sql
	@echo "Done. Commit docker/db-init/02_schema.sql to git."

# Dump the full database (schema + data) to a binary .dump file.
# Share this file with collaborators who need a fully populated DB.
# Usage:
#   make db-dump
#   make db-dump DUMP=exports/suds_20260220.dump
.PHONY: db-dump
db-dump:
	@echo "Dumping full DB to $(DUMP) ..."
	@docker exec suds-postgis pg_dump \
		-U postgres \
		-d suds \
		--format=custom \
		--no-owner \
		--no-acl \
		-f /tmp/suds_dump.dump
	@docker cp suds-postgis:/tmp/suds_dump.dump $(DUMP)
	@docker exec suds-postgis rm /tmp/suds_dump.dump
	@echo "Done: $(DUMP)"

# Restore the full database from a binary .dump file.
# Requires the DB container to be running (make db-up).
# Usage:
#   make db-restore
#   make db-restore DUMP=exports/suds_20260220.dump
.PHONY: db-restore
db-restore:
	@if [ ! -f "$(DUMP)" ]; then \
		echo "ERROR: dump file not found: $(DUMP)"; \
		echo "Usage: make db-restore DUMP=path/to/file.dump"; \
		exit 1; \
	fi
	@echo "Restoring DB from $(DUMP) ..."
	@docker cp $(DUMP) suds-postgis:/tmp/suds_restore.dump
	@docker exec suds-postgis pg_restore \
		-U postgres \
		-d suds \
		--no-owner \
		--no-acl \
		-v \
		/tmp/suds_restore.dump 2>&1 | tail -5
	@docker exec suds-postgis rm /tmp/suds_restore.dump
	@echo "Done. Run 'make validate-db' to verify."

# -----------------------
# Ingestion
# Note: raw data paths are gitignored and must exist locally.
# See docs/DATA_INGESTION.md for the full guide.
# -----------------------

.PHONY: ingest-neighbourhoods
ingest-neighbourhoods: install-dev
	@$(RUN) scripts/ingest/ingest_neighbourhoods.py \
		--path "data/raw/Neighbourhoods/ge_26_sofpr_20200616.geojson" \
		--truncate

.PHONY: ingest-green-areas
ingest-green-areas: install-dev
	@$(RUN) scripts/ingest/ingest_green_areas.py \
		--path "data/raw/Green_areas/green_areas_26_sofp_20200518.geojson" \
		--truncate

.PHONY: ingest-pedestrian
ingest-pedestrian: install-dev
	@$(RUN) scripts/ingest/ingest_pedestrian_network.py \
		--path "data/raw/Pedestrian_network_enriched/pedestrian_network_26_2020_eniched.gpkg" \
		--layer "pedestrian_with_adj_pois" \
		--truncate

.PHONY: ingest-streets
ingest-streets: install-dev
	@$(RUN) scripts/ingest/ingest_streets.py \
		--path "data/raw/Street_network_enriched/street_network_with_limit_and_lanes.geojson" \
		--truncate \
		--source-id-col "NewSegId"

.PHONY: ingest-buildings
ingest-buildings: install-dev
	@$(RUN) scripts/ingest/ingest_buildings.py \
		--path "data/raw/Buildings/buildings_so_2025_enriched_20250916.gpkg" \
		--truncate \
		--chunk-size 50000 \
		--source-id-col "cadnum"

.PHONY: ingest-trees
ingest-trees: install-dev
	@$(RUN) scripts/ingest/ingest_trees.py \
		--path "data/raw/Vegetation/sofia_trees_municipality_dtm_city.gpkg" \
		--truncate \
		--chunk-size 50000

.PHONY: ingest-pois
ingest-pois: install-dev
	@$(RUN) scripts/ingest/ingest_pois.py \
		--path "data/raw/POIs/pois/all_pos.shp" \
		--truncate \
		--source-id-col "guid"

.PHONY: ingest-all
ingest-all: ingest-neighbourhoods ingest-green-areas ingest-pedestrian ingest-streets ingest-buildings ingest-trees ingest-pois
	@echo "All datasets ingested."

# -----------------------
# API
# -----------------------
.PHONY: api-run
api-run: install-dev
	@$(UVICORN) suds_api.main:app --reload --port 8000

# -----------------------
# UI
# -----------------------
.PHONY: ui-run
ui-run: install-ui
	@$(VENV)/bin/python -m streamlit run packages/suds-ui/src/suds_ui/app.py

citylab-stations:
	$(RUN) scripts/ingest/ingest_citylab_stations.py

citylab-backfill-2024:
	$(RUN) scripts/ingest/backfill_citylab_airquality_2024_monthly.py