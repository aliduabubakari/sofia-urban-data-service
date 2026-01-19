from __future__ import annotations

import argparse
import time

from suds_core.db.engine import session_scope
from suds_core.geo.crs import parse_bbox
from suds_core.services.green_areas import green_areas_bbox
from suds_core.services.pedestrian import pedestrian_bbox
from suds_core.services.pois import pois_bbox
from suds_core.services.streets import streets_bbox

# You can also include trees/buildings from your existing services later.


DATASET_TO_FUNC = {
    "streets": streets_bbox,
    "pois": pois_bbox,
    "green_areas": green_areas_bbox,
    "pedestrian_network": pedestrian_bbox,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, choices=sorted(DATASET_TO_FUNC.keys()))
    parser.add_argument("--bbox", required=True, help="minx,miny,maxx,maxy (EPSG:4326 lon/lat)")
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--simplify-m", type=float, default=None, help="Simplify tolerance in meters (lines/polygons)")
    args = parser.parse_args()

    bbox = parse_bbox(args.bbox)
    func = DATASET_TO_FUNC[args.dataset]

    with session_scope() as session:
        t0 = time.perf_counter()
        fc = func(
            session,
            bbox=bbox,
            limit=args.limit,
            offset=args.offset,
            simplify_m=args.simplify_m,
        )
        dt_ms = (time.perf_counter() - t0) * 1000.0

    n = len(fc.get("features", []))
    print("\n=== SMOKE QUERY RESULT ===")
    print(f"dataset: {args.dataset}")
    print(f"bbox:    {args.bbox}")
    print(f"limit:   {args.limit}")
    print(f"offset:  {args.offset}")
    print(f"simplify_m: {args.simplify_m}")
    print(f"returned features: {n:,}")
    print(f"elapsed: {dt_ms:.2f} ms")
    print("==========================\n")


if __name__ == "__main__":
    main()