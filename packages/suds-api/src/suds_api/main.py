from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from suds_api.routers import datasets, context, stations, osm, weather
from suds_api.routers import datasets, context, osm, weather, enrich


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sofia Urban Data Service (SUDS)",
        version="0.1.0",
        default_response_class=ORJSONResponse,
    )

    # Compress big GeoJSON responses
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
    app.include_router(context.router, prefix="/context", tags=["context"])
    app.include_router(stations.router, prefix="/stations", tags=["stations"])
    app.include_router(osm.router, prefix="/osm", tags=["osm"])
    app.include_router(weather.router, prefix="/weather", tags=["weather"])
    app.include_router(enrich.router, prefix="/enrich", tags=["enrich"])

    return app


app = create_app()