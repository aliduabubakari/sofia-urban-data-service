# suds-api

FastAPI service for the Sofia Urban Data Service (SUDS).

This package exposes HTTP endpoints over the PostGIS-backed datasets stored by `suds-core`.

## Local development

### 1 Start PostGIS (Docker)
From repo root:

```bash
docker compose -f docker/compose.yml up -d db