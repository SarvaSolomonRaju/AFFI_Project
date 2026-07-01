#!/usr/bin/env python3
"""11_acquire_3dep_dem.py
Download USGS 3DEP 10-m DEM for HUC-12 150503010204 (Sonoita Creek-Patagonia)
using py3dep. Saves a GeoTIFF in projected meters (UTM 12N, EPSG:32612)."""
import json, sys
from pathlib import Path
import numpy as np
import geopandas as gpd
from shapely.geometry import box
import py3dep
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform

OUT = Path("data/terrain"); OUT.mkdir(parents=True, exist_ok=True)
HUC12 = "150503010204"
BBOX = (-110.85, 31.46, -110.65, 31.62)  # WGS84

def main():
    print(f"[info] py3dep get_dem bbox={BBOX} res=10m")
    geom = box(*BBOX)
    try:
        dem = py3dep.get_dem(geom, resolution=10, crs="EPSG:4326")
    except Exception as e:
        print(f"[warn] 10m failed ({e}); trying 30m...")
        dem = py3dep.get_dem(geom, resolution=30, crs="EPSG:4326")
    print(f"[info] DEM shape={dem.shape}, crs={dem.rio.crs}, res={dem.rio.resolution()}")
    # Save WGS84 DEM
    src_path = OUT/"dem_huc12_wgs84.tif"
    dem.rio.to_raster(src_path, compress="deflate")
    print(f"[ok] wrote {src_path}")
    # Reproject to UTM 12N
    dst_crs = "EPSG:32612"
    with rasterio.open(src_path) as src:
        transform, w, h = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds, resolution=10)
        kwargs = src.meta.copy()
        kwargs.update({"crs": dst_crs, "transform": transform, "width": w, "height": h, "compress":"deflate"})
        dst_path = OUT/"dem_huc12_utm12n_10m.tif"
        with rasterio.open(dst_path, "w", **kwargs) as dst:
            reproject(rasterio.band(src,1), rasterio.band(dst,1),
                      src_transform=src.transform, src_crs=src.crs,
                      dst_transform=transform, dst_crs=dst_crs, resampling=Resampling.bilinear)
    print(f"[ok] wrote {dst_path}")
    with rasterio.open(dst_path) as r:
        a = r.read(1, masked=True)
        stats = {"min_m": float(a.min()), "max_m": float(a.max()),
                 "mean_m": float(a.mean()), "shape":list(a.shape),
                 "pixel_size_m":[float(abs(r.transform.a)), float(abs(r.transform.e))],
                 "crs":str(r.crs), "bounds":list(r.bounds)}
    (OUT/"dem_manifest.json").write_text(json.dumps({
        "source":"USGS 3DEP (py3dep)","huc12":HUC12,"bbox_wgs84":list(BBOX),
        "files":["dem_huc12_wgs84.tif","dem_huc12_utm12n_10m.tif"],
        "stats_utm":stats}, indent=2))
    print(json.dumps(stats, indent=2))
    return 0

if __name__ == "__main__": sys.exit(main())
