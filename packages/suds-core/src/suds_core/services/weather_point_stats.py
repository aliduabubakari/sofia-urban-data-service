from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Optional


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def _basic_stats(values: Iterable[Any]) -> dict[str, Any]:
    nums = [float(v) for v in values if _is_num(v)]
    if not nums:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(nums),
        "min": min(nums),
        "max": max(nums),
        "mean": sum(nums) / len(nums),
    }


def _circular_mean_deg(values: Iterable[Any]) -> Optional[float]:
    degs = [float(v) for v in values if _is_num(v)]
    if not degs:
        return None
    # circular mean
    s = sum(math.sin(math.radians(d)) for d in degs)
    c = sum(math.cos(math.radians(d)) for d in degs)
    if s == 0 and c == 0:
        return None
    ang = math.degrees(math.atan2(s, c))
    return ang % 360.0


def weather_timeseries_stats(
    *,
    granularity: str,  # "daily" | "hourly"
    rows: list[dict[str, Any]],
) -> Dict[str, Any]:
    """
    Computes simple summary stats over returned rows.
    This is intentionally lightweight and schema-flexible.
    """
    elevation = None
    for r in rows:
        if r.get("elevation_m") is not None:
            elevation = r.get("elevation_m")
            break

    if granularity == "daily":
        return {
            "granularity": "daily",
            "n_rows": len(rows),
            "elevation_m": elevation,
            "temperature_2m_max": _basic_stats([r.get("temperature_2m_max") for r in rows]),
            "temperature_2m_min": _basic_stats([r.get("temperature_2m_min") for r in rows]),
            "temperature_2m_mean": _basic_stats([r.get("temperature_2m_mean") for r in rows]),
            "precipitation_sum_total": sum(float(r.get("precipitation_sum") or 0.0) for r in rows if _is_num(r.get("precipitation_sum"))),
            "windspeed_10m_max": _basic_stats([r.get("windspeed_10m_max") for r in rows]),
            "winddirection_10m_dominant_circular_mean": _circular_mean_deg([r.get("winddirection_10m_dominant") for r in rows]),
        }

    # hourly
    return {
        "granularity": "hourly",
        "n_rows": len(rows),
        "elevation_m": elevation,
        "temperature_2m": _basic_stats([r.get("temperature_2m") for r in rows]),
        "precipitation_total": sum(float(r.get("precipitation") or 0.0) for r in rows if _is_num(r.get("precipitation"))),
        "windspeed_10m": _basic_stats([r.get("windspeed_10m") for r in rows]),
        "winddirection_10m_circular_mean": _circular_mean_deg([r.get("winddirection_10m") for r in rows]),
    }