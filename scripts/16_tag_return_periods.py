#!/usr/bin/env python3
"""
scripts/16_tag_return_periods.py
=================================

roads_huc12.geojson, buildings_huc12.geojson, and infrastructure.geojson
were only ever tagged against the FEMA 100-yr reference flood
(scripts/14_build_local_assets.py, scripts/15_build_infrastructure.py) —
every "will this building/road flood" answer on the map was silently
answered "...at the 100-yr event" even when a user is exploring a 5-yr
or 200-yr what-if scenario, with no way to tell.

data/flood_library_real/ already has a real depth raster for every
return period the rest of the app uses (5/10/25/50/100/200-yr, the same
set as src/probabilistic/scenarios.py's DEFAULT_RETURN_PERIODS) — this
script re-samples the existing feature geometries (no OSM re-download)
against each one and adds a `depth_by_rp` property:
    {"5": 0.0, "10": 0.3, "25": 1.1, ...}
so the map API can answer "flooded at T-year event?" for whichever
scenario is currently selected, not just the 100-yr default. Existing
`max_depth_m` / `flooded_100yr` / `status` fields are left untouched for
backward compatibility.

Run:  python scripts/16_tag_return_periods.py
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LIB_DIR = DATA / "flood_library_real"
LOCAL = DATA / "local_assets"

RETURN_PERIODS = (5, 10, 25, 50, 100, 200)  # matches scenarios.py DEFAULT_RETURN_PERIODS

_TARGETS = [
    LOCAL / "roads_huc12.geojson",
    LOCAL / "buildings_huc12.geojson",
    LOCAL / "infrastructure.geojson",
]


def _tif_for(rp: int) -> Path:
    manifest = json.loads((LIB_DIR / "manifest.json").read_text())
    fname = manifest["files"][str(rp)]
    return LIB_DIR / fname


def sample_max_depth(geom_proj, src, n=25) -> float:
    """Same sampling strategy as scripts/14_build_local_assets.py —
    lines get n interpolated points, polygons/points get one representative
    point, and we take the max so a road/building counts as flooded if
    ANY part of it is under water."""
    try:
        if geom_proj.geom_type in ("LineString", "MultiLineString"):
            if geom_proj.length <= 0:
                return 0.0
            pts = [geom_proj.interpolate(t / (n - 1), normalized=True) for t in range(n)]
            xy = [(p.x, p.y) for p in pts]
        elif geom_proj.geom_type in ("Polygon", "MultiPolygon", "Point", "MultiPoint"):
            c = geom_proj.centroid if geom_proj.geom_type != "Point" else geom_proj
            xy = [(c.x, c.y)]
        else:
            return 0.0
        vals = []
        for v in src.sample(xy, indexes=1):
            x = float(v[0])
            if np.isnan(x):
                x = 0.0
            vals.append(x)
        return float(max(vals)) if vals else 0.0
    except Exception:
        return 0.0


def tag_file(path: Path) -> None:
    if not path.exists():
        print(f"[skip] {path.name} not found")
        return

    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    if len(gdf) == 0:
        print(f"[skip] {path.name} has no features")
        return

    depth_by_rp: dict[int, list[float]] = {rp: [] for rp in RETURN_PERIODS}

    for rp in RETURN_PERIODS:
        tif_path = _tif_for(rp)
        with rasterio.open(tif_path) as src:
            gdf_proj = gdf.to_crs(src.crs)
            depth_by_rp[rp] = [sample_max_depth(g, src) for g in gdf_proj.geometry]
        print(f"  [{path.name}] T={rp}yr: {sum(1 for d in depth_by_rp[rp] if d > 0.05)}/{len(gdf)} features flooded")

    gdf["depth_by_rp"] = [
        {str(rp): round(depth_by_rp[rp][i], 4) for rp in RETURN_PERIODS}
        for i in range(len(gdf))
    ]
    # geopandas can't serialize a dict column straight to GeoJSON via to_file
    # (it tries to write it as a shapefile-safe scalar) — build the
    # FeatureCollection by hand instead, reusing gdf's own geometry
    # serialization so nothing else about the file's shape changes.
    raw = json.loads(gdf.to_json())
    for feature, depth_map in zip(raw["features"], gdf["depth_by_rp"]):
        feature["properties"]["depth_by_rp"] = depth_map
    path.write_text(json.dumps(raw))
    print(f"[OK] {path.name} — {len(gdf)} features tagged across {len(RETURN_PERIODS)} return periods")


def main():
    print(f"[info] return periods: {RETURN_PERIODS}")
    for path in _TARGETS:
        tag_file(path)


if __name__ == "__main__":
    main()
