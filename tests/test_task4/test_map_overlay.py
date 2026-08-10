"""write_live_map_overlays (src/probabilistic/map_overlay.py) -- pins that
the live scheduler cycle refreshes the map's raster overlay PNGs + bounds
every run, rather than only once via the manual src/dashboard/interactive_map.py
build (the bug this closes: the map's blue water overlay was frozen on
whatever snapshot that manual script last produced)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.probabilistic.map_overlay import write_live_map_overlays


def test_writes_pngs_and_merges_bounds_without_clobbering_existing_keys(tmp_path):
    transform = from_origin(-110.8, 31.6, 10.0, 10.0)
    crs = "EPSG:32612"  # UTM 12N, a real projected CRS the flood library uses
    likely = np.ones((20, 20), dtype=np.float32) * 0.6
    poi = np.ones((20, 20), dtype=np.float32) * 0.7

    bounds_path = tmp_path / "_map_layer_bounds.json"
    bounds_path.write_text(json.dumps({"fema-100yr": {"west": -1, "south": -1, "east": 1, "north": 1}}))

    write_live_map_overlays(likely, poi, transform, crs, out_dir=tmp_path, bounds_path=bounds_path)

    assert (tmp_path / "_map_layer_today_likely.png").exists()
    assert (tmp_path / "_map_layer_today_poi.png").exists()

    manifest = json.loads(bounds_path.read_text())
    assert "fema-100yr" in manifest  # untouched
    assert "today-likely" in manifest
    assert "today-poi" in manifest
    assert manifest["today-likely"]["west"] < manifest["today-likely"]["east"]
    assert manifest["today-likely"]["south"] < manifest["today-likely"]["north"]
