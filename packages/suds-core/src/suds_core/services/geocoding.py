from __future__ import annotations

import hashlib
import time
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from suds_core.config.settings import get_settings
from suds_core.connectors.geoapify import GeoapifyClient
from suds_core.db.models import GeocodeCache


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split())


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _extract_best_from_geoapify_json(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Geoapify format=json returns:
      { "results": [ { "lat":..., "lon":..., "formatted":..., "rank": {...} } ], ... }
    """
    results = payload.get("results") or []
    if not isinstance(results, list) or not results:
        return {"lat": None, "lon": None, "formatted": None, "confidence": None}

    best = results[0] if isinstance(results[0], dict) else {}
    lat = best.get("lat")
    lon = best.get("lon")
    formatted = best.get("formatted")
    # confidence is not always present; rank.confidence sometimes exists
    confidence = None
    rank = best.get("rank")
    if isinstance(rank, dict) and "confidence" in rank:
        confidence = rank.get("confidence")

    return {"lat": lat, "lon": lon, "formatted": formatted, "confidence": confidence}


def geocode_search_cached(
    session: Session,
    *,
    text: str,
    limit: int = 5,
    lang: str = "bg",
    provider: str = "geoapify",
    force_refresh: bool = False,
) -> dict[str, Any]:
    s = get_settings()
    q = _norm_text(text)
    h = _sha256_hex(f"search|{lang}|{limit}|{q}")

    if not force_refresh:
        row = session.execute(
            select(GeocodeCache).where(
                GeocodeCache.provider == provider,
                GeocodeCache.kind == "search",
                GeocodeCache.query_hash == h,
            )
        ).scalar_one_or_none()

        if row:
            return {
                "cached": True,
                "provider": provider,
                "kind": "search",
                "query": text,
                "query_norm": row.query_text,
                "best": {
                    "lat": row.best_lat,
                    "lon": row.best_lon,
                    "formatted": row.best_formatted,
                    "confidence": row.best_confidence,
                },
                "result": row.result,
            }

    # Rate limit (simple)
    delay_s = 60.0 / max(1, int(s.geocode_rate_limit_per_min))
    time.sleep(delay_s)

    client = GeoapifyClient()
    payload = client.search(text=text, limit=limit, lang=lang)
    best = _extract_best_from_geoapify_json(payload)

    session.add(
        GeocodeCache(
            provider=provider,
            kind="search",
            query_hash=h,
            query_text=q,
            best_lat=best["lat"],
            best_lon=best["lon"],
            best_formatted=best["formatted"],
            best_confidence=best["confidence"],
            result=payload,
        )
    )
    session.flush()

    return {
        "cached": False,
        "provider": provider,
        "kind": "search",
        "query": text,
        "query_norm": q,
        "best": best,
        "result": payload,
    }


def geocode_reverse_cached(
    session: Session,
    *,
    lat: float,
    lon: float,
    limit: int = 1,
    lang: str = "bg",
    provider: str = "geoapify",
    coord_precision: int = 5,
    force_refresh: bool = False,
) -> dict[str, Any]:
    s = get_settings()

    lat_r = round(float(lat), coord_precision)
    lon_r = round(float(lon), coord_precision)
    q = f"{lat_r},{lon_r}"
    h = _sha256_hex(f"reverse|{lang}|{limit}|{q}")

    if not force_refresh:
        row = session.execute(
            select(GeocodeCache).where(
                GeocodeCache.provider == provider,
                GeocodeCache.kind == "reverse",
                GeocodeCache.query_hash == h,
            )
        ).scalar_one_or_none()

        if row:
            return {
                "cached": True,
                "provider": provider,
                "kind": "reverse",
                "query": {"lat": lat, "lon": lon},
                "query_norm": row.query_text,
                "best": {
                    "lat": row.best_lat,
                    "lon": row.best_lon,
                    "formatted": row.best_formatted,
                    "confidence": row.best_confidence,
                },
                "result": row.result,
            }

    delay_s = 60.0 / max(1, int(s.geocode_rate_limit_per_min))
    time.sleep(delay_s)

    client = GeoapifyClient()
    payload = client.reverse(lat=lat_r, lon=lon_r, limit=limit, lang=lang)
    best = _extract_best_from_geoapify_json(payload)

    session.add(
        GeocodeCache(
            provider=provider,
            kind="reverse",
            query_hash=h,
            query_text=q,
            best_lat=best["lat"],
            best_lon=best["lon"],
            best_formatted=best["formatted"],
            best_confidence=best["confidence"],
            result=payload,
        )
    )
    session.flush()

    return {
        "cached": False,
        "provider": provider,
        "kind": "reverse",
        "query": {"lat": lat, "lon": lon},
        "query_norm": q,
        "best": best,
        "result": payload,
    }


def geocode_search_batch(
    session: Session,
    *,
    queries: list[str],
    limit: int = 5,
    lang: str = "bg",
    force_refresh: bool = False,
) -> dict[str, Any]:
    """
    Batch geocode:
    - returns results aligned to input queries
    - uses DB cache for hits
    - for misses:
        - sequential calls by default (reliable)
        - optional Geoapify batch job if enabled and list is large
    """
    s = get_settings()

    if len(queries) > s.geocode_batch_max_size:
        raise ValueError(f"Too many queries: {len(queries)} > {s.geocode_batch_max_size}")

    # 1) cache hits
    results: list[dict[str, Any]] = []
    misses: list[tuple[int, str]] = []

    for i, q in enumerate(queries):
        qn = _norm_text(q)
        h = _sha256_hex(f"search|{lang}|{limit}|{qn}")

        if not force_refresh:
            row = session.execute(
                select(GeocodeCache).where(
                    GeocodeCache.provider == "geoapify",
                    GeocodeCache.kind == "search",
                    GeocodeCache.query_hash == h,
                )
            ).scalar_one_or_none()
            if row:
                results.append(
                    {
                        "index": i,
                        "query": q,
                        "cached": True,
                        "best": {
                            "lat": row.best_lat,
                            "lon": row.best_lon,
                            "formatted": row.best_formatted,
                            "confidence": row.best_confidence,
                        },
                        "result": row.result,
                    }
                )
                continue

        misses.append((i, q))
        results.append({"index": i, "query": q, "cached": False, "best": None, "result": None})

    if not misses:
        return {"count": len(queries), "cached_hits": len(queries), "fetched": 0, "results": sorted(results, key=lambda r: r["index"])}

    # 2) fetch misses
    fetched = 0

    # Optional Geoapify batch job usage
    if s.geoapify_use_batch_api and len(misses) >= s.geoapify_batch_min_size:
        client = GeoapifyClient()
        texts = [q for _, q in misses]
        job_id = client.batch_search_create_job(texts=texts, limit=1, lang=lang)
        payload = client.batch_search_wait(job_id=job_id, timeout_s=s.geoapify_batch_timeout_s, poll_s=s.geoapify_batch_poll_s)

        # payload format varies by plan; we handle common form:
        # list aligned to queries OR dict with "results"
        payload_list: list[Any]
        if isinstance(payload, list):
            payload_list = payload
        elif isinstance(payload, dict) and "results" in payload and isinstance(payload["results"], list):
            payload_list = payload["results"]
        else:
            payload_list = [payload] * len(misses)

        for (idx, q), item_payload in zip(misses, payload_list):
            # normalize item_payload into Geoapify-like search payload with "results"
            if isinstance(item_payload, dict) and "results" in item_payload:
                search_payload = item_payload
            else:
                search_payload = {"results": item_payload if isinstance(item_payload, list) else []}

            row = geocode_search_cached(session, text=q, limit=limit, lang=lang, force_refresh=True)
            # overwrite result slot
            results[idx]["best"] = row["best"]
            results[idx]["result"] = row["result"]
            fetched += 1

    else:
        # Reliable default: sequential search calls
        for idx, q in misses:
            row = geocode_search_cached(session, text=q, limit=limit, lang=lang, force_refresh=force_refresh)
            results[idx]["best"] = row["best"]
            results[idx]["result"] = row["result"]
            fetched += 1

    return {
        "count": len(queries),
        "cached_hits": len(queries) - len(misses),
        "fetched": fetched,
        "results": sorted(results, key=lambda r: r["index"]),
    }