"""Return-period scenario library for the Simulation Mode slider.

Single source of truth for "what would happen at a T-year storm" — used by
both the static dashboard generator (scripts/build_dashboard.py) and the
live API (/api/v1/simulation/*). Reprojects each return-period depth raster
in data/flood_library_real/ to WGS84 and writes a PNG overlay to
outputs/sim/, alongside the stats (Q, max depth, wet area) from the library
manifest.

Road/infrastructure-at-risk counts and alert/severity/probability labels
below are curated scenario metadata (not derived from the raster) — same
values previously hardcoded inline in build_dashboard.py.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

from common.paths import DATA_DIR, OUTPUTS_DIR

SIM_DIR = OUTPUTS_DIR / "sim"
DEFAULT_RETURN_PERIODS: tuple[int, ...] = (5, 10, 25, 50, 100, 200)

# Curated per-scenario metadata not present in the flood-map manifest.
_SCENARIO_META = {
    5:   {"roads_at_risk": 82,  "infra_at_risk": 4,  "alert_level": "YELLOW", "severity": "Minor",    "probability": "20%"},
    10:  {"roads_at_risk": 105, "infra_at_risk": 7,  "alert_level": "ORANGE", "severity": "Moderate", "probability": "10%"},
    25:  {"roads_at_risk": 132, "infra_at_risk": 10, "alert_level": "ORANGE", "severity": "Major",    "probability": "4%"},
    50:  {"roads_at_risk": 146, "infra_at_risk": 11, "alert_level": "RED",    "severity": "Major",    "probability": "2%"},
    100: {"roads_at_risk": 154, "infra_at_risk": 12, "alert_level": "RED",    "severity": "Severe",   "probability": "1%"},
    200: {"roads_at_risk": 162, "infra_at_risk": 14, "alert_level": "RED",    "severity": "Severe",   "probability": "0.5%"},
}


def _reproject_depth_to_png(tif_path: Path, out_png: Path, thumb_png: Path | None = None) -> bool:
    """Reproject a depth GeoTIFF to WGS84 and save as a colored PNG overlay.

    The creek channel only occupies ~1-2% of the full HUC-12 raster frame —
    real geography, not a bug — so a flood ribbon that reads perfectly fine
    on the full interactive map (which zooms/pans) becomes nearly invisible
    once scaled down to a ~180px scenario-card thumbnail. When thumb_png is
    given, also write a second PNG cropped tight to the wet-pixel bounding
    box (+ padding) so small preview cards actually show visible water
    instead of a few sub-pixel blue specks. out_png stays the full,
    correctly-georeferenced frame — only the thumbnail is cropped, and only
    for card-sized previews that don't need real coordinates.
    """
    import numpy as np
    import rasterio
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    from PIL import Image
    from rasterio.warp import reproject, Resampling, calculate_default_transform

    with rasterio.open(tif_path) as src:
        arr = np.nan_to_num(src.read(1), nan=0.0).astype(np.float32)
        src_crs, src_transform = src.crs, src.transform
        h, w = arr.shape
        left, top = src_transform.c, src_transform.f
        right = left + w * src_transform.a
        bottom = top + h * src_transform.e
        dst_transform, dst_w, dst_h = calculate_default_transform(
            src_crs, "EPSG:4326", w, h, left, bottom, right, top
        )
        dst = np.zeros((dst_h, dst_w), dtype=np.float32)
        reproject(
            source=arr, destination=dst,
            src_transform=src_transform, src_crs=src_crs,
            dst_transform=dst_transform, dst_crs="EPSG:4326",
            resampling=Resampling.bilinear,
            src_nodata=0.0, dst_nodata=0.0,
        )
    cmap = cm.get_cmap("Blues")
    norm = mcolors.Normalize(vmin=0, vmax=12, clip=True)
    rgba = (cmap(norm(dst)) * 255).astype("uint8")
    wet = dst > 0.05
    rgba[..., 3] = np.where(wet, 200, 0).astype("uint8")
    Image.fromarray(rgba, "RGBA").save(out_png)

    if thumb_png is not None:
        if wet.any():
            ys, xs = np.where(wet)
            y0, y1 = int(ys.min()), int(ys.max())
            x0, x1 = int(xs.min()), int(xs.max())
            pad_y = max(int((y1 - y0) * 0.25), 15)
            pad_x = max(int((x1 - x0) * 0.25), 15)
            y0, y1 = max(0, y0 - pad_y), min(rgba.shape[0], y1 + pad_y + 1)
            x0, x1 = max(0, x0 - pad_x), min(rgba.shape[1], x1 + pad_x + 1)
            crop = rgba[y0:y1, x0:x1].copy()

            # A real creek channel is a handful of pixels wide even after the
            # crop above — a bounding box around a wandering line still has
            # mostly-empty area inside it. Thickening the wet pixels here is
            # the same cartographic convention as drawing a highway many times
            # its true GIS width: legibility at small scale, not fabricated
            # extent. Dilation only touches this small preview thumbnail —
            # the full out_png used for the analytical/interactive map is
            # untouched pixel-for-pixel.
            from scipy.ndimage import binary_dilation, grey_dilation
            wet_crop = crop[..., 3] > 10
            dilated = binary_dilation(wet_crop, iterations=3)
            newly_wet = dilated & ~wet_crop
            if newly_wet.any():
                # Spread color into the newly-thickened ring via a max filter
                # over each channel so the thickened edge isn't just alpha
                # with no color underneath.
                for c in range(3):
                    crop[..., c] = grey_dilation(crop[..., c], size=(7, 7))
                crop[..., 3] = np.where(dilated, 200, 0).astype("uint8")
        else:
            crop = rgba
        Image.fromarray(crop, "RGBA").save(thumb_png)

    return True


def build_scenario_library(
    return_periods: Sequence[int] = DEFAULT_RETURN_PERIODS,
    write_pngs: bool = True,
) -> dict[int, dict]:
    """Build the T-year scenario dict: {T: {Q_cms, max_depth_m, wet_area_km2,
    roads_at_risk, infra_at_risk, alert_level, severity, probability, png_path}}.

    png_path is an absolute Path to outputs/sim/depth_T{T:03d}yr.png,
    written if write_pngs=True and not already present.
    """
    manifest_path = DATA_DIR / "flood_library_real" / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text())
    rp_stats = manifest.get("return_periods", {})
    files = manifest.get("files", {})

    if write_pngs:
        SIM_DIR.mkdir(parents=True, exist_ok=True)

    result: dict[int, dict] = {}
    for T in return_periods:
        tif_name = files.get(str(T))
        if not tif_name:
            continue
        tif_path = DATA_DIR / "flood_library_real" / tif_name
        if not tif_path.exists():
            continue

        stats = rp_stats.get(str(T), {})
        out_png = SIM_DIR / f"depth_T{T:03d}yr.png"
        thumb_png = SIM_DIR / f"depth_T{T:03d}yr_thumb.png"
        if write_pngs and (not out_png.exists() or not thumb_png.exists()):
            try:
                _reproject_depth_to_png(tif_path, out_png, thumb_png=thumb_png)
            except Exception:
                out_png = None
                thumb_png = None
        elif not out_png.exists():
            out_png = None
            thumb_png = None

        meta = _SCENARIO_META.get(T, {})

        # Population-at-risk — real WorldPop counts disaggregated onto this
        # scenario's own depth raster (see population_exposure.py). The
        # library's flood *extent* is fixed across T (only depth is Leopold-
        # scaled, per this module's docstring), so "exposed" barely moves —
        # the threshold cut is what actually distinguishes scenarios.
        pop_exposed = pop_life_safety = None
        try:
            import rasterio
            from common.population_exposure import population_at_risk

            with rasterio.open(tif_path) as src:
                depth_arr = src.read(1)
                pop_exposed = population_at_risk(depth_arr, src.transform, threshold_m=0.0)
                pop_life_safety = population_at_risk(depth_arr, src.transform, threshold_m=0.5)
        except Exception:
            pass

        result[T] = {
            "Q_cms": round(stats.get("Q_cms", 0)),
            "max_depth_m": round(stats.get("max_depth_m", 0.0), 2),
            "wet_area_km2": round(stats.get("wet_area_km2", 0.0), 4),
            "roads_at_risk": meta.get("roads_at_risk"),
            "infra_at_risk": meta.get("infra_at_risk"),
            "alert_level": meta.get("alert_level"),
            "severity": meta.get("severity"),
            "probability": meta.get("probability"),
            "population_exposed": pop_exposed,
            "population_life_safety": pop_life_safety,
            "png_path": out_png,
            "thumb_png_path": thumb_png,
        }
    return result
