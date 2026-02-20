from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from suds_core.db.models import CityLabAggregate, CityLabStation


Method = Literal["nearest", "idw"]


def airquality_exposure_point(
    session: Session,
    *,
    lat: float,
    lon: float,
    start: dt.date,
    end: dt.date,
    params: list[str] = ["PM2.5", "PM10", "NO2", "O3"],
    method: Method = "idw",
    k: int = 3,
    granularity: Literal["month"] = "month",
) -> dict[str, Any]:
    """
    Phase 1: exposure uses monthly mean aggregates stored in DB.

    Output: weighted exposure per month and overall mean across months.
    """
    if granularity != "month":
        raise ValueError("Phase 1 supports only granularity='month' (monthly means)")

    if k < 1 or k > 5:
        raise ValueError("k must be 1..5")

    # Find nearest k airquality stations by distance (meters)
    # Use geography distance for meters
    pt = func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326)
    dist_m = func.ST_Distance(func.Geography(CityLabStation.geom), func.Geography(pt)).label("distance_m")

    stations = session.execute(
        select(CityLabStation, dist_m)
        .where(CityLabStation.station_type == "airquality")
        .order_by(dist_m)
        .limit(k)
    ).all()

    if not stations:
        return {"error": "No airquality stations available"}

    # IDW weights
    eps = 10.0  # meters to avoid division blow-up
    power = 2.0

    station_info = []
    weights = []
    for st, d in stations:
        d = float(d)
        w = 1.0 / ((d + eps) ** power)
        weights.append(w)
        station_info.append(
            {"station_name": st.name, "external_id": st.external_id, "distance_m": d, "weight": w}
        )

    # Normalize weights
    wsum = sum(weights) or 1.0
    for s in station_info:
        s["weight_norm"] = s["weight"] / wsum

    if method == "nearest":
        # force weights: 1 for first
        station_info = [station_info[0]]
        station_info[0]["weight_norm"] = 1.0

    # Determine month starts within [start,end]
    # We store period_start at YYYY-MM-01 00:00:00Z
    start_month = dt.date(start.year, start.month, 1)
    end_month = dt.date(end.year, end.month, 1)

    month_starts = []
    cur = start_month
    while cur <= end_month:
        month_starts.append(dt.datetime(cur.year, cur.month, 1, tzinfo=dt.timezone.utc))
        # increment month
        if cur.month == 12:
            cur = dt.date(cur.year + 1, 1, 1)
        else:
            cur = dt.date(cur.year, cur.month + 1, 1)

    # Fetch aggregates for these stations/months/params
    station_names = [s["station_name"] for s in station_info]

    rows = session.execute(
        select(
            CityLabAggregate.station_name,
            CityLabAggregate.period_start,
            CityLabAggregate.param,
            CityLabAggregate.value,
        )
        .where(
            CityLabAggregate.station_type == "airquality",
            CityLabAggregate.granularity == "month",
            CityLabAggregate.calculation_type == "Mean",
            CityLabAggregate.station_name.in_(station_names),
            CityLabAggregate.param.in_(params),
            CityLabAggregate.period_start.in_(month_starts),
        )
    ).all()

    # index: (station, period_start, param) -> value
    val = {(r[0], r[1], r[2]): float(r[3]) for r in rows}

    # Build weighted monthly series
    series = []
    for m in month_starts:
        rec = {"period_start": m.isoformat(), "params": {}}
        for p in params:
            # weighted sum across stations that have value
            num = 0.0
            denom = 0.0
            for s in station_info:
                w = float(s["weight_norm"])
                v = val.get((s["station_name"], m, p))
                if v is None:
                    continue
                num += w * v
                denom += w
            rec["params"][p] = (num / denom) if denom > 0 else None
        series.append(rec)

    # Overall mean across months (ignoring None)
    overall = {}
    for p in params:
        vals = [r["params"][p] for r in series if r["params"][p] is not None]
        overall[p] = sum(vals) / len(vals) if vals else None

    return {
        "point": {"lat": lat, "lon": lon},
        "method": method,
        "k": len(station_info),
        "stations": station_info,
        "granularity": "month",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "params": params,
        "series": series,
        "overall_mean": overall,
    }