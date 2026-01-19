from __future__ import annotations

from typing import Any, Dict, List, Optional

from geoalchemy2.elements import WKBElement
from shapely.geometry import Point
from sqlalchemy import select
from sqlalchemy.orm import Session

from suds_core.connectors.gate import GateClient
from suds_core.db.models import Stations
from suds_core.db.ingest import sanitize_json_value


def upsert_stations_from_gate(session: Session) -> Dict[str, Any]:
    client = GateClient()
    gate_stations = client.list_stations()

    created = 0
    updated = 0

    for st in gate_stations:
        # Build geom WKB (EPSG:4326)
        pt = Point(st.longitude, st.latitude)
        geom = WKBElement(pt.wkb, srid=4326)

        # Store full raw record + convenience fields
        props = sanitize_json_value(dict(st.raw))
        props["lat"] = st.latitude
        props["lon"] = st.longitude
        props["source"] = "gate"
        props["gate_variant"] = client.variant_name

        existing = session.execute(
            select(Stations).where(Stations.station_name == st.name)
        ).scalar_one_or_none()

        if existing is None:
            session.add(
                Stations(
                    station_name=st.name,
                    props=props,
                    geom=geom,
                )
            )
            created += 1
        else:
            existing.props = props
            existing.geom = geom
            updated += 1

    session.flush()
    return {
        "variant": client.variant_name,
        "fetched": len(gate_stations),
        "created": created,
        "updated": updated,
    }


def list_stations(session: Session) -> List[Dict[str, Any]]:
    rows = session.execute(select(Stations).order_by(Stations.station_name)).scalars().all()
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "station_name": r.station_name,
                "props": r.props,
            }
        )
    return out


def get_station(session: Session, station_name: str) -> Optional[Dict[str, Any]]:
    r = session.execute(select(Stations).where(Stations.station_name == station_name)).scalar_one_or_none()
    if r is None:
        return None
    return {"station_name": r.station_name, "props": r.props}

from sqlalchemy import func, select
from suds_core.geo.serialization import feature, feature_collection

def list_stations_geojson(session: Session) -> dict[str, Any]:
    rows = session.execute(
        select(
            Stations.id,
            Stations.station_name,
            Stations.props,
            func.ST_AsGeoJSON(Stations.geom).label("geom_geojson"),
        ).order_by(Stations.station_name)
    ).all()

    feats = []
    for r in rows:
        props = dict(r.props or {})
        props["station_name"] = r.station_name
        feats.append(feature(r.geom_geojson, props, fid=r.id))

    return feature_collection(feats)