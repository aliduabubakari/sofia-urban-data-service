from __future__ import annotations

from typing import Any

import requests

from suds_core.config.settings import get_settings


class WikidataClient:
    def __init__(self) -> None:
        s = get_settings()
        self.api_url = s.wikidata_api_url
        self.timeout_s = s.http_timeout_s

        # Use a session so we can control headers + proxy behavior
        self.session = requests.Session()

        # IMPORTANT: avoid proxy env vars breaking Wikimedia calls
        self.session.trust_env = False

        # Wikimedia-friendly UA
        user_agent = getattr(s, "wikidata_user_agent", None) or "SUDS/0.1 (contact: dev@localhost)"
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": user_agent,
            }
        )

    def search(self, *, query: str, lang: str = "bg", limit: int = 10) -> dict[str, Any]:
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": lang,
            "format": "json",
            "limit": int(limit),
            "origin": "*",
        }
        r = self.session.get(self.api_url, params=params, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def get_entity(self, *, qid: str, lang: str = "bg") -> dict[str, Any]:
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "languages": lang,
            "props": "labels|descriptions|claims|sitelinks",
            "format": "json",
            "origin": "*",
        }
        r = self.session.get(self.api_url, params=params, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def get_entities(self, *, qids: list[str], lang: str = "bg") -> dict[str, Any]:
        if not qids:
            return {"entities": {}}

        params = {
            "action": "wbgetentities",
            "ids": "|".join(qids),
            "languages": lang,
            "props": "labels|descriptions|claims|sitelinks",
            "format": "json",
            "origin": "*",
        }
        r = self.session.get(self.api_url, params=params, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()