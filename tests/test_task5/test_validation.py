"""Tests for the pipeline validation harness."""
import json

from src.probabilistic import FloodMapLibrary
from src.benchmarking import pipeline_validation, score_report


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
