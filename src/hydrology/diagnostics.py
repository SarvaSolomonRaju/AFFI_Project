"""
diagnostics.py — Data diagnostics and baseline plots.
Run this BEFORE training anything. Understand your data first.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

from common.logging_setup import get_logger
from hydrology.baselines import run_baselines

log = get_logger(__name__)


def plot_data_diagnostics(df: pd.DataFrame, out_dir: Path, target_col: str = "runoff_mm") -> None:
    """
    4-panel diagnostic figure:
      Panel 1 — Full runoff time series (log scale)
      Panel 2 — Runoff distribution histogram (log-log)
      Panel 3 — Seasonal event rate (% days with runoff > 0 per month)
      Panel 4 — Precip vs runoff scatter (event days only)
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    obs = df[target_col].values.astype(np.float32)
    event_mask = obs > 0.0

    fig = plt.figure(figsize=(16, 10))
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.35)

    # Panel 1 — Time series
    ax1 = fig.add_subplot(gs[0, :])
    ax1.semilogy(df.index, np.where(obs > 0, obs, np.nan), color="#2166ac", lw=0.6, alpha=0.8)
    ax1.set_title("Walnut Gulch Daily Runoff (log scale)", fontsize=11)
    ax1.set_ylabel("Runoff (mm)")
    ax1.set_xlabel("Date")

    # Panel 2 — Distribution
    ax2 = fig.add_subplot(gs[1, 0])
    event_vals = obs[event_mask]
    ax2.hist(event_vals, bins=60, color="#d6604d", edgecolor="white", linewidth=0.3)
    ax2.set_yscale("log")
    ax2.set_title(
        f"Runoff Distribution — Event Days Only\n"
        f"({event_mask.sum()} events / {len(obs)} days = {100*event_mask.mean():.1f}%)",
        fontsize=10,
    )
    ax2.set_xlabel("Runoff (mm)")
    ax2.set_ylabel("Count (log)")

    # Panel 3 — Seasonal event rate
    ax3 = fig.add_subplot(gs[1, 1])
    monthly_rate = (
        pd.Series(event_mask, index=df.index)
        .groupby(df.index.month)
        .mean() * 100
    )
    ax3.bar(monthly_rate.index, monthly_rate.values, color="#4dac26", edgecolor="white")
    ax3.set_xticks(range(1, 13))
    ax3.set_xticklabels(["J","F","M","A","M","J","J","A","S","O","N","D"])
    ax3.set_title("Seasonal Event Rate (% days with runoff > 0)", fontsize=10)
    ax3.set_ylabel("Event rate (%)")
    ax3.set_xlabel("Month")

    out_path = out_dir / "data_diagnostics.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved data diagnostics → %s", out_path)


def plot_baseline_results(
    obs_test: np.ndarray,
    dates_test: pd.DatetimeIndex,
    results_df: pd.DataFrame,
    out_dir: Path,
) -> None:
    """
    Bar chart of NSE / KGE / F1 for all three baselines.
    This is the reference floor the LSTM must beat.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    metrics = ["nse", "kge", "event_f1"]
    x = np.arange(len(results_df))
    width = 0.25

    fig, ax = plt.subplots(figsize=(9, 5))
    colors = ["#4393c3", "#d6604d", "#4dac26"]
    for i, (metric, color) in enumerate(zip(metrics, colors)):
        ax.bar(x + i * width, results_df[metric].values, width, label=metric.upper(), color=color)

    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_xticks(x + width)
    ax.set_xticklabels(results_df.index, fontsize=10)
    ax.set_ylabel("Score")
    ax.set_title("Baseline Model Performance — LSTM Must Beat All Three", fontsize=11)
    ax.legend()
    ax.set_ylim(-0.5, 1.0)

    out_path = out_dir / "baseline_results.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved baseline results → %s", out_path)
    log.info("\n%s", results_df.to_string())