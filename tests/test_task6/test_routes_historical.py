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


class TestHistoricalComparison:
    def test_returns_200_or_404(self):
        resp = client.get("/api/v1/historical-comparison")
        assert resp.status_code in (200, 404)

    def test_closest_event_is_actually_closest(self):
        resp = client.get("/api/v1/historical-comparison")
        if resp.status_code != 200:
            return
        data = resp.json()
        today_q = data["today_discharge_cms"]
        closest = data["closest_event"]
        assert "name" in closest and "peak_q_cms" in closest and "date" in closest
        assert data["catalog_size"] == 4

        # Re-derive independently from the raw catalog file, rather than
        # trusting the endpoint's own math.
        import json
        events = json.loads((ROOT / "data" / "historical_events" / "sonoita_events.json").read_text())["events"]
        expected = min(events, key=lambda e: abs(e["peak_q_cms"] - today_q))
        assert closest["name"] == expected["name"]

        # A dry day (Q=0) always computes to -100% vs whatever event is
        # closest — a technically-correct but meaningless number. Should
        # be omitted, not shown, on dry days.
        if today_q == 0:
            assert data["delta_pct_vs_closest_event"] is None

    def test_requires_key_when_auth_enabled(self, monkeypatch):
        monkeypatch.delenv("AFFI_AUTH_DISABLED", raising=False)
        resp = client.get("/api/v1/historical-comparison")
        assert resp.status_code == 401
        os.environ["AFFI_AUTH_DISABLED"] = "true"
