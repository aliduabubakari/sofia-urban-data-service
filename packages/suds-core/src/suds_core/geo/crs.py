# packages/suds-core/src/suds_core/geo/crs.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class BBox:
    minx: float
    miny: float
    maxx: float
    maxy: float

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.minx, self.miny, self.maxx, self.maxy)


def parse_bbox(value: str) -> BBox:
    """
    Parse bbox from a string: "minx,miny,maxx,maxy" (lon/lat order in EPSG:4326).
    """
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must have 4 comma-separated values: minx,miny,maxx,maxy")

    minx, miny, maxx, maxy = map(float, parts)
    if minx >= maxx or miny >= maxy:
        raise ValueError("bbox invalid: ensure minx<maxx and miny<maxy")

    return BBox(minx=minx, miny=miny, maxx=maxx, maxy=maxy)