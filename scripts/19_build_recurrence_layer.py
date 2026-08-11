"""Build the inundation-frequency ("how often does this flood") map layer.

Google Flood Hub shows an "inundation history" layer — how often an area has
been under water. We build the same idea from the flood-map library instead of
satellite history: for every pixel, find the SMALLEST return period at which it
floods. A spot that already floods in a 2-year event floods often (~50% chance
any given year); one that only floods at 100-year floods rarely (~1%). The pixel
value is that annual-exceedance chance, so the color ramp reads "deep = floods
often, pale = floods rarely, transparent = essentially never."

This is derived purely from the static return-period library, so unlike the
live overlays it does not change with the daily forecast — run it once (or
whenever the library is rebuilt), not every cycle.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
for p in (str(ROOT), str(ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from probabilistic.map_overlay import reproject_to_wgs84, array_to_png

LIB_DIR = ROOT / "data" / "flood_library_real"
OUT_DIR = ROOT / "outputs"
BOUNDS_PATH = OUT_DIR / "_map_layer_bounds.json"
WET_THRESHOLD_M = 0.15  # ~0.5 ft — a depth that actually matters underfoot


def main() -> int:
    manifest = json.loads((LIB_DIR / "manifest.json").read_text())
    rp_files = manifest["files"]  # {"2": "depth_T2yr_...tif", ...}
    return_periods = sorted(int(rp) for rp in rp_files)

    # smallest return period at which each pixel is wet (0 = never wet in range)
    min_rp = None
    transform = crs = None
    for rp in return_periods:
        with rasterio.open(LIB_DIR / rp_files[str(rp)]) as src:
            depth = np.nan_to_num(src.read(1).astype(np.float32), nan=0.0)
            if transform is None:
                transform, crs = src.transform, src.crs
                min_rp = np.zeros(depth.shape, dtype=np.float32)
        wet = depth > WET_THRESHOLD_M
        # assign this RP only where not already assigned a (smaller) one
        newly = wet & (min_rp == 0)
        min_rp[newly] = rp

    # annual-exceedance chance = 1/RP (2yr -> 0.5, 100yr -> 0.01); 0 where never
    freq = np.zeros_like(min_rp)
    np.divide(1.0, min_rp, out=freq, where=min_rp > 0)
    freq = freq.astype(np.float32)

    freq_wgs, bounds = reproject_to_wgs84(freq, transform, crs)
    # YlOrRd: high chance (frequent) -> deep red, low chance (rare) -> pale.
    # vmax 0.5 = the 2-year (most-frequent) end of the scale.
    array_to_png(freq_wgs, "YlOrRd", 0.0, 0.5, OUT_DIR / "_map_layer_recurrence.png")

    manifest_bounds = json.loads(BOUNDS_PATH.read_text()) if BOUNDS_PATH.exists() else {}
    manifest_bounds["recurrence"] = {
        "west": bounds[0], "south": bounds[1], "east": bounds[2], "north": bounds[3],
    }
    BOUNDS_PATH.write_text(json.dumps(manifest_bounds, indent=2))

    wet_px = int((min_rp > 0).sum())
    print(f"[recurrence] wrote _map_layer_recurrence.png — {wet_px} wet pixels "
          f"across return periods {return_periods}")
    print(f"[recurrence] bounds merged into {BOUNDS_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
