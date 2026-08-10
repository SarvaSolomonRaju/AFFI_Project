"""
test_alert_engine.py — Tests for Alert Classification
=======================================================
These tests verify that the alert engine correctly classifies
different rainfall scenarios into the right alert levels.

KEY PRINCIPLE:
    Tests should cover EDGE CASES — the tricky situations
    where bugs are most likely to hide:
    - Zero rainfall → must be GREEN
    - Exactly at threshold → which side does it fall?
    - Extreme rainfall → must be WARNING
    - All members agree → 100% probability
    - Members disagree → mixed probability
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import numpy as np
import pandas as pd
from src.forecast.alert_engine import AlertEngine, build_return_period_comparison
from src.forecast.map_calculator import compute_rolling_accumulations, compute_daily_statistics


# Create a mock alert config using a simple class
class MockThreshold:
    def __init__(self, f24, f1, trigger):
        self.fraction_of_10yr_24hr = f24
        self.fraction_of_10yr_1hr = f1
        self.probability_trigger_pct = trigger

class MockAlertConfig:
    def __init__(self):
        self.advisory = MockThreshold(0.25, 0.18, 20)
        self.watch = MockThreshold(0.40, 0.36, 30)
        self.warning = MockThreshold(0.65, 0.71, 30)


IDF_10YR = {"1hr": 1.40, "3hr": 1.85, "6hr": 2.20, "24hr": 3.10}


@pytest.fixture
def engine():
    """Create an AlertEngine for testing."""
    return AlertEngine(IDF_10YR, MockAlertConfig())


def test_zero_rainfall_is_green(engine):
    """No rainfall should always be GREEN."""
    day_stats = {"day": 0, "date": "2026-07-15",
                 "p10_24hr": 0, "p50_24hr": 0, "p90_24hr": 0,
                 "p50_1hr": 0, "p90_1hr": 0, "p50_6hr": 0}
    members_24hr = np.zeros(31)
    members_1hr = np.zeros(31)

    result = engine.classify_day(day_stats, members_24hr, members_1hr)
    assert result["alert_level"] == "GREEN"


def test_extreme_rainfall_is_warning(engine):
    """Very heavy rainfall should be WARNING."""
    day_stats = {"day": 0, "date": "2026-07-15",
                 "p10_24hr": 4.0, "p50_24hr": 5.0, "p90_24hr": 8.0,
                 "p50_1hr": 2.0, "p90_1hr": 3.0, "p50_6hr": 4.0}
    # All 31 members predict heavy rain
    members_24hr = np.full(31, 5.0)
    members_1hr = np.full(31, 2.0)

    result = engine.classify_day(day_stats, members_24hr, members_1hr)
    assert result["alert_level"] == "WARNING"


def test_moderate_rainfall_is_watch(engine):
    """Moderate rainfall exceeding watch but not warning threshold."""
    watch_thr = 0.40 * 3.10  # 1.24 inches
    warn_thr = 0.65 * 3.10   # 2.015 inches

    # 15 members at 1.5" (above watch, below warning)
    # 16 members at 0.5" (below watch)
    members_24hr = np.array([1.5] * 15 + [0.5] * 16)
    members_1hr = np.zeros(31)

    day_stats = {"day": 0, "date": "2026-07-15",
                 "p10_24hr": 0.5, "p50_24hr": 1.0, "p90_24hr": 1.5,
                 "p50_1hr": 0, "p90_1hr": 0, "p50_6hr": 0.5}

    result = engine.classify_day(day_stats, members_24hr, members_1hr)
    assert result["alert_level"] == "WATCH"


def test_probability_of_exceedance_all_above():
    """If all members exceed threshold, PoE should be 100%."""
    values = np.full(31, 5.0)
    poe = AlertEngine.probability_of_exceedance(values, 1.0)
    assert poe == 100.0


def test_probability_of_exceedance_none_above():
    """If no members exceed threshold, PoE should be 0%."""
    values = np.full(31, 0.5)
    poe = AlertEngine.probability_of_exceedance(values, 1.0)
    assert poe == 0.0


def test_probability_of_exceedance_half():
    """If ~half exceed, PoE should be ~50%."""
    values = np.array([2.0] * 16 + [0.0] * 15)
    poe = AlertEngine.probability_of_exceedance(values, 1.0)
    assert 45 < poe < 55  # ~51.6%


def test_storm_index_calculation(engine):
    """Storm index should be p50_24hr / idf_10yr_24hr."""
    day_stats = {"day": 0, "date": "2026-07-15",
                 "p10_24hr": 1.0, "p50_24hr": 1.55, "p90_24hr": 2.0,
                 "p50_1hr": 0.5, "p90_1hr": 0.7, "p50_6hr": 1.0}
    members_24hr = np.full(31, 1.55)
    members_1hr = np.full(31, 0.5)

    result = engine.classify_day(day_stats, members_24hr, members_1hr)
    expected_si = 1.55 / 3.10  # 0.5
    assert abs(result["storm_index_24hr"] - expected_si) < 0.01


def test_classify_all_days_converts_mm_before_comparing_to_inch_thresholds(engine):
    """
    Regression test for the mm/inches unit bug fixed 2026-08-10.

    classify_all_days() re-derives its own per-member arrays from the raw
    (mm) `accumulations` dict rather than reusing compute_daily_statistics's
    already-converted output. A mild, real rainfall (0.1 mm/hour, so a
    24-hr sum of ~2.4 mm = ~0.094 in) must NOT trigger WARNING just
    because 2.4 (misread as inches) would exceed the 2.015-in warning
    threshold. Before the fix this asserted WARNING; it must be GREEN.
    """
    times = pd.date_range("2026-08-10", periods=48, freq="h")
    cols = [f"member_{i:02d}" for i in range(5)]
    map_matrix = pd.DataFrame(0.1, index=times, columns=cols)  # mm/hour

    accum = compute_rolling_accumulations(map_matrix)
    daily_stats = compute_daily_statistics(map_matrix, accum, n_days=1)

    classified = engine.classify_all_days(daily_stats, accum, map_matrix)
    assert classified[0]["alert_level"] == "GREEN"


def test_return_period_comparison():
    """Test return period classification."""
    idf_all = {
        "2yr": {"1hr": 0.90, "3hr": 1.15, "6hr": 1.40, "24hr": 1.90},
        "10yr": {"1hr": 1.40, "3hr": 1.85, "6hr": 2.20, "24hr": 3.10},
        "100yr": {"1hr": 2.40, "3hr": 3.10, "6hr": 3.70, "24hr": 5.40},
    }

    # Light rain — below 2yr
    day = {"p50_24hr": 1.0, "p90_24hr": 1.5}
    result = build_return_period_comparison(day, idf_all)
    assert result["exceeds_10yr"] == False
    assert "Minor" in result["severity_class"]

    # Heavy rain — above 10yr
    day = {"p50_24hr": 4.0, "p90_24hr": 6.0}
    result = build_return_period_comparison(day, idf_all)
    assert result["exceeds_10yr"] == True
    assert result["exceeds_100yr"] == False
