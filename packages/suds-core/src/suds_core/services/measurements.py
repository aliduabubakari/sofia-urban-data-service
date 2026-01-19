
# packages/suds-core/src/suds_core/services/measurements.py
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from suds_core.connectors.gate import GateClient
from suds_core.db.models import AirQualityMeasurements, Stations


def get_measurements(
    session: Session,
    *,
    station_name: str,
    parameter: str,
    start: dt.datetime,
    end: dt.datetime,
) -> list[dict[str, Any]]:
    station = session.execute(
        select(Stations).where(Stations.station_name == station_name)
    ).scalar_one_or_none()
    if not station:
        raise ValueError(f"Unknown station: {station_name}")

    rows = session.execute(
        select(AirQualityMeasurements)
        .where(
            and_(
                AirQualityMeasurements.station_id == station.id,
                AirQualityMeasurements.parameter == parameter,
                AirQualityMeasurements.timestamp >= start,
                AirQualityMeasurements.timestamp <= end,
            )
        )
        .order_by(AirQualityMeasurements.timestamp)
    ).scalars().all()

    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "station_name": station_name,
            "parameter": r.parameter,
            "value": r.value,
            "parameter_raw": r.parameter_raw,
            "unit": r.unit,
            "source": r.source,
        }
        for r in rows
    ]


def refresh_measurements_from_gate(
    session: Session,
    *,
    station_name: str,
    parameter: str,
    start: dt.datetime,
    end: dt.datetime,
) -> int:
    """
    Placeholder for pulling from Gate and upserting into AirQualityMeasurements.

    Next step: implement GateClient.fetch_measurements() and parse responses.
    """
    _client = GateClient()  # will raise if creds missing
    _ = _client

    # TODO implement:
    # data = client.fetch_measurements(...)
    # upsert into DB (station_id, parameter, timestamp unique)
    raise NotImplementedError("Implement Gate refresh logic and DB upsert.")