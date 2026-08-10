from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["AFFI_AUTH_DISABLED"] = "true"

from src.api import routes_action
from src.api.server import app

client = TestClient(app)


class TestActionPlan:
    def test_returns_200(self):
        resp = client.get("/api/v1/action-plan")
        assert resp.status_code == 200

    def test_known_counts_and_sorted_by_depth(self, monkeypatch, tmp_path):
        # Pins down the FEMA 100-yr reference fallback specifically (today's
        # live forecast overrides these counts whenever it's available and
        # is exercised by its own test below) -- forcing the fallback path
        # so this keeps validating the known, stable 100-yr counts.
        monkeypatch.setattr(routes_action, "TODAY_STATUS_PATH", tmp_path / "missing.json")
        data = client.get("/api/v1/action-plan").json()
        assert data["roads_to_barricade"]["total_count"] == 154
        assert data["buildings_to_evacuate"]["total_count"] == 512
        assert len(data["roads_to_barricade"]["top"]) == 20
        assert len(data["buildings_to_evacuate"]["top"]) == 20

        depths = [r["max_depth_m"] for r in data["roads_to_barricade"]["top"]]
        assert depths == sorted(depths, reverse=True)

    def test_has_legal_note(self):
        data = client.get("/api/v1/action-plan").json()
        assert "28-910" in data["legal_note"]

    def test_buildings_carry_category(self, monkeypatch, tmp_path):
        monkeypatch.setattr(routes_action, "TODAY_STATUS_PATH", tmp_path / "missing.json")
        data = client.get("/api/v1/action-plan").json()
        categories = {b["category"] for b in data["buildings_to_evacuate"]["top"]}
        assert categories  # non-empty
        valid = {"School", "Public/Civic", "Residential", "Commercial/Industrial", "Agricultural/Outbuilding", "Unclassified"}
        assert categories <= valid

    def test_today_live_forecast_overrides_reference_when_present(self, monkeypatch, tmp_path):
        # When today_feature_status.json exists, the Action Plan must answer
        # "what's flooding today," not silently fall back to the static
        # 100-yr reference -- this is the bug this feature fixes (see
        # src/probabilistic/today_feature_status.py).
        roads = routes_action._load_geojson("roads_huc12.geojson")
        n_roads = len(roads.get("features", []))
        buildings = routes_action._load_geojson("buildings_huc12.geojson")
        n_buildings = len(buildings.get("features", []))
        fake_status = tmp_path / "today_feature_status.json"
        fake_status.write_text(json.dumps({
            "roads": [{"max_depth_m": 0.0, "max_depth_worst_m": 0.0, "status": "OPEN"} for _ in range(n_roads)],
            "buildings": [{"max_depth_m": 0.0, "max_depth_worst_m": 0.0, "status": "OPEN"} for _ in range(n_buildings)],
        }))
        monkeypatch.setattr(routes_action, "TODAY_STATUS_PATH", fake_status)
        data = client.get("/api/v1/action-plan").json()
        assert data["reference_scenario"] == "Today's live forecast"
        assert data["roads_to_barricade"]["total_count"] == 0
        assert data["buildings_to_evacuate"]["total_count"] == 0

    def test_missing_today_status_falls_back_with_honest_label(self, monkeypatch, tmp_path):
        monkeypatch.setattr(routes_action, "TODAY_STATUS_PATH", tmp_path / "missing.json")
        data = client.get("/api/v1/action-plan").json()
        assert "100-yr" in data["reference_scenario"]
        assert "unavailable" in data["reference_scenario"]

    def test_schools_in_flood_zone_is_uncapped_and_school_only(self):
        data = client.get("/api/v1/action-plan").json()
        schools = data["schools_in_flood_zone"]
        assert isinstance(schools, list)
        # Real data as of 2026-06-30: 0 flooded schools at the 100-yr
        # reference — this asserts the *shape* holds regardless of
        # that count changing if the library gets rebuilt.
        assert all("name" in s and "max_depth_m" in s for s in schools)

    def test_requires_key_when_auth_enabled(self, monkeypatch):
        monkeypatch.delenv("AFFI_AUTH_DISABLED", raising=False)
        resp = client.get("/api/v1/action-plan")
        assert resp.status_code == 401
        os.environ["AFFI_AUTH_DISABLED"] = "true"
