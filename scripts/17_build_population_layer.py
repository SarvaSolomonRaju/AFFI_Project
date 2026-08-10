#!/usr/bin/env python3
"""
scripts/17_build_population_layer.py
=====================================

Clips WorldPop's free, no-API-key USA population-density GeoTIFF
(data/population/usa_ppp_2020_1km.tif — downloaded once from
data.worldpop.org, 1km resolution, 2020 estimate) to the Upper Sonoita
Creek HUC-12 bounding box and renders it as a colored PNG overlay, the
same convention as the flood depth rasters (src/probabilistic/scenarios.py)
so it drops into the existing map raster pipeline unchanged.

Real population counts, not a fabricated overlay — 1km resolution is
coarse for a ~144 km^2 watershed (roughly 12x12 grid cells), but it is
genuine WorldPop data, not invented.

Run:  python scripts/17_build_population_layer.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC_TIF = ROOT / "data" / "population" / "usa_ppp_2020_1km.tif"
OUT_DIR = ROOT / "outputs"
OUT_PNG = OUT_DIR / "_map_layer_population.png"
BOUNDS_JSON = OUT_DIR / "_map_layer_bounds.json"

# Same HUC-12 bounding box used throughout this project (config/watersheds,
# src/api/routes_map.py reference markers).
BBOX = {"north": 31.85, "south": 31.47, "east": -110.50, "west": -110.90}


def main():
    if not SRC_TIF.exists():
        raise SystemExit(f"Population source raster not found: {SRC_TIF}\n"
                          f"Download from https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/USA/usa_ppp_2020_1km_Aggregated.tif")

    with rasterio.open(SRC_TIF) as src:
        window = rasterio.windows.from_bounds(
            BBOX["west"], BBOX["south"], BBOX["east"], BBOX["north"], src.transform
        )
        arr = src.read(1, window=window)
        nodata = src.nodata
        win_transform = src.window_transform(window)

    arr = np.where(arr == nodata, 0.0, arr).astype(np.float32)
    arr = np.nan_to_num(arr, nan=0.0)
    arr = np.clip(arr, 0, None)

    print(f"[info] clipped population grid: {arr.shape}, "
          f"total pop (sum of cells) ~= {arr.sum():.0f}, max cell = {arr.max():.1f}")

    # Population per km^2 (source cells are already ~1km, so this is close
    # to per-cell count; kept as a density-style color ramp either way).
    cmap = cm.get_cmap("YlOrRd")
    vmax = max(float(np.percentile(arr[arr > 0], 95)) if (arr > 0).any() else 1.0, 1.0)
    norm = mcolors.Normalize(vmin=0, vmax=vmax, clip=True)
    rgba = (cmap(norm(arr)) * 255).astype("uint8")
    rgba[..., 3] = np.where(arr > 0.5, 190, 0).astype("uint8")  # transparent where ~nobody lives

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgba, "RGBA").save(OUT_PNG)
    print(f"[OK] wrote {OUT_PNG}")

    # Register bounds for the frontend the same way every other raster
    # layer's bounds are registered (outputs/_map_layer_bounds.json, read
    # by /api/v1/map/config).
    bounds_data = json.loads(BOUNDS_JSON.read_text()) if BOUNDS_JSON.exists() else {}
    h, w = arr.shape
    left, top = win_transform.c, win_transform.f
    right = left + w * win_transform.a
    bottom = top + h * win_transform.e
    bounds_data["population"] = {"west": left, "south": bottom, "east": right, "north": top}
    BOUNDS_JSON.write_text(json.dumps(bounds_data, indent=2))
    print(f"[OK] registered bounds in {BOUNDS_JSON}")


if __name__ == "__main__":
    main()
