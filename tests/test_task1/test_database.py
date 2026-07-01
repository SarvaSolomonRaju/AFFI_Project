"""
test_database.py — Tests for Database Operations
===================================================
Uses a TEMPORARY database (deleted after each test).
This ensures tests don't pollute your real database.
"""

import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.common.database import FloodDatabase


@pytest.fixture
def db(tmp_path):
    """Create a temporary database for testing."""
    db_path = str(tmp_path / "test_flood.db")
    database = FloodDatabase(db_path)
    yield database
    database.close()


def test_database_creates_tables(db):
    """Database should create all required tables."""
    cursor = db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )
    tables = {row[0] for row in cursor.fetchall()}

    assert "forecast_runs" in tables
    assert "api_calls" in tables
    assert "alerts_history" in tables


def test_save_and_retrieve_forecast(db):
    """Should save a forecast and retrieve it."""
    packet = {
        "generated_utc": "2026-07-15T10:00:00",
        "watershed": {"name": "Test Creek", "huc": "12345678"},
        "current_alert": "WATCH",
        "forecast_days": [
            {"alert_level": "GREEN", "storm_index_24hr": 0.1,
             "p50_24hr": 0.5, "p90_24hr": 1.0},
            {"alert_level": "WATCH", "storm_index_24hr": 0.6,
             "p50_24hr": 1.5, "p90_24hr": 3.0},
        ]
    }

    run_id = db.save_forecast_run(packet, "api")
    assert run_id >= 1

    runs = db.get_recent_runs(1)
    assert len(runs) == 1
    assert runs[0]["current_alert"] == "WATCH"
    assert runs[0]["watershed_name"] == "Test Creek"


def test_save_api_call(db):
    """Should log API calls."""
    db.save_api_call(
        endpoint="https://api.example.com",
        grid_point_id="P1",
        lat=31.66, lon=-110.70,
        success=True,
        response_time_ms=250.5
    )

    cursor = db.conn.execute("SELECT COUNT(*) FROM api_calls")
    count = cursor.fetchone()[0]
    assert count == 1


def test_alert_stats(db):
    """Should count alerts by level."""
    for alert in ["GREEN", "GREEN", "WATCH", "WARNING"]:
        packet = {
            "generated_utc": "2026-07-15T10:00:00",
            "watershed": {"name": "Test", "huc": "12345"},
            "current_alert": alert,
            "forecast_days": [{"alert_level": alert, "storm_index_24hr": 0.5,
                              "p50_24hr": 1.0, "p90_24hr": 2.0}]
        }
        db.save_forecast_run(packet)

    stats = db.get_alert_stats()
    assert stats.get("GREEN", 0) == 2
    assert stats.get("WATCH", 0) == 1
    assert stats.get("WARNING", 0) == 1
