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


def _reproject_depth_to_png(tif_path: Path, out_png: Path) -> bool:
    """Reproject a depth GeoTIFF to WGS84 and save as a colored PNG overlay."""
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
    rgba[..., 3] = np.where(dst > 0.05, 200, 0).astype("uint8")
    Image.fromarray(rgba, "RGBA").save(out_png)
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
        if write_pngs and not out_png.exists():
            try:
                _reproject_depth_to_png(tif_path, out_png)
            except Exception:
                out_png = None
        elif not out_png.exists():
            out_png = None

        meta = _SCENARIO_META.get(T, {})
        result[T] = {
            "Q_cms": round(stats.get("Q_cms", 0)),
            "max_depth_m": round(stats.get("max_depth_m", 0.0), 2),
            "wet_area_km2": round(stats.get("wet_area_km2", 0.0), 4),
            "roads_at_risk": meta.get("roads_at_risk"),
            "infra_at_risk": meta.get("infra_at_risk"),
            "alert_level": meta.get("alert_level"),
            "severity": meta.get("severity"),
            "probability": meta.get("probability"),
            "png_path": out_png,
        }
    return result
