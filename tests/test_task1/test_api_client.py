"""
test_api_client.py — Tests for API Client
============================================
These tests use SYNTHETIC data only (no real API calls).
This is important because:
1. Tests must work offline
2. Tests must be fast (no network delays)
3. Tests must be deterministic (same result every time)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.forecast.api_client import EnsembleForecastClient


@pytest.fixture
def client():
    """Create a client with 0 retries (for fast testing)."""
    return EnsembleForecastClient(max_retries=1, timeout=5)


def test_synthetic_fallback(client):
    """Client should fall back to synthetic data on failure."""
    # Use an invalid URL to force failure
    client.base_url = "https://invalid-url-that-does-not-exist.com/api"
    df, source = client.fetch(31.66, -110.70, "TEST")

    assert source == "synthetic"
    assert df.shape[0] == 168  # 7 days × 24 hours
    assert df.shape[1] == 31   # 31 ensemble members


def test_synthetic_data_is_non_negative(client):
    """Synthetic rainfall should never be negative."""
    client.base_url = "https://invalid-url.com"
    df, _ = client.fetch(31.66, -110.70, "TEST")

    assert (df >= 0).all().all(), "Synthetic data contains negative values"


def test_stats_tracking(client):
    """Client should track call statistics."""
    client.base_url = "https://invalid-url.com"
    client.fetch(31.66, -110.70, "TEST")

    stats = client.get_stats()
    assert stats["total_calls"] == 1
    assert stats["failed"] == 1
    assert stats["synthetic_fallbacks"] == 1
