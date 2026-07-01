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


class TestBulletin:
    def test_returns_200_or_404(self):
        # 404 only if no forecast packet exists at all (fresh clone,
        # pipeline never run) — matches the pattern of every other
        # alert-packet-backed endpoint in this test suite.
        resp = client.get("/api/v1/bulletin")
        assert resp.status_code in (200, 404)

    def test_bulletin_has_nws_format_sections(self):
        resp = client.get("/api/v1/bulletin")
        if resp.status_code != 200:
            return
        text = resp.json()["text"]
        for section in ("* WHAT:", "* WHERE:", "* WHEN:", "* IMPACTS:", "* ACTION:"):
            assert section in text

    def test_bulletin_includes_legal_note(self):
        resp = client.get("/api/v1/bulletin")
        if resp.status_code != 200:
            return
        assert "28-910" in resp.json()["text"]

    def test_alert_level_matches_current_alert(self):
        resp = client.get("/api/v1/bulletin")
        if resp.status_code != 200:
            return
        data = resp.json()
        current = client.get("/api/v1/alert/current").json()
        assert data["alert_level"] == current["current_alert"]
