# packages/suds-core/src/suds_core/geo/serialization.py
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping


def feature(geometry_geojson_str: str, properties: Mapping[str, Any], fid: Any | None = None) -> dict[str, Any]:
    geom = json.loads(geometry_geojson_str) if geometry_geojson_str else None
    out: dict[str, Any] = {
        "type": "Feature",
        "geometry": geom,
        "properties": dict(properties),
    }
    if fid is not None:
        out["id"] = fid
    return out


def feature_collection(features: Iterable[dict[str, Any]], *, crs_epsg: int = 4326) -> dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": list(features),
        "crs": {
            "type": "name",
            "properties": {"name": f"EPSG:{crs_epsg}"},
        },
    }