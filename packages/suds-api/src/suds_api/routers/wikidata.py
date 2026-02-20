from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from suds_api.deps import get_db_session, require_api_key
from suds_core.services.wikidata import (
    extract_kindergarten_relevant_properties,
    wikidata_entity_cached,
    wikidata_search_cached,
    wikidata_search_typed,
)

router = APIRouter()


@router.get("/search")
def wikidata_search(
    query: str = Query(..., min_length=1),
    lang: str = Query(default="bg"),
    limit: int = Query(default=10, ge=1, le=50),
    refresh: bool = Query(default=False),

    type_hint: str | None = Query(default=None, description="Optional: neighbourhood|district|city"),
    type_mode: str = Query(default="soft", pattern="^(soft|strict)$"),
    within_qid: str | None = Query(default=None, description="Optional: constrain candidates to those located in this QID (direct P131)"),

    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    try:
        if type_hint is not None and type_hint not in {"neighbourhood", "district", "city"}:
            raise HTTPException(status_code=400, detail="type_hint must be one of: neighbourhood, district, city")

        return wikidata_search_typed(
            session,
            query=query,
            lang=lang,
            limit=limit,
            type_hint=type_hint,   # type: ignore[arg-type]
            type_mode=type_mode,   # type: ignore[arg-type]
            within_qid=within_qid,
            refresh=refresh,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/entity/{qid}")
def wikidata_entity(
    qid: str,
    lang: str = Query(default="bg"),
    refresh: bool = Query(default=False),
    include_raw: bool = Query(default=False),
    session: Session = Depends(get_db_session),
    _: None = Depends(require_api_key),
):
    try:
        payload = wikidata_entity_cached(session, qid=qid, lang=lang, refresh=refresh)
        extracted = extract_kindergarten_relevant_properties(qid=qid, lang=lang, entity_payload=payload["entity"])

        out = {
            "cached": payload["cached"],
            "qid": qid,
            "lang": lang,
            "extracted": extracted,
        }
        if include_raw:
            out["raw"] = payload["entity"]
        return out
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))