"""
Regression test for the Task 2 hurdle model's reported metrics.

The whitepaper (docs/AFFI_whitepaper_2026-08-10.md, Section 4.4) quotes
NSE 0.348 and PBIAS -2.9% verbatim from models/best_inference_config.json.
Nothing previously re-derived those numbers from the saved held-out
predictions in models/test_arrays.npz, so a stale/hand-edited config
value could drift from the actual model output undetected. This
recomputes NSE and PBIAS directly from the saved arrays and asserts
they match the config file the whitepaper cites.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import json
import numpy as np
import pytest

from hydrology.baselines import nse

MODELS_DIR = Path(__file__).parent.parent.parent / "models"


@pytest.fixture
def test_arrays():
    if not (MODELS_DIR / "test_arrays.npz").exists():
        pytest.skip("models/test_arrays.npz not present")
    return np.load(MODELS_DIR / "test_arrays.npz")


@pytest.fixture
def config():
    if not (MODELS_DIR / "best_inference_config.json").exists():
        pytest.skip("models/best_inference_config.json not present")
    return json.loads((MODELS_DIR / "best_inference_config.json").read_text())


def test_reported_nse_matches_saved_predictions(test_arrays, config):
    y_obs, y_pred = test_arrays["y_obs"], test_arrays["y_pred"]
    assert nse(y_obs, y_pred) == pytest.approx(config["test_nse"], abs=1e-6)


def test_reported_pbias_matches_saved_predictions(test_arrays, config):
    y_obs, y_pred = test_arrays["y_obs"], test_arrays["y_pred"]
    pbias = 100.0 * (y_pred.sum() - y_obs.sum()) / y_obs.sum()
    assert pbias == pytest.approx(config["test_pbias"], abs=1e-4)


def test_hurdle_prediction_is_zero_when_gate_does_not_fire(test_arrays):
    """The hurdle structure means non-event days must predict exactly 0."""
    y_pred = test_arrays["y_pred"]
    assert (y_pred == 0).any(), "expected some non-event days with zero-gated prediction"
    assert (y_pred >= 0).all(), "discharge prediction must never be negative"
