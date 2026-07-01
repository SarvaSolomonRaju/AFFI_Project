"""
baselines.py — Sanity baselines before any LSTM.
Three dumb predictors: ZeroModel, MeanModel, PersistenceModel.
If LSTM can't beat all three, the LSTM is broken.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple

from common.logging_setup import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

def nse(obs: np.ndarray, sim: np.ndarray) -> float:
    """Nash-Sutcliffe Efficiency. 1.0 = perfect. <0 = worse than mean."""
    obs_mean = obs.mean()
    ss_res = np.sum((obs - sim) ** 2)
    ss_tot = np.sum((obs - obs_mean) ** 2)
    if ss_tot == 0:
        return float("nan")
    return float(1.0 - ss_res / ss_tot)


def kge(obs: np.ndarray, sim: np.ndarray) -> float:
    """Kling-Gupta Efficiency. 1.0 = perfect."""
    r = np.corrcoef(obs, sim)[0, 1] if obs.std() > 0 and sim.std() > 0 else 0.0
    alpha = sim.std() / obs.std() if obs.std() > 0 else float("nan")
    beta = sim.mean() / obs.mean() if obs.mean() > 0 else float("nan")
    return float(1.0 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))


def event_f1(obs: np.ndarray, sim: np.ndarray, threshold: float = 0.0) -> float:
    """F1 score for event-day detection (obs > threshold)."""
    obs_bin = (obs > threshold).astype(int)
    sim_bin = (sim > threshold).astype(int)
    tp = int(np.sum((obs_bin == 1) & (sim_bin == 1)))
    fp = int(np.sum((obs_bin == 0) & (sim_bin == 1)))
    fn = int(np.sum((obs_bin == 1) & (sim_bin == 0)))
    denom = 2 * tp + fp + fn
    return float(2 * tp / denom) if denom > 0 else 0.0


def compute_all_metrics(obs: np.ndarray, sim: np.ndarray, label: str) -> dict:
    """Compute and log all metrics for one model."""
    metrics = {
        "model": label,
        "nse": nse(obs, sim),
        "kge": kge(obs, sim),
        "event_f1": event_f1(obs, sim),
        "rmse": float(np.sqrt(np.mean((obs - sim) ** 2))),
        "bias_pct": float(
            100 * (sim.sum() - obs.sum()) / obs.sum() if obs.sum() > 0 else float("nan")
        ),
    }
    log.info(
        "[%s] NSE=%.3f  KGE=%.3f  F1=%.3f  RMSE=%.4f  Bias=%.1f%%",
        label, metrics["nse"], metrics["kge"],
        metrics["event_f1"], metrics["rmse"], metrics["bias_pct"],
    )
    return metrics


# ─────────────────────────────────────────────────────────────────────────────
# Baseline models
# ─────────────────────────────────────────────────────────────────────────────

def zero_model(obs: np.ndarray) -> np.ndarray:
    """Predict zero always. Correct 97% of the time on Walnut Gulch."""
    return np.zeros_like(obs)


def mean_model(train_obs: np.ndarray, n_test: int) -> np.ndarray:
    """Predict training-set mean always. NSE definition: this scores exactly 0."""
    return np.full(n_test, train_obs.mean())


def persistence_model(obs_full: np.ndarray, train_size: int) -> np.ndarray:
    """Predict yesterday's value. Naive but beats mean on event days."""
    test_obs = obs_full[train_size:]
    # shift by 1: last training day is the first prediction
    prev = np.concatenate([[obs_full[train_size - 1]], test_obs[:-1]])
    return prev


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

def run_baselines(
    df: pd.DataFrame,
    target_col: str = "runoff_mm",
    train_frac: float = 0.7,
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    """
    Run all three baselines on df[target_col].

    Returns
    -------
    results_df : DataFrame with one row per model and all metrics
    obs_test   : raw observed values on test split (for plotting)
    dates_test : DatetimeIndex for test split
    """
    obs = df[target_col].values.astype(np.float32)
    n = len(obs)
    split = int(n * train_frac)

    obs_train = obs[:split]
    obs_test = obs[split:]
    dates_test = df.index[split:]

    log.info(
        "Baselines — train=%d days  test=%d days  event_rate=%.1f%%",
        split, n - split, 100 * (obs_test > 0).mean(),
    )

    rows = []
    rows.append(compute_all_metrics(obs_test, zero_model(obs_test), "ZeroModel"))
    rows.append(compute_all_metrics(obs_test, mean_model(obs_train, len(obs_test)), "MeanModel"))
    rows.append(compute_all_metrics(obs_test, persistence_model(obs, split), "PersistenceModel"))

    results_df = pd.DataFrame(rows).set_index("model")
    return results_df, obs_test, dates_test