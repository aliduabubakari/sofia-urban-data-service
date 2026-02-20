from __future__ import annotations

import datetime as dt
from typing import Any, Iterable, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from suds_core.config.settings import get_settings


class CityLabClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.citylab_api_key:
            raise RuntimeError("Missing SUDS_CITYLAB_API_KEY")

        self.base_url = settings.citylab_base_url.rstrip("/")
        self.timeout_s = settings.citylab_timeout_s

        self.session = requests.Session()
        self.session.headers.update(
            {
                "X-API-Key": settings.citylab_api_key,
                "Accept": "application/json",
                "User-Agent": "suds-core/airquality",
            }
        )

        retry = Retry(
            total=5,
            connect=5,
            read=5,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def list_stations(self) -> list[dict[str, Any]]:
        url = f"{self.base_url}/stations/"
        r = self.session.get(url, timeout=(10, self.timeout_s))
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            raise RuntimeError("Unexpected stations payload")
        return data

    def list_parameters(self) -> Any:
        url = f"{self.base_url}/stations/parameters"
        r = self.session.get(url, timeout=(10, self.timeout_s))
        r.raise_for_status()
        return r.json()

    def list_stations_by_type(self, station_type: str) -> list[dict[str, Any]]:
        url = f"{self.base_url}/stations/type"
        r = self.session.get(url, params={"station_type": station_type}, timeout=(10, self.timeout_s))
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list):
            raise RuntimeError("Unexpected stations/type payload")
        return data

    def aggregated_values(
        self,
        *,
        granularity: str,  # "hour"|"day"|"week"|"month"
        station_name: str,
        selected_params: list[str],
        start_dt: dt.datetime,
        end_dt: dt.datetime,
        calculation_type: str = "Mean",
    ) -> Any:
        """
        Calls one of:
          /aggregated/values/{granularity}/station/
        """
        if granularity not in {"hour", "day", "week", "month"}:
            raise ValueError("granularity must be hour/day/week/month")

        url = f"{self.base_url}/aggregated/values/{granularity}/station/"

        # CityLab expects "YYYY-MM-DD HH:00:00"
        def fmt(x: dt.datetime) -> str:
            x = x.replace(minute=0, second=0, microsecond=0)
            return x.strftime("%Y-%m-%d %H:%M:%S")

        params: list[tuple[str, str]] = [
            ("station_name", station_name),
            ("start_date", fmt(start_dt)),
            ("end_date", fmt(end_dt)),
            ("calculation_type", calculation_type),
        ]
        # selected_params is repeated in query string
        for p in selected_params:
            params.append(("selected_params", p))

        r = self.session.get(url, params=params, timeout=(10, self.timeout_s))
        r.raise_for_status()
        return r.json()