from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["AFFI_AUTH_DISABLED"] = "true"

from src.api.server import app

client = TestClient(app)


class TestActionPlan:
    def test_returns_200(self):
        resp = client.get("/api/v1/action-plan")
        assert resp.status_code == 200

    def test_known_counts_and_sorted_by_depth(self):
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

    def test_requires_key_when_auth_enabled(self, monkeypatch):
        monkeypatch.delenv("AFFI_AUTH_DISABLED", raising=False)
        resp = client.get("/api/v1/action-plan")
        assert resp.status_code == 401
        os.environ["AFFI_AUTH_DISABLED"] = "true"
