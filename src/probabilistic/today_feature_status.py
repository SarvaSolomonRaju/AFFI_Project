"""Tag roads/buildings/infrastructure against TODAY's actual live forecast
depth -- the same idea as scripts/16_tag_return_periods.py (which tags them
against the FEMA 5/10/25/50/100/200-yr library), but against today's real
best/likely/worst rasters instead of a hypothetical return period.

Without this, the map's default LIVE view and the Action Plan/Bulletin had
no way to answer "is anything flooding today" at the road/building level --
they fell back to the static FEMA 100-yr reference tagging baked in by
scripts/14_build_local_assets.py / scripts/15_build_infrastructure.py, which
reads as "everything's flooded" on a dry day. routes_action.py used to
disclose this as a known gap; this closes it.

Written once per forecast-generation run (scripts/07_task4_probabilistic.py)
to outputs/task4/today_feature_status.json, keyed by array index against
each source file's feature order -- so the API just reads a small JSON
instead of re-sampling rasters on every request.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.io import MemoryFile
from shapely.geometry import shape as shapely_shape
from shapely.ops import transform as shapely_transform
from pyproj import Transformer

from common.paths import DATA_DIR

LOCAL = DATA_DIR / "local_assets"
DEPTH_THRESHOLD_M = 0.05  # matches routes_map.py's _DEPTH_THRESHOLD_M

# Plain-language severity tiers, in meters -- the same human-scale bands
# DepthScaleReference.tsx already cites to the NWS "Turn Around Don't Drown"
# figures (0.5/1/2 ft = 0.15/0.3/0.6 m), so a road tagged "moderate" on the
# map means the same thing as "moderate" on the depth-scale panel. This
# replaces the old binary FLOODED/OPEN paint (every wet pixel above 2in
# rendered the identical solid red as a pixel under 14ft of water).
_SEVERITY_BANDS = [
    (DEPTH_THRESHOLD_M, "none"),
    (0.3, "minor"),      # up to ~1 ft: ankle-to-shin, a car can still cross
    (0.6, "moderate"),   # 1-2 ft: floats a car away (NWS TADD)
    (float("inf"), "severe"),  # 2 ft+: carries away most vehicles (NWS TADD)
]


def severity_tier(depth_m: float) -> str:
    for cutoff, tier in _SEVERITY_BANDS:
        if depth_m <= cutoff:
            return tier
    return "severe"

# (source file, label for "not flooded") -- FLOODED/OPEN for roads+buildings,
# FLOODED/SAFE for infrastructure, matching scripts/14 and scripts/15's own
# conventions exactly so nothing downstream has to special-case a new label.
_TARGETS = {
    "roads": ("roads_huc12.geojson", "OPEN"),
    "buildings": ("buildings_huc12.geojson", "OPEN"),
    "infrastructure": ("infrastructure.geojson", "SAFE"),
}


def _sample_max_depth(geom, src, n: int = 25) -> float:
    """Mirrors scripts/16_tag_return_periods.py's sampling: lines get n
    interpolated points, polygons/points get one representative point --
    max across samples so a feature counts as flooded if any part is
    underwater."""
    try:
        if geom.geom_type in ("LineString", "MultiLineString"):
            if geom.length <= 0:
                return 0.0
            pts = [geom.interpolate(t / (n - 1), normalized=True) for t in range(n)]
            xy = [(p.x, p.y) for p in pts]
        elif geom.geom_type in ("Polygon", "MultiPolygon", "Point", "MultiPoint"):
            c = geom.centroid if geom.geom_type != "Point" else geom
            xy = [(c.x, c.y)]
        else:
            return 0.0
        vals = [float(v[0]) for v in src.sample(xy, indexes=1)]
        vals = [0.0 if np.isnan(v) else v for v in vals]
        return float(max(vals)) if vals else 0.0
    except Exception:
        return 0.0


def _open_memory_dataset(memfile: MemoryFile, arr: np.ndarray, transform, crs) -> None:
    with memfile.open(
        driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
        dtype="float32", crs=crs, transform=transform,
    ) as ds:
        ds.write(arr.astype("float32"), 1)


def build_today_feature_status(likely: np.ndarray, worst: np.ndarray, transform, crs,
                                poi: np.ndarray | None = None) -> dict:
    """{"roads": [{"status", "severity", "max_depth_m", "max_depth_worst_m", "poi_pct"}, ...], ...}

    List order matches each source GeoJSON's own feature order exactly.
    `poi` is the Probability-of-Inundation raster (0-1, Pearson-Tukey
    weighted across best/likely/worst — src/probabilistic/risk_map.py) —
    sampled the same way as depth so each feature gets a real, ensemble-
    weighted percentage instead of a fabricated one.
    """
    result: dict[str, list[dict]] = {}
    likely_mem, worst_mem, poi_mem = MemoryFile(), MemoryFile(), (MemoryFile() if poi is not None else None)
    _open_memory_dataset(likely_mem, likely, transform, crs)
    _open_memory_dataset(worst_mem, worst, transform, crs)
    if poi_mem is not None:
        _open_memory_dataset(poi_mem, poi, transform, crs)
    try:
        with likely_mem.open() as likely_src, worst_mem.open() as worst_src:
            poi_src_cm = poi_mem.open() if poi_mem is not None else None
            try:
                # GeoJSON is WGS84; reproject each feature to the raster CRS with
                # pyproj+shapely rather than geopandas — geopandas' read_file goes
                # through fiona, and fiona 1.10 breaks geopandas 0.14 with
                # "module 'fiona' has no attribute 'path'", which silently killed
                # this whole step (and left the flood forecast stale) in the
                # container. shapely/pyproj carry no fiona dependency.
                to_raster = Transformer.from_crs("EPSG:4326", likely_src.crs, always_xy=True).transform
                for key, (fname, not_flooded_label) in _TARGETS.items():
                    path = LOCAL / fname
                    if not path.exists():
                        result[key] = []
                        continue
                    fc = json.loads(path.read_text())
                    features = fc.get("features", [])
                    rows = []
                    for feat in features:
                        geom_json = feat.get("geometry")
                        if not geom_json:
                            rows.append({
                                "max_depth_m": 0.0, "max_depth_worst_m": 0.0,
                                "status": not_flooded_label, "severity": "none", "poi_pct": 0,
                            })
                            continue
                        geom = shapely_transform(to_raster, shapely_shape(geom_json))
                        depth_likely = _sample_max_depth(geom, likely_src)
                        depth_worst = _sample_max_depth(geom, worst_src)
                        poi_frac = _sample_max_depth(geom, poi_src_cm) if poi_src_cm is not None else None
                        rows.append({
                            "max_depth_m": round(depth_likely, 4),
                            "max_depth_worst_m": round(depth_worst, 4),
                            "status": "FLOODED" if depth_likely > DEPTH_THRESHOLD_M else not_flooded_label,
                            "severity": severity_tier(depth_likely),
                            "poi_pct": round(poi_frac * 100) if poi_frac is not None else None,
                        })
                    result[key] = rows
            finally:
                if poi_src_cm is not None:
                    poi_src_cm.close()
    finally:
        likely_mem.close()
        worst_mem.close()
        if poi_mem is not None:
            poi_mem.close()
    return result


def write_today_feature_status(likely: np.ndarray, worst: np.ndarray, transform, crs, out_path: Path,
                                poi: np.ndarray | None = None) -> dict:
    data = build_today_feature_status(likely, worst, transform, crs, poi=poi)
    out_path.write_text(json.dumps(data))
    return data
