from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd

try:
    import fiona
except Exception:
    fiona = None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", required=True, help="Path to dataset (gpkg/geojson/shp)")
    parser.add_argument("--layer", default=None, help="Layer name for GPKG (optional)")
    args = parser.parse_args()

    path = Path(args.path)
    layer = args.layer

    if fiona and path.suffix.lower() == ".gpkg" and layer is None:
        layers = fiona.listlayers(str(path))
        print(f"Layers in {path.name}: {layers}")

    gdf = gpd.read_file(str(path), layer=layer)
    print("---- SOURCE INSPECTION ----")
    print(f"Path: {path}")
    print(f"Layer: {layer}")
    print(f"Rows: {len(gdf):,}")
    print(f"CRS: {gdf.crs}")
    print(f"Geom types: {gdf.geometry.geom_type.value_counts().to_dict()}")
    print(f"Columns: {list(gdf.columns)}")
    print("---------------------------")


if __name__ == "__main__":
    main()