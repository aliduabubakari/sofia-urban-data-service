from __future__ import annotations

import time
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from suds_core.config.settings import get_settings


class GeoapifyClient:
    def __init__(self) -> None:
        s = get_settings()
        if not s.geoapify_api_key:
            raise RuntimeError("Missing SUDS_GEOAPIFY_API_KEY")

        self.api_key = s.geoapify_api_key
        self.base_url = s.geoapify_base_url.rstrip("/")
        self.timeout_s = s.http_timeout_s

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "suds-core/geocode",
            }
        )

        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=0.8,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def search(self, *, text: str, limit: int = 5, lang: str = "bg") -> dict[str, Any]:
        url = f"{self.base_url}/search"
        params = {
            "text": text,
            "lang": lang,
            "limit": int(limit),
            "format": "json",         # Geoapify supports "json" (not GeoJSON) too
            "apiKey": self.api_key,
        }
        r = self.session.get(url, params=params, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def reverse(self, *, lat: float, lon: float, limit: int = 1, lang: str = "bg") -> dict[str, Any]:
        url = f"{self.base_url}/reverse"
        params = {
            "lat": float(lat),
            "lon": float(lon),
            "lang": lang,
            "limit": int(limit),
            "format": "json",
            "apiKey": self.api_key,
        }
        r = self.session.get(url, params=params, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    # Optional: Geoapify batch job API (may require plan; keep behind feature flag)
    def batch_search_create_job(self, *, texts: list[str], limit: int = 1, lang: str = "bg") -> str:
        """
        Geoapify documented pattern (approx):
          POST /v1/batch/geocode/search?apiKey=...
          body: { "api": "/v1/geocode/search", "params": {...}, "queries": [{"text": "..."}] }
        """
        # NOTE: Geoapify uses a different base for batch endpoints
        url = "https://api.geoapify.com/v1/batch/geocode/search"
        payload = {
            "api": "/v1/geocode/search",
            "params": {"limit": int(limit), "lang": lang, "format": "json"},
            "queries": [{"text": t} for t in texts],
        }
        r = self.session.post(url, params={"apiKey": self.api_key}, json=payload, timeout=self.timeout_s)
        r.raise_for_status()
        data = r.json()
        job_id = data.get("id")
        if not job_id:
            raise RuntimeError(f"Unexpected Geoapify batch create response: {data}")
        return str(job_id)

    def batch_search_fetch_results(self, *, job_id: str) -> Any:
        """
        GET results:
          GET /v1/batch/geocode/search?id=JOB_ID&apiKey=...&format=json
        """
        url = "https://api.geoapify.com/v1/batch/geocode/search"
        r = self.session.get(url, params={"id": job_id, "apiKey": self.api_key, "format": "json"}, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def batch_search_wait(self, *, job_id: str, timeout_s: int = 60, poll_s: float = 1.0) -> Any:
        t0 = time.time()
        while True:
            try:
                return self.batch_search_fetch_results(job_id=job_id)
            except requests.HTTPError as e:
                # Some implementations return 404/202 while still processing; keep polling
                if time.time() - t0 > timeout_s:
                    raise RuntimeError(f"Geoapify batch job timed out after {timeout_s}s") from e
                time.sleep(poll_s)