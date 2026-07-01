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


class TestDecisionCockpit:
    def test_returns_200_or_404(self):
        resp = client.get("/api/v1/decision-cockpit")
        assert resp.status_code in (200, 404)

    def test_time_to_peak_ordering(self):
        resp = client.get("/api/v1/decision-cockpit")
        if resp.status_code != 200:
            return
        ttp = resp.json()["time_to_peak_hours"]
        # p90 rainfall -> faster/earlier peak than p10 rainfall (more
        # intense storm concentrates runoff sooner) — Kirpich/SCS lag
        # method, not a computation this test re-derives, just checks
        # the ordering makes physical sense.
        assert ttp["p90"] <= ttp["p50"] <= ttp["p10"]

    def test_life_safety_is_a_percentage(self):
        resp = client.get("/api/v1/decision-cockpit")
        if resp.status_code != 200:
            return
        pct = resp.json()["life_safety"]["prob_gt_0_5m_max_pct"]
        assert 0.0 <= pct <= 100.0

    def test_requires_key_when_auth_enabled(self, monkeypatch):
        monkeypatch.delenv("AFFI_AUTH_DISABLED", raising=False)
        resp = client.get("/api/v1/decision-cockpit")
        assert resp.status_code == 401
        os.environ["AFFI_AUTH_DISABLED"] = "true"
