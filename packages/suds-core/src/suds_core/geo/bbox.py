from __future__ import annotations

import math
from suds_core.geo.crs import BBox

def bbox_from_point_radius(lat: float, lon: float, radius_m: float) -> BBox:
    # Approx conversion: good enough for small radii like 300m–1000m
    dlat = radius_m / 111_320.0
    dlon = radius_m / (111_320.0 * math.cos(math.radians(lat)))
    return BBox(minx=lon - dlon, miny=lat - dlat, maxx=lon + dlon, maxy=lat + dlat)