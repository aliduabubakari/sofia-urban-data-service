# packages/suds-core/src/suds_core/services/osm.py
from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from suds_core.connectors.overpass import OverpassClient
from suds_core.db.models import OsmMetrics, Stations


def get_cached_osm_metrics(
    session: Session,
    *,
    station_name: str,
    buffer_m: int = 300,
) -> Optional[dict[str, Any]]:
    station = session.execute(
        select(Stations).where(Stations.station_name == station_name)
    ).scalar_one_or_none()
    if not station:
        raise ValueError(f"Unknown station: {station_name}")

    row = session.execute(
        select(OsmMetrics)
        .where(OsmMetrics.station_id == station.id, OsmMetrics.buffer_m == buffer_m)
        .order_by(desc(OsmMetrics.extracted_at))
        .limit(1)
    ).scalar_one_or_none()

    return row.metrics if row else None


def compute_and_cache_osm_metrics(
    session: Session,
    *,
    station_name: str,
    buffer_m: int = 300,
) -> dict[str, Any]:
    """
    Placeholder: you already have working OSM extraction.
    Here we define the caching mechanism.

    Next step: port your Overpass extraction into here, return metrics dict.
    """
    station = session.execute(
        select(Stations).where(Stations.station_name == station_name)
    ).scalar_one_or_none()
    if not station:
        raise ValueError(f"Unknown station: {station_name}")

    # TODO: implement actual metrics computation using OverpassClient and station coordinates
    client = OverpassClient()
    _ = client  # placeholder to show dependency

    metrics: dict[str, Any] = {
        "station_name": station_name,
        "buffer_m": buffer_m,
        "status": "not_implemented",
    }

    session.add(
        OsmMetrics(
            station_id=station.id,
            buffer_m=buffer_m,
            extracted_at=dt.datetime.now(dt.timezone.utc),
            metrics=metrics,
        )
    )
    session.flush()
    return metrics