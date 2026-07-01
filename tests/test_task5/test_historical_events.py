"""Tests for historical event catalog + replay."""
import json

from src.benchmarking import load_events, replay_event
from src.probabilistic import FloodMapLibrary, rainfall_to_discharge


def test_events_load():
    ev = load_events("data/historical_events/sonoita_events.json")
    assert len(ev) >= 3
    for e in ev:
        assert "name" in e and "date" in e
        assert e.get("peak_q_cms", 0) > 0


def test_replay_event_observed_q():
    lib = FloodMapLibrary.load("outputs/task3/spatial_predictions.npz")
    ev = load_events("data/historical_events/sonoita_events.json")[0]
    r = replay_event(ev, lib)
    assert r["source_q"] == "observed_peak_q"
    assert r["predicted_max_depth_m"] >= 0


def test_replay_event_from_rainfall():
    lib = FloodMapLibrary.load("outputs/task3/spatial_predictions.npz")
    ev = {"name": "synthetic", "rainfall_24hr_in": 2.0, "peak_stage_m": None}
    r = replay_event(ev, lib, ensemble_fn=rainfall_to_discharge)
    assert r["source_q"] == "derived_from_rainfall"
    assert r["q_used_cms"] > 0
