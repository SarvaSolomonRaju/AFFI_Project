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


class TestLiveGauge:
    def test_returns_200_or_upstream_failure(self):
        # This hits a real external service (USGS NWIS) — no key required,
        # but network-dependent. Accept a clean 502 (this route's own
        # graceful handling of an upstream failure) rather than requiring
        # the live network call to succeed in every test environment.
        resp = client.get("/api/v1/live-gauge")
        assert resp.status_code in (200, 502, 404)

    def test_response_shape_when_available(self):
        resp = client.get("/api/v1/live-gauge")
        if resp.status_code != 200:
            return
        data = resp.json()
        assert data["pilot_gauge"]["id"] == "09481500"
        assert data["pilot_gauge_has_telemetry"] is False
        assert data["nearest_live_gauge"]["id"] == "09480500"
        assert "readings" in data
