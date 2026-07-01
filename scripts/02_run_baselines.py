"""
scripts/02_run_baselines.py
Run data diagnostics and all three baselines.
This is the mandatory first step before any model training.

Usage:
    python scripts/02_run_baselines.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make src/ importable from scripts/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from src.common.logging_setup import get_logger
from src.common.paths import DATA_INTERIM as INTERIM_DIR, FIGURES_DIR
from src.hydrology.baselines import run_baselines
from src.hydrology.diagnostics import plot_data_diagnostics, plot_baseline_results

log = get_logger("02_run_baselines")


def main() -> None:
    # ── 1. Load interim data ──────────────────────────────────────────────────
    parquet_path = INTERIM_DIR / "walnut_gulch_daily.parquet"
    if not parquet_path.exists():
        log.error("Data not found: %s — run scripts/01_download_data.py first", parquet_path)
        sys.exit(1)

    df = pd.read_parquet(parquet_path)
    df.index = pd.to_datetime(df.index)
    log.info("Loaded %d rows from %s", len(df), parquet_path)

    # ── 2. Data diagnostics ───────────────────────────────────────────────────
    plot_data_diagnostics(df, out_dir=FIGURES_DIR)

    # ── 3. Run baselines ──────────────────────────────────────────────────────
    results_df, obs_test, dates_test = run_baselines(df, target_col="runoff_mm")

    # ── 4. Plot baseline results ──────────────────────────────────────────────
    plot_baseline_results(obs_test, dates_test, results_df, out_dir=FIGURES_DIR)

    # ── 5. Save baseline results to CSV ──────────────────────────────────────
    out_csv = INTERIM_DIR / "baseline_metrics.csv"
    results_df.to_csv(out_csv)
    log.info("Baseline metrics saved → %s", out_csv)

    # ── 6. Print acceptance floor ─────────────────────────────────────────────
    log.info("=" * 60)
    log.info("ACCEPTANCE FLOOR — LSTM must beat ALL of these:")
    log.info("  Classifier  F1  ≥ 0.30")
    log.info("  Regressor   NSE ≥ 0.20  (event days only)")
    log.info("  Combined    NSE ≥ 0.10  (full timeline)")
    log.info("  Combined    AUC-PR ≥ 0.25")
    log.info("=" * 60)


if __name__ == "__main__":
    main()