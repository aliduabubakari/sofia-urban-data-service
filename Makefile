SHELL := /bin/bash
.DEFAULT_GOAL := help

PYTHON := python3
VENV := .venv
PIP := $(VENV)/bin/python -m pip
UVICORN := $(VENV)/bin/python -m uvicorn

COMPOSE := docker compose -f docker/compose.yml

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
	@echo "  make analyze-db        VACUUM/ANALYZE (needs shm_size set in compose)"
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
	@$(VENV)/bin/python scripts/ops/create_tables.py

.PHONY: validate-db
validate-db: install-core
	@$(VENV)/bin/python scripts/ops/validate_db.py

.PHONY: analyze-db
analyze-db: install-core
	@$(VENV)/bin/python scripts/ops/analyze_db.py

.PHONY: purge-cache
purge-cache: install-core
	@$(VENV)/bin/python scripts/ops/purge_cache.py

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