from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import ORJSONResponse
from suds_api.routers import airquality
from suds_api.routers import context, datasets, enrich, osm, stations, weather
from suds_api.routers import geocode
from suds_api.routers import spatial
from suds_api.routers import wikidata

def create_app() -> FastAPI:
    app = FastAPI(
        title="Sofia Urban Data Service (SUDS)",
        version="0.1.0",
        default_response_class=ORJSONResponse,
    )

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
    app.include_router(airquality.router, prefix="/airquality", tags=["airquality"])
    app.include_router(geocode.router, prefix="/geocode", tags=["geocode"])
    app.include_router(spatial.router, prefix="/spatial", tags=["spatial"])
    app.include_router(wikidata.router, prefix="/wikidata", tags=["wikidata"])

    return app


app = create_app()