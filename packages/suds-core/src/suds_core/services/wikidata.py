from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any, Optional
from typing import Literal


from sqlalchemy import select
from sqlalchemy.orm import Session

from suds_core.config.settings import get_settings
from suds_core.connectors.wikidata import WikidataClient
from suds_core.db.models import WikidataEntityCache, WikidataSearchCache


def _norm(s: str) -> str:
    return " ".join((s or "").strip().split())


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def wikidata_search_cached(session: Session, *, query: str, lang: str = "bg", limit: int = 10, refresh: bool = False) -> dict[str, Any]:
    settings = get_settings()
    qn = _norm(query)
    h = _sha256(f"{qn}|{lang}|{limit}")

    if not refresh:
        row = session.execute(
            select(WikidataSearchCache).where(
                WikidataSearchCache.query_hash == h,
                WikidataSearchCache.lang == lang,
                WikidataSearchCache.limit == limit,
            )
        ).scalar_one_or_none()

        if row:
            return {"cached": True, "query": query, "lang": lang, "limit": limit, "result": row.result}

    client = WikidataClient()
    payload = client.search(query=qn, lang=lang, limit=limit)

    session.add(WikidataSearchCache(query_hash=h, query=qn, lang=lang, limit=limit, result=payload))
    session.flush()

    return {"cached": False, "query": query, "lang": lang, "limit": limit, "result": payload}


def wikidata_entity_cached(session: Session, *, qid: str, lang: str = "bg", refresh: bool = False) -> dict[str, Any]:
    settings = get_settings()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.wikidata_cache_ttl_days)

    if not refresh:
        row = session.execute(
            select(WikidataEntityCache).where(WikidataEntityCache.qid == qid, WikidataEntityCache.lang == lang)
        ).scalar_one_or_none()

        if row and row.updated_at >= cutoff:
            return {"cached": True, "qid": qid, "lang": lang, "entity": row.entity}

    client = WikidataClient()
    payload = client.get_entity(qid=qid, lang=lang)

    row = session.execute(
        select(WikidataEntityCache).where(WikidataEntityCache.qid == qid, WikidataEntityCache.lang == lang)
    ).scalar_one_or_none()

    if row is None:
        session.add(WikidataEntityCache(qid=qid, lang=lang, entity=payload))
    else:
        row.entity = payload

    session.flush()
    return {"cached": False, "qid": qid, "lang": lang, "entity": payload}


# ---------------------------
# Property extraction helpers
# ---------------------------
def _claims(entity_payload: dict[str, Any], qid: str) -> dict[str, Any]:
    try:
        return entity_payload["entities"][qid]["claims"]
    except Exception:
        return {}


def _label(entity_payload: dict[str, Any], qid: str, lang: str) -> Optional[str]:
    try:
        return entity_payload["entities"][qid]["labels"][lang]["value"]
    except Exception:
        return None


def _description(entity_payload: dict[str, Any], qid: str, lang: str) -> Optional[str]:
    try:
        return entity_payload["entities"][qid]["descriptions"][lang]["value"]
    except Exception:
        return None


def _sitelink(entity_payload: dict[str, Any], qid: str, site: str) -> Optional[str]:
    try:
        return entity_payload["entities"][qid]["sitelinks"][site]["title"]
    except Exception:
        return None


def _extract_quantity(claims: dict[str, Any], pid: str) -> list[dict[str, Any]]:
    """
    Returns list of quantities with optional 'point_in_time' qualifier.
    Handles P1082 (population), P2046 (area), P2044 (elevation).
    """
    out: list[dict[str, Any]] = []
    for c in claims.get(pid, []) or []:
        try:
            mainsnak = c["mainsnak"]
            dv = mainsnak["datavalue"]["value"]
            amount = float(dv["amount"])
            unit = dv.get("unit")
            qualifiers = c.get("qualifiers", {}) or {}
            # point in time qualifier P585 (optional)
            pit = None
            if "P585" in qualifiers and qualifiers["P585"]:
                pitv = qualifiers["P585"][0]["datavalue"]["value"]
                pit = pitv.get("time")
            out.append({"value": amount, "unit": unit, "point_in_time": pit})
        except Exception:
            continue
    return out


def _best_latest_quantity(values: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """
    Picks the entry with the latest point_in_time when available; otherwise the first.
    """
    if not values:
        return None

    def sort_key(v: dict[str, Any]) -> str:
        # Wikidata time looks like "+2020-01-01T00:00:00Z"
        return str(v.get("point_in_time") or "")

    # place dated values last lexicographically works for ISO-like dates
    return sorted(values, key=sort_key, reverse=True)[0]


def extract_kindergarten_relevant_properties(
    *,
    qid: str,
    lang: str,
    entity_payload: dict[str, Any],
) -> dict[str, Any]:
    claims = _claims(entity_payload, qid)

    population = _best_latest_quantity(_extract_quantity(claims, "P1082"))  # population
    area = _best_latest_quantity(_extract_quantity(claims, "P2046"))        # area
    elevation = _best_latest_quantity(_extract_quantity(claims, "P2044"))   # elevation

    # Compute density if possible (assuming area is in m² in many Wikidata entries, but not guaranteed)
    density_per_km2 = None
    if population and area:
        try:
            pop = float(population["value"])
            area_val = float(area["value"])
            # Heuristic: if area is huge, likely m²; if small could be km² (unit varies).
            # We'll support both by checking the unit URI.
            unit = (area.get("unit") or "")
            if "square kilometre" in unit or unit.endswith("Q712226"):  # Wikidata Q712226 = square kilometre
                area_km2 = area_val
            else:
                # assume m²
                area_km2 = area_val / 1_000_000.0

            if area_km2 > 0:
                density_per_km2 = pop / area_km2
        except Exception:
            density_per_km2 = None

    bgwiki_title = _sitelink(entity_payload, qid, "bgwiki")
    enwiki_title = _sitelink(entity_payload, qid, "enwiki")

    def wiki_url(title: Optional[str], lang_code: str) -> Optional[str]:
        if not title:
            return None
        return f"https://{lang_code}.wikipedia.org/wiki/{title.replace(' ', '_')}"

    return {
        "qid": qid,
        "label": _label(entity_payload, qid, lang),
        "description": _description(entity_payload, qid, lang),
        "wikipedia": {
            "bg": wiki_url(bgwiki_title, "bg"),
            "en": wiki_url(enwiki_title, "en"),
        },
        "population": population,
        "area": area,
        "elevation": elevation,
        "population_density_per_km2_est": density_per_km2,
        "notes": {
            "population_pid": "P1082",
            "area_pid": "P2046",
            "elevation_pid": "P2044",
            "density_computed": True,
        },
    }


TypeHint = Literal["neighbourhood", "district", "city"]
TypeMode = Literal["soft", "strict"]


# Minimal initial mapping (expand over time)
TYPE_HINT_INSTANCE_OF: dict[str, set[str]] = {
    # Q515 = city
    "city": {"Q515"},
    # neighbourhood/suburb
    "neighbourhood": {"Q123705", "Q188509"},
    # district / city district (these can vary)
    "district": {"Q1187811", "Q13220204"},
}


def _extract_qids_from_claims(entity_payload: dict[str, Any], qid: str, pid: str) -> list[str]:
    """
    Extract QIDs from entity claims:
      - P31 (instance of)
      - P131 (located in the administrative territorial entity)
    """
    try:
        claims = entity_payload["entities"][qid]["claims"]
    except Exception:
        return []

    out: list[str] = []
    for c in claims.get(pid, []) or []:
        try:
            dv = c["mainsnak"]["datavalue"]["value"]
            if dv.get("entity-type") == "item":
                out.append(str(dv.get("id")))
        except Exception:
            continue
    return out


def _extract_search_hits(search_payload: dict[str, Any]) -> list[dict[str, Any]]:
    hits = search_payload.get("search") or []
    if not isinstance(hits, list):
        return []
    out = []
    for h in hits:
        if not isinstance(h, dict):
            continue
        # the search API gives "id", "label", "description", "match" sometimes
        out.append(h)
    return out


def wikidata_search_typed(
    session: Session,
    *,
    query: str,
    lang: str = "bg",
    limit: int = 10,
    type_hint: TypeHint | None = None,
    type_mode: TypeMode = "soft",
    within_qid: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """
    Search + optional type hint filtering/reranking based on:
      - P31 (instance of)
      - optional within_qid check using P131 (direct containment)

    Soft mode: rerank, but keep non-matching results.
    Strict mode: keep only matching results; if none match, returns empty list.

    Note: within_qid uses direct P131 membership only (not recursive). This is good enough for v1.
    """
    base = wikidata_search_cached(session, query=query, lang=lang, limit=limit, refresh=refresh)
    payload = base["result"]
    hits = _extract_search_hits(payload)

    # No type filtering requested -> return raw search with a uniform wrapper
    if type_hint is None and within_qid is None:
        return {
            "cached": base["cached"],
            "query": query,
            "lang": lang,
            "limit": limit,
            "type_hint": None,
            "type_mode": type_mode,
            "within_qid": None,
            "results": hits,
            "notes": ["No type_hint/within_qid applied."],
        }

    # Collect candidate qids
    qids = [h.get("id") for h in hits if isinstance(h.get("id"), str) and h.get("id", "").startswith("Q")]
    qids = qids[:limit]

    # Bulk fetch entities (cached per-qid as well)
    # We'll fetch only those missing or stale.
    # For simplicity: call wikidata_entity_cached per qid (uses TTL), but that's multiple HTTP calls.
    # Better: bulk fetch missing qids in one call. We'll do hybrid:
    settings = get_settings()
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=settings.wikidata_cache_ttl_days)

    cached_entities: dict[str, dict[str, Any]] = {}
    missing: list[str] = []

    for q in qids:
        row = session.execute(
            select(WikidataEntityCache).where(WikidataEntityCache.qid == q, WikidataEntityCache.lang == lang)
        ).scalar_one_or_none()
        if row and row.updated_at >= cutoff and isinstance(row.entity, dict):
            cached_entities[q] = row.entity
        else:
            missing.append(q)

    if missing:
        client = WikidataClient()
        bulk_payload = client.get_entities(qids=missing, lang=lang)

        # Save each entity to cache table
        entities_dict = bulk_payload.get("entities") or {}
        for q in missing:
            ent = entities_dict.get(q)
            if not isinstance(ent, dict):
                continue
            normalized = {"entities": {q: ent}}

            row = session.execute(
                select(WikidataEntityCache).where(WikidataEntityCache.qid == q, WikidataEntityCache.lang == lang)
            ).scalar_one_or_none()
            if row is None:
                session.add(WikidataEntityCache(qid=q, lang=lang, entity=normalized))
            else:
                row.entity = normalized

            cached_entities[q] = normalized

        session.flush()

    allowed_p31 = TYPE_HINT_INSTANCE_OF.get(type_hint, set()) if type_hint else set()

    enriched = []
    for h in hits:
        q = h.get("id")
        if not isinstance(q, str) or q not in cached_entities:
            enriched.append({**h, "type_match": None, "within_match": None, "instance_of": [], "located_in": []})
            continue

        ent = cached_entities[q]
        instance_of = _extract_qids_from_claims(ent, q, "P31")
        located_in = _extract_qids_from_claims(ent, q, "P131")

        type_match = None
        if type_hint is not None:
            type_match = any(x in allowed_p31 for x in instance_of)

        within_match = None
        if within_qid is not None:
            within_match = within_qid in located_in

        enriched.append(
            {
                **h,
                "type_match": type_match,
                "within_match": within_match,
                "instance_of": instance_of,
                "located_in": located_in,
            }
        )

    # Apply strict filtering if requested
    if type_mode == "strict":
        filtered = []
        for r in enriched:
            ok = True
            if type_hint is not None:
                ok = ok and (r.get("type_match") is True)
            if within_qid is not None:
                ok = ok and (r.get("within_match") is True)
            if ok:
                filtered.append(r)

        return {
            "cached": base["cached"],
            "query": query,
            "lang": lang,
            "limit": limit,
            "type_hint": type_hint,
            "type_mode": type_mode,
            "within_qid": within_qid,
            "results": filtered,
            "notes": [
                "Type filtering is best-effort based on direct P31/P131 claims.",
                "type_mode=strict removes non-matching candidates.",
            ],
        }

    # Soft mode reranking
    def rank_key(r: dict[str, Any]) -> tuple[int, int, float]:
        # within_match first, then type_match, then original match score if available
        w = 1 if r.get("within_match") is True else 0
        t = 1 if r.get("type_match") is True else 0
        # search API sometimes returns "match" dict or "match" float; handle both
        score = 0.0
        m = r.get("match")
        if isinstance(m, dict) and "text" in m:
            score = 1.0
        elif isinstance(m, (int, float)):
            score = float(m)
        return (w, t, score)

    reranked = sorted(enriched, key=rank_key, reverse=True)

    return {
        "cached": base["cached"],
        "query": query,
        "lang": lang,
        "limit": limit,
        "type_hint": type_hint,
        "type_mode": type_mode,
        "within_qid": within_qid,
        "results": reranked,
        "notes": [
            "Type filtering is best-effort based on direct P31/P131 claims.",
            "type_mode=soft reranks but keeps non-matching candidates.",
            "within_qid uses direct P131 only (not recursive).",
        ],
    }