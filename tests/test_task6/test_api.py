from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ["AFFI_AUTH_DISABLED"] = "true"

from src.api.server import app

client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "operational"
        assert "version" in data
        assert "uptime_seconds" in data

    def test_health_includes_watershed(self):
        resp = client.get("/health")
        assert resp.json()["watershed"] == "Upper Sonoita Creek"


class TestAlertEndpoints:
    def test_current_alert_returns_data_or_404(self):
        resp = client.get("/api/v1/alert/current")
        assert resp.status_code in (200, 404)
        if resp.status_code == 200:
            data = resp.json()
            assert "current_alert" in data
            assert data["current_alert"] in ("GREEN", "ADVISORY", "WATCH", "WARNING")

    def test_alert_packet_returns_data_or_404(self):
        resp = client.get("/api/v1/alert/packet")
        assert resp.status_code in (200, 404)

    def test_alert_history(self):
        resp = client.get("/api/v1/alert/history?limit=5")
        assert resp.status_code in (200, 500)

    def test_forecast_days(self):
        resp = client.get("/api/v1/forecast/days")
        assert resp.status_code in (200, 404)

    def test_return_periods(self):
        resp = client.get("/api/v1/forecast/return_periods")
        assert resp.status_code in (200, 404)


class TestModelEndpoint:
    def test_model_metrics(self):
        resp = client.get("/api/v1/model/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "task1_metrics" in data
        assert "task2_inference_config" in data


class TestWatershedConfig:
    def test_get_config(self):
        resp = client.get("/api/v1/watershed/config")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "watershed" in data
            assert data["watershed"]["name"] == "Upper Sonoita Creek"


class TestDashboardFiles:
    def test_missing_file_returns_404(self):
        resp = client.get("/api/v1/dashboard/nonexistent_file")
        assert resp.status_code == 404


class TestAuthDisabled:
    def test_all_endpoints_accessible_with_auth_disabled(self):
        endpoints = [
            "/api/v1/alert/current",
            "/api/v1/alert/packet",
            "/api/v1/alert/history",
            "/api/v1/forecast/days",
            "/api/v1/model/metrics",
            "/api/v1/watershed/config",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            assert resp.status_code != 401, f"{ep} returned 401 with auth disabled"
