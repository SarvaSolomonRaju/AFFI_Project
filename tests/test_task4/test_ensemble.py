"""Tests for rainfall->discharge + ensemble propagation."""
import json
import numpy as np
import pytest

from src.probabilistic import (
    FloodMapLibrary, rainfall_to_discharge, propagate_ensemble,
)


def test_zero_rain_zero_q():
    assert rainfall_to_discharge(0.0) == 0.0


def test_runoff_initial_abstraction():
    # 0.1" rain is below initial abstraction for CN=75 -> 0 runoff
    assert rainfall_to_discharge(0.1) == 0.0


def test_q_increases_with_rain():
    qs = [rainfall_to_discharge(p) for p in [0.5, 1.0, 2.0, 4.0, 8.0]]
    for a, b in zip(qs, qs[1:]):
        assert b >= a


def test_propagate_monotonic():
    lib = FloodMapLibrary.load("outputs/task3/spatial_predictions.npz")
    day = {"p10_24hr": 0.3, "p50_24hr": 1.2, "p90_24hr": 3.5,
           "date": "test", "alert_level": "WATCH"}
    res = propagate_ensemble(day, lib)
    q10 = res["discharge_cms"]["p10"]
    q50 = res["discharge_cms"]["p50"]
    q90 = res["discharge_cms"]["p90"]
    assert q10 <= q50 <= q90
    # Scenarios present
    for k in ("best", "likely", "worst"):
        assert "lookup" in res["scenarios"][k]
        assert "stats" in res["scenarios"][k]


def test_real_alert_packet_runs():
    lib = FloodMapLibrary.load("outputs/task3/spatial_predictions.npz")
    alert = json.loads(open("outputs/task1_alert_packet.json").read())
    for d in alert["forecast_days"]:
        res = propagate_ensemble(d, lib)
        assert res["discharge_cms"]["p50"] >= 0
