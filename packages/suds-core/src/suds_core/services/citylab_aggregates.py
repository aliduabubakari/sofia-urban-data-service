from __future__ import annotations

import calendar
import datetime as dt
from typing import Any, Iterable

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from suds_core.connectors.citylab import CityLabClient
from suds_core.db.models import CityLabAggregate, CityLabStation

def _month_start(year: int, month: int) -> dt.datetime:
    return dt.datetime(year, month, 1, 0, 0, 0, tzinfo=dt.timezone.utc)


def _next_month_start(year: int, month: int) -> dt.datetime:
    if month == 12:
        return dt.datetime(year + 1, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)
    return dt.datetime(year, month + 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc)


def _normalize_citylab_agg_payload(payload: Any) -> list[dict[str, Any]]:
    """
    We haven't pinned the exact response schema in this chat, so we normalize defensively.

    Supported shapes:
      - list of dicts with keys like {"timestamp": "...", "value": ...} or {"date": "...", "value": ...}
      - dict mapping timestamp->value
      - list of [timestamp, value] pairs
    """
    out: list[dict[str, Any]] = []

    if isinstance(payload, dict):
        for k, v in payload.items():
            out.append({"time": str(k), "value": v, "raw": payload})
        return out

    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                t = item.get("time") or item.get("timestamp") or item.get("date")
                if t is None:
                    # store anyway; caller may handle
                    out.append({"time": None, "value": item, "raw": item})
                else:
                    out.append({"time": str(t), "value": item.get("value", item.get("val", item)), "raw": item})
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                out.append({"time": str(item[0]), "value": item[1], "raw": item})
            else:
                out.append({"time": None, "value": item, "raw": item})
        return out

    # unknown type
    return [{"time": None, "value": payload, "raw": payload}]


def backfill_citylab_monthly_means(
    session: Session,
    *,
    year: int = 2024,
    station_type: str = "airquality",
    params: list[str] = ["PM2.5", "PM10", "NO2", "O3"],
) -> dict[str, Any]:
    client = CityLabClient()

    stations = (
        session.query(CityLabStation)
        .filter(CityLabStation.station_type == station_type)
        .order_by(CityLabStation.name)
        .all()
    )

    upserts = 0
    requested_calls = 0
    skipped_payloads = 0
    skipped_rows = 0

    for st in stations:
        station_name = st.name

        for month in range(1, 13):
            start_dt = _month_start(year, month)
            end_dt = _next_month_start(year, month)

            requested_calls += 1
            payload = client.aggregated_values(
                granularity="month",
                station_name=station_name,
                selected_params=params,     # <-- fetch ALL params at once
                start_dt=start_dt,
                end_dt=end_dt,
                calculation_type="Mean",
            )

            if not isinstance(payload, list):
                skipped_payloads += 1
                continue

            rows_to_upsert: list[dict[str, Any]] = []

            for item in payload:
                if not isinstance(item, dict):
                    skipped_rows += 1
                    continue

                param = item.get("Parameter")
                value = item.get("Values")  # <-- CityLab uses "Values"

                if param is None or value is None:
                    skipped_rows += 1
                    continue

                try:
                    value_f = float(value)
                except Exception:
                    skipped_rows += 1
                    continue

                # Optional: use Start_Date from payload if present, otherwise use start_dt
                period_start = start_dt
                sd = item.get("Start_Date")
                if isinstance(sd, str) and sd:
                    try:
                        # "YYYY-MM-DD HH:MM:SS" -> treat as UTC
                        period_start = dt.datetime.strptime(sd, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
                    except Exception:
                        period_start = start_dt

                rows_to_upsert.append(
                    {
                        "station_name": station_name,
                        "station_type": station_type,
                        "granularity": "month",
                        "period_start": period_start,
                        "param": str(param),
                        "calculation_type": "Mean",
                        "value": value_f,
                        "unit": None,
                        "raw": {"citylab_payload_row": item},
                    }
                )

            if not rows_to_upsert:
                continue

            stmt = insert(CityLabAggregate).values(rows_to_upsert)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_citylab_agg_key",
                set_={
                    "value": stmt.excluded.value,
                    "raw": stmt.excluded.raw,
                    "updated_at": func.now(),
                },
            )
            session.execute(stmt)
            upserts += len(rows_to_upsert)

    session.flush()
    return {
        "station_type": station_type,
        "stations": len(stations),
        "year": year,
        "params": params,
        "requested_calls": requested_calls,
        "rows_upserted": upserts,
        "skipped_payloads": skipped_payloads,
        "skipped_rows": skipped_rows,
    }