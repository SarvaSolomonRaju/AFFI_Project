from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["AFFI_AUTH_DISABLED"] = "true"

from src.api.server import app

client = TestClient(app)


class TestMapConfig:
    def test_returns_200(self):
        resp = client.get("/api/v1/map/config")
        assert resp.status_code == 200

    def test_has_bbox_and_markers(self):
        data = client.get("/api/v1/map/config").json()
        assert set(data["bbox"].keys()) == {"north", "south", "east", "west"}
        assert len(data["reference_markers"]) == 3
        assert data["available_layers"] == [
            "nfhl-zones", "bfe-lines", "creek-centerline", "roads", "buildings", "infrastructure", "evac-routes",
        ]
        assert data["available_rasters"] == ["fema-100yr", "today-likely", "today-poi", "population"]

    def test_has_raster_bounds_for_frontend_overlay_placement(self):
        data = client.get("/api/v1/map/config").json()
        bounds = data["raster_bounds"]["fema-100yr"]
        assert set(bounds.keys()) == {"west", "south", "east", "north"}
        assert bounds["west"] < bounds["east"]
        assert bounds["south"] < bounds["north"]


class TestMapLayers:
    @pytest.mark.parametrize(
        "layer,min_features",
        [
            ("nfhl-zones", 92),
            ("bfe-lines", 85),
            ("creek-centerline", 8),
            ("roads", 324),
            ("buildings", 1345),
            ("infrastructure", 19),
        ],
    )
    def test_known_layer_returns_geojson(self, layer, min_features):
        resp = client.get(f"/api/v1/map/layers/{layer}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "FeatureCollection"
        assert len(data["features"]) == min_features

    def test_unknown_layer_returns_404(self):
        resp = client.get("/api/v1/map/layers/not-a-real-layer")
        assert resp.status_code == 404

    def test_buildings_layer_has_category_injected(self):
        data = client.get("/api/v1/map/layers/buildings").json()
        categories = {f["properties"]["category"] for f in data["features"]}
        assert "School" in categories
        assert "Unclassified" in categories
        # Every building got a category — none silently skipped.
        assert all("category" in f["properties"] for f in data["features"])

    def test_other_layers_not_mutated_with_category(self):
        # Only buildings gets the transform — roads/zones/etc. stay a
        # raw passthrough, no unexpected extra property.
        data = client.get("/api/v1/map/layers/roads").json()
        assert "category" not in data["features"][0]["properties"]


class TestMapRasters:
    @pytest.mark.parametrize("layer", ["fema-100yr", "today-likely", "today-poi"])
    def test_known_raster_returns_png(self, layer):
        resp = client.get(f"/api/v1/map/raster/{layer}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"

    def test_unknown_raster_returns_404(self):
        resp = client.get("/api/v1/map/raster/not-a-real-raster")
        assert resp.status_code == 404


class TestSimulationScenarios:
    def test_returns_all_return_periods(self):
        resp = client.get("/api/v1/simulation/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert data["return_periods_yr"] == [5, 10, 25, 50, 100, 200]
        assert set(data["scenarios"].keys()) == {"5", "10", "25", "50", "100", "200"}

    def test_scenario_has_expected_fields(self):
        data = client.get("/api/v1/simulation/scenarios").json()
        s100 = data["scenarios"]["100"]
        assert s100["Q_cms"] > 0
        assert s100["max_depth_m"] > 0
        assert s100["alert_level"] in ("YELLOW", "ORANGE", "RED")
        assert s100["raster_url"] == "/api/v1/simulation/raster/100"

    def test_raster_for_each_scenario_is_servable(self):
        for T in (5, 10, 25, 50, 100, 200):
            resp = client.get(f"/api/v1/simulation/raster/{T}")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "image/png"

    def test_unknown_return_period_raster_404s(self):
        resp = client.get("/api/v1/simulation/raster/999")
        assert resp.status_code == 404


class TestAuthEnforced:
    def test_map_endpoints_require_key_when_auth_enabled(self, monkeypatch):
        monkeypatch.delenv("AFFI_AUTH_DISABLED", raising=False)
        resp = client.get("/api/v1/map/layers/nfhl-zones")
        assert resp.status_code == 401
        os.environ["AFFI_AUTH_DISABLED"] = "true"


class TestElevation:
    def test_point_inside_watershed_returns_elevation(self):
        resp = client.get("/api/v1/map/elevation?lat=31.5393&lon=-110.7548")
        assert resp.status_code == 200
        data = resp.json()
        assert data["elevation_m"] is not None
        assert 1000 < data["elevation_m"] < 2500  # sane range for this AZ watershed

    def test_point_with_return_period_includes_flood_depth(self):
        resp = client.get("/api/v1/map/elevation?lat=31.5393&lon=-110.7548&return_period=100")
        assert resp.status_code == 200
        data = resp.json()
        assert data["return_period_yr"] == 100
        assert data["flood_depth_m"] is not None
        assert data["flood_depth_m"] >= 0

    def test_point_outside_watershed_400s(self):
        resp = client.get("/api/v1/map/elevation?lat=0&lon=0")
        assert resp.status_code == 400

    def test_missing_query_params_422s(self):
        resp = client.get("/api/v1/map/elevation")
        assert resp.status_code == 422

    def test_evac_routes_layer_is_servable(self):
        resp = client.get("/api/v1/map/layers/evac-routes")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["features"]) == 3

    def test_population_raster_is_servable(self):
        resp = client.get("/api/v1/map/raster/population")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
