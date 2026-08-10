"""Population-at-risk: real WorldPop counts, disaggregated onto the flood grid.

Every depth raster in this project (data/flood_library_real/*.tif, and the
today/live forecast in outputs/task4/today_rasters.npz) shares the same 10m
EPSG:32612 grid. WorldPop (data/population/usa_ppp_2020_1km.tif) is real
gridded population — not fabricated — but at 1km resolution, so each source
cell is disaggregated into people-per-m^2 (assuming uniform density within
that cell, the standard assumption for this class of product) before being
resampled onto the 10m grid and summed over the flooded pixels. Returns None
rather than a fabricated 0 when the source raster isn't present.
"""
from __future__ import annotations

import math
from functools import lru_cache

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.warp import Resampling, reproject, transform_bounds
from rasterio.windows import from_bounds

from common.paths import DATA_DIR

POP_TIF = DATA_DIR / "population" / "usa_ppp_2020_1km.tif"

# Same grid every flood_library_real/*.tif and today_rasters.npz array is on.
FLOOD_CRS = CRS.from_epsg(32612)

# Upper Sonoita Creek HUC-12 centroid — used only to convert the WorldPop
# source pixel's lat/lon degrees to an approximate area in meters (deg->m
# conversion depends on latitude; this basin spans well under a degree, so
# one reference latitude is accurate enough for this disaggregation).
_HUC12_LAT = 31.66
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(_HUC12_LAT))


@lru_cache(maxsize=4)
def _people_per_pixel_on_grid(dst_transform, dst_shape: tuple[int, int]) -> np.ndarray | None:
    """WorldPop reprojected onto the given 10m grid, in people-per-dest-pixel.

    Every return-period scenario (and the live "today" forecast) shares the
    exact same 10m grid, so without this cache a single /simulation/scenarios
    request reprojects the full CONUS-scale WorldPop raster 6 times over --
    ~19s measured before caching. Cached per-process since the grid never
    changes at runtime.
    """
    if not POP_TIF.exists():
        return None

    with rasterio.open(POP_TIF) as src:
        # usa_ppp_2020_1km.tif is a CONUS-scale raster (43072x6298, ~2.2GB as
        # float64) but every flood grid this function is ever called with is
        # one ~20x20km HUC-12 watershed. Reading the whole file (as this used
        # to) allocates several full-CONUS float64 copies in a row --
        # ru_maxrss measured at ~6.8GB, which reliably SIGKILLs the Task 4
        # scheduler subprocess under Docker's memory ceiling. Read only the
        # small source window covering the destination grid instead, padded
        # by a couple source pixels so bilinear resampling has edge context.
        dst_left, dst_bottom, dst_right, dst_top = rasterio.transform.array_bounds(
            dst_shape[0], dst_shape[1], dst_transform)
        src_left, src_bottom, src_right, src_top = transform_bounds(
            FLOOD_CRS, src.crs, dst_left, dst_bottom, dst_right, dst_top)
        pad = 2 * max(abs(src.transform.a), abs(src.transform.e))
        window = from_bounds(
            src_left - pad, src_bottom - pad, src_right + pad, src_top + pad,
            transform=src.transform,
        ).round_offsets().round_lengths()
        window = window.intersection(rasterio.windows.Window(0, 0, src.width, src.height))

        arr = src.read(1, window=window).astype(np.float64)
        if src.nodata is not None:
            arr = np.where(arr == src.nodata, 0.0, arr)
        np.nan_to_num(arr, copy=False, nan=0.0)
        np.clip(arr, 0, None, out=arr)

        px_w_deg, px_h_deg = abs(src.transform.a), abs(src.transform.e)
        src_pixel_area_m2 = (px_w_deg * _M_PER_DEG_LON) * (px_h_deg * _M_PER_DEG_LAT)
        density = arr / src_pixel_area_m2  # people per m^2, disaggregated

        window_transform = src.window_transform(window)
        dst_density = np.zeros(dst_shape, dtype=np.float64)
        reproject(
            source=density,
            destination=dst_density,
            src_transform=window_transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=FLOOD_CRS,
            resampling=Resampling.bilinear,
            src_nodata=0.0,
            dst_nodata=0.0,
        )

    dst_pixel_area_m2 = abs(dst_transform.a) * abs(dst_transform.e)
    return dst_density * dst_pixel_area_m2


def population_at_risk(depth_m: np.ndarray, dst_transform, threshold_m: float = 0.0) -> float | None:
    """Sum of exposed population where depth_m > threshold_m.

    None (never a fabricated 0) if the WorldPop source raster is missing.
    """
    people_per_pixel = _people_per_pixel_on_grid(dst_transform, depth_m.shape)
    if people_per_pixel is None:
        return None
    mask = np.nan_to_num(depth_m, nan=0.0) > threshold_m
    return round(float(people_per_pixel[mask].sum()))
