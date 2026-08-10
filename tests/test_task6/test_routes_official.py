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


class TestOfficialAlerts:
    def test_returns_200(self):
        # Hits the real NWS API; accept a clean unavailable response too so
        # the test isn't flaky on a network hiccup.
        resp = client.get("/api/v1/official-alerts")
        assert resp.status_code == 200
        d = resp.json()
        assert "available" in d and "alerts" in d

    def test_shape_when_available(self):
        d = client.get("/api/v1/official-alerts").json()
        if not d["available"]:
            return
        assert isinstance(d["alerts"], list)
        assert "flood_alert_active" in d
        for a in d["alerts"]:
            assert "event" in a and "is_flood" in a

    def test_requires_key_when_auth_enabled(self, monkeypatch):
        monkeypatch.delenv("AFFI_AUTH_DISABLED", raising=False)
        resp = client.get("/api/v1/official-alerts")
        assert resp.status_code == 401
        os.environ["AFFI_AUTH_DISABLED"] = "true"


class TestForecastVerification:
    def test_returns_200_and_shape(self):
        resp = client.get("/api/v1/forecast-verification")
        assert resp.status_code == 200
        d = resp.json()
        assert "records" in d and "summary" in d and "self_correction" in d
        s = d["summary"]
        assert set(["hits", "misses", "false_alarms", "correct_calm", "n_verified"]).issubset(s)

    def test_categories_are_valid(self):
        d = client.get("/api/v1/forecast-verification").json()
        valid = {"hit", "miss", "false_alarm", "correct_calm", "pending"}
        assert all(r["category"] in valid for r in d["records"])

    def test_proxy_note_is_disclosed(self):
        # The honesty note about using a downstream proxy gauge must always
        # be present — it's the whole point of not overclaiming.
        d = client.get("/api/v1/forecast-verification").json()
        assert d.get("proxy_note")
        assert "proxy" in d["proxy_note"].lower() or "downstream" in d["proxy_note"].lower()
        assert d["observed_source"]["id"] == "09480500"
