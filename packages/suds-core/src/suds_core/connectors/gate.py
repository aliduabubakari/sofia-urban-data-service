from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any, List, Optional
from urllib.parse import urljoin

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from suds_core.config.settings import get_settings


@dataclass(frozen=True)
class GateStation:
    name: str
    latitude: float
    longitude: float
    raw: dict[str, Any]


class GateClient:
    """
    Robust stations-only client.
    Tries CityLab first, then Twin-Web.

    Auth:
      - If GATE_API_KEY is set -> sends API key header.
      - Else uses Basic auth from GATE_API_USERNAME/PASSWORD.
    """

    api_variants = [
        {"name": "citylab", "base_url": "https://citylab.gate-ai.eu/citylab/api/", "stations": "stations/"},
        {"name": "twin", "base_url": "https://twin-web.gate-ai.eu/", "stations": "/api/dist/stations/"},
    ]

    def __init__(self) -> None:
        self.settings = get_settings()
        self.timeout_s = int(os.getenv("GATE_REQUEST_TIMEOUT", str(self.settings.http_timeout_s)))

        self.session = requests.Session()
        self.session.trust_env = os.getenv("GATE_DISABLE_PROXIES", "0") != "1"

        # browser-like headers help with some gateways/WAFs
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate, br",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Connection": "keep-alive",
            }
        )

        # Auth mode: API key preferred if present
        if self.settings.gate_api_key:
            self.session.headers[self.settings.gate_api_key_header] = self.settings.gate_api_key
        else:
            user = self.settings.gate_api_username
            pwd = self.settings.gate_api_password
            if not user or not pwd:
                raise RuntimeError("Missing Gate credentials. Set either GATE_API_KEY or GATE_API_USERNAME/PASSWORD.")
            credentials = base64.b64encode(f"{user}:{pwd}".encode()).decode()
            self.session.headers["Authorization"] = f"Basic {credentials}"

        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.variant_name: Optional[str] = None
        self.base_url: Optional[str] = None
        self.stations_endpoint: Optional[str] = None

    def _get_json(self, base_url: str, endpoint: str) -> Any:
        url = urljoin(base_url, endpoint.lstrip("/"))
        r = self.session.get(url, timeout=self.timeout_s)
        r.raise_for_status()
        return r.json()

    def autodetect(self) -> None:
        last_err: Optional[Exception] = None
        for v in self.api_variants:
            try:
                data = self._get_json(v["base_url"], v["stations"])
                if isinstance(data, list) and data and isinstance(data[0], dict) and "name" in data[0]:
                    self.variant_name = v["name"]
                    self.base_url = v["base_url"]
                    self.stations_endpoint = v["stations"]
                    return
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"Failed to connect to any GATE API variant. Last error: {last_err}")

    def list_stations(self) -> List[GateStation]:
        if not self.base_url:
            self.autodetect()
        assert self.base_url and self.stations_endpoint

        data = self._get_json(self.base_url, self.stations_endpoint)
        out: List[GateStation] = []
        if not isinstance(data, list):
            return out

        for row in data:
            try:
                out.append(
                    GateStation(
                        name=str(row["name"]),
                        latitude=float(row["latitude"]),
                        longitude=float(row["longitude"]),
                        raw=row,
                    )
                )
            except Exception:
                continue
        return out