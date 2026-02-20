from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.services.geocoding import geocode_reverse_cached, geocode_search_batch, geocode_search_cached

router = APIRouter()


class BatchSearchRequest(BaseModel):
    queries: list[str] = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=20)
    lang: str = Field(default="bg")
    refresh: bool = Field(default=False)


@router.get("/search")
def geocode_search(
    text: str = Query(..., min_length=1),
    limit: int = Query(default=5, ge=1, le=20),
    lang: str = Query(default="bg"),
    refresh: bool = Query(default=False),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    try:
        return geocode_search_cached(session, text=text, limit=limit, lang=lang, force_refresh=refresh)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/reverse")
def geocode_reverse(
    lat: float = Query(...),
    lon: float = Query(...),
    limit: int = Query(default=1, ge=1, le=5),
    lang: str = Query(default="bg"),
    refresh: bool = Query(default=False),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    try:
        return geocode_reverse_cached(session, lat=lat, lon=lon, limit=limit, lang=lang, force_refresh=refresh)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/search/batch")
def geocode_search_batch_endpoint(
    body: BatchSearchRequest,
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    try:
        return geocode_search_batch(
            session,
            queries=body.queries,
            limit=body.limit,
            lang=body.lang,
            force_refresh=body.refresh,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))