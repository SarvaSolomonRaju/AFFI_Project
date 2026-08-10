"""Reprojects a depth/probability array (in the flood library's native CRS)
to a transparent WGS84 RGBA PNG the frontend can drop straight onto a
MapLibre map as an image overlay, plus the lat/lon bounds it needs to place
it. Shared by scripts/07_task4_probabilistic.py (the live per-cycle refresh)
and src/dashboard/interactive_map.py (the one-time Folium build) — both used
to duplicate this logic, which is how the live map's raster overlay ended up
silently stuck on whichever snapshot interactive_map.py was last run against.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from PIL import Image
from rasterio.warp import reproject, Resampling, calculate_default_transform


def reproject_to_wgs84(arr: np.ndarray, src_transform, src_crs):
    h, w = arr.shape
    left = src_transform.c
    top = src_transform.f
    right = left + w * src_transform.a
    bottom = top + h * src_transform.e
    dst_transform, dst_w, dst_h = calculate_default_transform(
        src_crs, "EPSG:4326", w, h, left, bottom, right, top
    )
    dst = np.zeros((dst_h, dst_w), dtype=np.float32)
    reproject(
        source=arr.astype(np.float32),
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs="EPSG:4326",
        resampling=Resampling.bilinear,
        src_nodata=0.0,
        dst_nodata=0.0,
    )
    W = dst_transform.c
    N = dst_transform.f
    E = W + dst_w * dst_transform.a
    S = N + dst_h * dst_transform.e
    return dst, (W, S, E, N)


def array_to_png(arr: np.ndarray, cmap_name: str, vmin: float, vmax: float,
                  out_png: Path, alpha_zero: bool = True) -> None:
    cmap = cm.get_cmap(cmap_name)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    rgba = (cmap(norm(arr)) * 255).astype(np.uint8)
    if alpha_zero:
        rgba[..., 3] = np.where(arr > 1e-6, 200, 0).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(out_png)


def write_live_map_overlays(likely: np.ndarray, poi: np.ndarray, ref_transform, ref_crs,
                             out_dir: Path, bounds_path: Path) -> None:
    """Refreshes _map_layer_today_likely.png / _map_layer_today_poi.png and
    merges their bounds into _map_layer_bounds.json, leaving any other keys
    already in that file (fema-100yr, population) untouched."""
    import json

    likely_wgs, likely_bounds = reproject_to_wgs84(likely, ref_transform, ref_crs)
    poi_wgs, poi_bounds = reproject_to_wgs84(poi, ref_transform, ref_crs)

    array_to_png(likely_wgs, "Blues", 0.05, max(float(likely.max()), 0.5),
                 out_dir / "_map_layer_today_likely.png")
    array_to_png(poi_wgs, "YlOrRd", 0.01, max(float(poi.max()), 0.05),
                 out_dir / "_map_layer_today_poi.png")

    manifest = json.loads(bounds_path.read_text()) if bounds_path.exists() else {}
    manifest["today-likely"] = {"west": likely_bounds[0], "south": likely_bounds[1],
                                 "east": likely_bounds[2], "north": likely_bounds[3]}
    manifest["today-poi"] = {"west": poi_bounds[0], "south": poi_bounds[1],
                              "east": poi_bounds[2], "north": poi_bounds[3]}
    bounds_path.write_text(json.dumps(manifest, indent=2))
