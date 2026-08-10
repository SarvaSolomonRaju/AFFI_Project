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


class TestContactRoster:
    def test_returns_200(self):
        resp = client.get("/api/v1/contacts")
        assert resp.status_code == 200

    def test_only_callable_categories_included(self):
        data = client.get("/api/v1/contacts").json()
        contacts = data["contacts"]
        assert len(contacts) > 0
        categories = {c["category"] for c in contacts}
        # Physical assets, not organizations — must never appear here.
        assert "power_line" not in categories
        assert "bridge" not in categories
        assert "cell_tower" not in categories

    def test_phone_is_real_or_explicitly_null_never_fabricated(self):
        # Every facility on file today (the official critical-facilities
        # roster) came with a verified address but no phone number -- null
        # is the honest answer, never a made-up placeholder.
        data = client.get("/api/v1/contacts").json()
        contacts = data["contacts"]
        assert all(c["phone"] is None for c in contacts)

    def test_requires_key_when_auth_enabled(self, monkeypatch):
        monkeypatch.delenv("AFFI_AUTH_DISABLED", raising=False)
        resp = client.get("/api/v1/contacts")
        assert resp.status_code == 401
        os.environ["AFFI_AUTH_DISABLED"] = "true"
