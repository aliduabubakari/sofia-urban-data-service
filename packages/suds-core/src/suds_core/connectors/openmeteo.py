from __future__ import annotations

import datetime as dt
from typing import Any, Iterable, Optional

import requests

from suds_core.config.settings import get_settings


class OpenMeteoClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.timeout = self.settings.http_timeout_s

        self.archive_url = self.settings.openmeteo_archive_url
        self.forecast_url = self.settings.openmeteo_forecast_url

    def _get(
        self,
        *,
        base_url: str,
        lat: float,
        lon: float,
        start_date: dt.date,
        end_date: dt.date,
        daily_vars: Optional[Iterable[str]] = None,
        hourly_vars: Optional[Iterable[str]] = None,
        timezone: str = "UTC",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": timezone,
        }

        if daily_vars:
            params["daily"] = list(daily_vars)
        if hourly_vars:
            params["hourly"] = list(hourly_vars)

        r = requests.get(base_url, params=params, timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    # -------------------
    # Daily
    # -------------------
    def fetch_daily(
        self,
        *,
        source: str,  # "archive" | "forecast"
        lat: float,
        lon: float,
        start_date: dt.date,
        end_date: dt.date,
        timezone: str = "UTC",
    ) -> list[dict[str, Any]]:
        base_url = self.archive_url if source == "archive" else self.forecast_url

        daily_vars = [
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
        ]

        data = self._get(
            base_url=base_url,
            lat=lat,
            lon=lon,
            start_date=start_date,
            end_date=end_date,
            daily_vars=daily_vars,
            hourly_vars=None,
            timezone=timezone,
        )

        elevation_m = data.get("elevation")
        daily = data.get("daily") or {}
        dates = daily.get("time") or []

        out: list[dict[str, Any]] = []
        for i, d in enumerate(dates):
            row: dict[str, Any] = {"date": d, "elevation_m": elevation_m}
            for k, v in daily.items():
                if k == "time":
                    continue
                if isinstance(v, list) and i < len(v):
                    row[k] = v[i]

            # convenience derived means
            if "temperature_2m_max" in row and "temperature_2m_min" in row:
                row["temperature_2m_mean"] = (row["temperature_2m_max"] + row["temperature_2m_min"]) / 2.0
            if "relative_humidity_2m_max" in row and "relative_humidity_2m_min" in row:
                row["relative_humidity_2m_mean"] = (row["relative_humidity_2m_max"] + row["relative_humidity_2m_min"]) / 2.0

            out.append(row)

        return out

    # -------------------
    # Hourly
    # -------------------
    def fetch_hourly(
        self,
        *,
        source: str,  # "archive" | "forecast"
        lat: float,
        lon: float,
        start_date: dt.date,
        end_date: dt.date,
        timezone: str = "UTC",
    ) -> list[dict[str, Any]]:
        base_url = self.archive_url if source == "archive" else self.forecast_url

        hourly_vars = [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "windspeed_10m",
            "winddirection_10m",
            "windgusts_10m",
        ]

        data = self._get(
            base_url=base_url,
            lat=lat,
            lon=lon,
            start_date=start_date,
            end_date=end_date,
            daily_vars=None,
            hourly_vars=hourly_vars,
            timezone=timezone,
        )

        elevation_m = data.get("elevation")
        hourly = data.get("hourly") or {}
        times = hourly.get("time") or []

        out: list[dict[str, Any]] = []
        for i, t in enumerate(times):
            row: dict[str, Any] = {"timestamp": t, "elevation_m": elevation_m}
            for k, v in hourly.items():
                if k == "time":
                    continue
                if isinstance(v, list) and i < len(v):
                    row[k] = v[i]
            out.append(row)

        return out