# packages/suds-core/src/suds_core/connectors/overpass.py
from __future__ import annotations

import time
from typing import Any, Optional

import requests

from suds_core.config.settings import get_settings


class OverpassClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.url = self.settings.overpass_url
        self.timeout = self.settings.overpass_timeout_s
        self.rate_limit_delay = self.settings.overpass_rate_limit_delay_s

    def query(self, query: str, *, retries: int = 3, backoff_s: float = 2.0) -> Optional[dict[str, Any]]:
        for attempt in range(1, retries + 1):
            try:
                r = requests.post(self.url, data={"data": query}, timeout=self.timeout)
                if r.status_code == 429:
                    time.sleep(backoff_s * attempt)
                    continue
                r.raise_for_status()
                time.sleep(self.rate_limit_delay)
                return r.json()
            except Exception:
                if attempt == retries:
                    return None
                time.sleep(backoff_s * attempt)
        return None
