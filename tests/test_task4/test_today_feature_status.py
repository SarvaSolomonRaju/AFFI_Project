"""Per-feature severity tier + Probability-of-Inundation sampling
(src/probabilistic/today_feature_status.py) -- pins the graduated severity
that replaced the old binary FLOODED/OPEN paint, and that poi_pct is a real
sample of the PT-weighted PoI raster, not a fabricated number."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.probabilistic.today_feature_status import severity_tier, build_today_feature_status


class TestSeverityTier:
    def test_dry_is_none(self):
        assert severity_tier(0.0) == "none"

    def test_ankle_is_minor(self):
        assert severity_tier(0.2) == "minor"

    def test_floats_a_car_is_moderate(self):
        assert severity_tier(0.4) == "moderate"

    def test_carries_away_vehicles_is_severe(self):
        assert severity_tier(1.5) == "severe"


class TestBuildTodayFeatureStatus:
    def test_poi_pct_reflects_real_raster_not_fabricated(self, tmp_path, monkeypatch):
        # A 10x10 grid, all wet in "likely" -> PoI should read back as 100
        # at the one point we sample, not some constant/global figure.
        transform = from_origin(-110.7, 31.55, 0.0001, 0.0001)
        crs = "EPSG:4326"
        likely = np.ones((10, 10), dtype=np.float32) * 0.4
        worst = np.ones((10, 10), dtype=np.float32) * 0.8
        poi = np.ones((10, 10), dtype=np.float32) * 0.75

        local = tmp_path / "local_assets"
        local.mkdir()
        # One road point sitting inside the raster footprint.
        road_fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "LineString", "coordinates": [[-110.6996, 31.5496], [-110.6994, 31.5494]]},
            }],
        }
        (local / "roads_huc12.geojson").write_text(__import__("json").dumps(road_fc))

        import src.probabilistic.today_feature_status as mod
        monkeypatch.setattr(mod, "LOCAL", local)

        out = build_today_feature_status(likely, worst, transform, crs, poi=poi)
        row = out["roads"][0]
        assert row["poi_pct"] == 75
        assert row["severity"] == "moderate"
        assert row["status"] == "FLOODED"
