"""Tests for the pipeline validation harness."""
import json

import pytest

from src.probabilistic import FloodMapLibrary
from src.benchmarking import pipeline_validation, score_report, classification_accuracy, sensitivity_analysis
from src.benchmarking.return_periods import discharge_to_return_period


def test_validation_all_pass_on_real_artifacts():
    lib = FloodMapLibrary.load("outputs/task3/spatial_predictions.npz")
    alert = json.loads(open("outputs/task1_alert_packet.json").read())
    v = pipeline_validation(lib, alert)
    assert v["n_failed"] == 0
    assert v["all_passed"] is True


def test_score_report_shape():
    lib = FloodMapLibrary.load("outputs/task3/spatial_predictions.npz")
    alert = json.loads(open("outputs/task1_alert_packet.json").read())
    v = pipeline_validation(lib, alert)
    r = score_report(v, [], [])
    assert "validation" in r and "historical_events" in r and "scores" in r
    assert r["scores"]["n_events_replayed"] == 0


def test_classification_accuracy_flags_unmatched_scale():
    """
    A discharge scale mismatch (comparing against a table the input Q
    doesn't belong on) should show up as a real accuracy number, not
    silently pass -- this is what caught the peak-Q-vs-daily-mean-Q bug
    while building this function on 2026-08-10.
    """
    events = [{"name": "e1", "peak_q_cms": 10.0, "approx_return_period_yr": 10}]
    # Table where 10 cms is far outside any reasonable 10yr bracket.
    bad_table = [(2, 500.0), (10, 800.0), (100, 1200.0)]
    result = classification_accuracy(
        events, lambda q: discharge_to_return_period(q, table=bad_table)
    )
    assert result["n_events"] == 1
    assert result["accuracy"] == 0.0
    assert result["events"][0]["correct_within_2x"] is False


def test_classification_accuracy_correct_within_tolerance():
    events = [{"name": "e1", "peak_q_cms": 9.0, "approx_return_period_yr": 10}]
    table = [(2, 1.5), (10, 9.0), (25, 20.0)]
    result = classification_accuracy(
        events, lambda q: discharge_to_return_period(q, table=table)
    )
    assert result["accuracy"] == 1.0


def test_sensitivity_analysis_higher_rainfall_increases_discharge():
    def fake_rainfall_to_discharge(rainfall_in, basin_area_km2=510.0):
        return rainfall_in * basin_area_km2 * 0.01

    result = sensitivity_analysis(
        fake_rainfall_to_discharge, baseline_rainfall_in=3.0, baseline_basin_area_km2=510.0
    )
    assert result["rainfall_sensitivity"]["pct_change_at_high"] > 0
    assert result["rainfall_sensitivity"]["pct_change_at_low"] < 0
    assert result["basin_area_sensitivity"]["pct_change_at_high"] == pytest.approx(10.0, abs=0.1)
