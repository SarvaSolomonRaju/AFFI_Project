"""
test_map_calculator.py — Tests for MAP Computation
=====================================================
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
import pandas as pd
from src.forecast.map_calculator import (
    compute_map,
    compute_rolling_accumulations,
    compute_daily_statistics
)


def make_test_data(n_hours=48, n_members=5, value=1.0):
    """Create simple test data where every cell = value."""
    times = pd.date_range("2026-07-15", periods=n_hours, freq="h")
    cols = [f"member_{i:02d}" for i in range(n_members)]
    return pd.DataFrame(value, index=times, columns=cols)


def test_map_with_equal_weights():
    """If all points have equal data and weights sum to 1, MAP = data."""
    df = make_test_data(value=2.0)
    points = [
        {"id": "P1", "lat": 31.66, "lon": -110.70, "weight": 0.50, "desc": "A"},
        {"id": "P2", "lat": 31.85, "lon": -110.70, "weight": 0.50, "desc": "B"},
    ]
    all_data = {"P1": df.copy(), "P2": df.copy()}

    result = compute_map(all_data, points)
    # 0.50 * 2.0 + 0.50 * 2.0 = 2.0
    assert np.allclose(result.values, 2.0)


def test_map_with_different_weights():
    """Weighted average should reflect weights correctly."""
    df1 = make_test_data(value=10.0)
    df2 = make_test_data(value=0.0)
    points = [
        {"id": "P1", "lat": 31.66, "lon": -110.70, "weight": 0.60, "desc": "A"},
        {"id": "P2", "lat": 31.85, "lon": -110.70, "weight": 0.40, "desc": "B"},
    ]
    all_data = {"P1": df1, "P2": df2}

    result = compute_map(all_data, points)
    # 0.60 * 10.0 + 0.40 * 0.0 = 6.0
    assert np.allclose(result.values, 6.0)


def test_rolling_accumulation_3hr():
    """3-hour rolling sum of constant 1.0 should be 3.0 (after warmup)."""
    df = make_test_data(value=1.0, n_hours=24)
    accum = compute_rolling_accumulations(df)

    # After 3 hours, rolling sum should be 3.0
    assert np.allclose(accum["3hr"].iloc[2:].values, 3.0)


def test_rolling_accumulation_24hr():
    """24-hour rolling sum of constant 1.0 should be 24.0."""
    df = make_test_data(value=1.0, n_hours=48)
    accum = compute_rolling_accumulations(df)

    # After 24 hours, rolling sum should be 24.0
    assert np.allclose(accum["24hr"].iloc[23:].values, 24.0)


def test_daily_statistics_count():
    """Should return correct number of days."""
    df = make_test_data(n_hours=72)  # 3 days
    accum = compute_rolling_accumulations(df)
    stats = compute_daily_statistics(df, accum, n_days=3)

    assert len(stats) == 3


def test_daily_statistics_has_required_keys():
    """Each day should have all required statistical keys."""
    df = make_test_data(n_hours=48)
    accum = compute_rolling_accumulations(df)
    stats = compute_daily_statistics(df, accum, n_days=2)

    required = {"day", "date", "p10_24hr", "p50_24hr", "p90_24hr",
                "p50_1hr", "p90_1hr", "p50_6hr"}
    for day in stats:
        assert required.issubset(day.keys()), \
            f"Missing keys: {required - set(day.keys())}"


def test_daily_statistics_converts_mm_to_inches():
    """
    Regression test for the mm/inches unit bug fixed 2026-08-10.

    Input rainfall is mm/hour (see EnsembleForecastClient.fetch() docstring).
    A constant 25.4 mm/hour for 24+ hours gives a 24-hr rolling sum of
    609.6 mm = exactly 24.0 inches. Every downstream consumer (alert
    thresholds, discharge model) expects this function's output in
    inches -- if the /25.4 conversion is ever removed, this asserts
    24.0 rather than the wrong 609.6.
    """
    df = make_test_data(n_hours=48, value=25.4)
    accum = compute_rolling_accumulations(df)
    stats = compute_daily_statistics(df, accum, n_days=1)

    assert stats[0]["p50_24hr"] == pytest.approx(24.0)
    assert stats[0]["p10_24hr"] == pytest.approx(24.0)
    assert stats[0]["p90_24hr"] == pytest.approx(24.0)
