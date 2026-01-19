# packages/suds-core/src/suds_core/connectors/openmeteo.py
from __future__ import annotations

import datetime as dt
from typing import Any

import requests

from suds_core.config.settings import get_settings


class OpenMeteoClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.openmeteo_archive_url
        self.timeout = self.settings.http_timeout_s

    def fetch_daily(
        self,
        *,
        lat: float,
        lon: float,
        start_date: dt.date,
        end_date: dt.date,
        timezone: str = "Europe/Sofia",
    ) -> list[dict[str, Any]]:
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "apparent_temperature_max",
                "apparent_temperature_min",
                "precipitation_sum",
                "daylight_duration",
                "windspeed_10m_max",
                "winddirection_10m_dominant",
                "windgusts_10m_max",
                "relative_humidity_2m_max",
                "relative_humidity_2m_min",
            ],
            "timezone": timezone,
        }

        r = requests.get(self.base_url, params=params, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        
        # Extract elevation from response
        elevation_m = data.get("elevation")

        daily = data.get("daily")
        if not daily:
            return []

        # Normalize into list of rows keyed by date
        dates = daily.get("time", [])
        out: list[dict[str, Any]] = []
        for i, d in enumerate(dates):
            row = {"date": d}
            for k, v in daily.items():
                if k == "time":
                    continue
                if isinstance(v, list) and i < len(v):
                    row[k] = v[i]
            
            # Add elevation to each row
            row["elevation_m"] = elevation_m
            
            # computed fields (optional)
            if "temperature_2m_max" in row and "temperature_2m_min" in row:
                row["temperature_2m_mean"] = (row["temperature_2m_max"] + row["temperature_2m_min"]) / 2.0
            if "relative_humidity_2m_max" in row and "relative_humidity_2m_min" in row:
                row["relative_humidity_2m_mean"] = (row["relative_humidity_2m_max"] + row["relative_humidity_2m_min"]) / 2.0

            out.append(row)

        return out