from __future__ import annotations

import datetime as dt
from typing import Any, Dict

from geoalchemy2.elements import WKBElement
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from suds_core.connectors.citylab import CityLabClient
from suds_core.db.models import CityLabStation


def upsert_citylab_stations(session: Session) -> dict[str, Any]:
    client = CityLabClient()
    stations = client.list_stations()

    created = 0
    updated = 0

    for st in stations:
        ext_id = int(st["id"])
        name = str(st.get("name"))
        stype = str(st.get("stationType"))
        lat = float(st.get("latitude"))
        lon = float(st.get("longitude"))

        geom = WKBElement(Point(lon, lat).wkb, srid=4326)

        existing = session.execute(
            select(CityLabStation).where(CityLabStation.external_id == ext_id)
        ).scalar_one_or_none()

        if existing is None:
            session.add(
                CityLabStation(
                    external_id=ext_id,
                    name=name,
                    station_type=stype,
                    address=st.get("address"),
                    operator=st.get("operator"),
                    model=st.get("model"),
                    serial_number=st.get("serialNumber"),
                    props=st,
                    geom=geom,
                )
            )
            created += 1
        else:
            existing.name = name
            existing.station_type = stype
            existing.address = st.get("address")
            existing.operator = st.get("operator")
            existing.model = st.get("model")
            existing.serial_number = st.get("serialNumber")
            existing.props = st
            existing.geom = geom
            updated += 1

    session.flush()
    return {"fetched": len(stations), "created": created, "updated": updated}