"""
scripts/03_train_hurdle.py
Train the two-stage hurdle model on Walnut Gulch data.

Usage:
    python scripts/03_train_hurdle.py
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
import torch
import yaml
from sklearn.metrics import f1_score, roc_auc_score, average_precision_score

from src.common.logging_setup import get_logger
from src.common.paths import DATA_INTERIM as INTERIM_DIR, TASK2_CONFIG
from src.task2_hydrology.features import build_sequences
from src.task2_hydrology.trainer import train_classifier, train_regressor
from src.task2_hydrology.baselines import nse

log = get_logger("03_train_hurdle")

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
MODELS_DIR.mkdir(exist_ok=True)

SCALER_PATH = MODELS_DIR / "feature_scaler.joblib"


def main() -> None:
    # ── Config ────────────────────────────────────────────────────────────────
    with open(TASK2_CONFIG) as f:
        cfg_full = yaml.safe_load(f)
    cfg = cfg_full["model"]

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    log.info("Device: %s", device)

    # ── Load data ─────────────────────────────────────────────────────────────
    df = pd.read_parquet(INTERIM_DIR / "walnut_gulch_daily.parquet")
    df.index = pd.to_datetime(df.index)
    log.info("Loaded %d rows", len(df))

    # ── Build sequences ───────────────────────────────────────────────────────
    lookback = cfg["lookback"]
    X, y_cls, y_reg, scaler = build_sequences(
        df,
        lookback=lookback,
        fit_scaler=True,
        scaler_path=SCALER_PATH,
    )
    log.info("Sequences: X=%s  y_cls=%s  event_rate=%.1f%%",
             X.shape, y_cls.shape, 100 * y_cls.mean())

    # ── Train / val / test split (70 / 15 / 15) ───────────────────────────────
    n = len(X)
    t1 = int(n * 0.70)
    t2 = int(n * 0.85)

    X_train, y_cls_train, y_reg_train = X[:t1],  y_cls[:t1],  y_reg[:t1]
    X_val,   y_cls_val,   y_reg_val   = X[t1:t2], y_cls[t1:t2], y_reg[t1:t2]
    X_test,  y_cls_test,  y_reg_test  = X[t2:],  y_cls[t2:],  y_reg[t2:]

    log.info("Split — train=%d  val=%d  test=%d", t1, t2-t1, n-t2)

    # ── Stage 1: Classifier ───────────────────────────────────────────────────
    classifier = train_classifier(
        X_train, y_cls_train, X_val, y_cls_val, cfg, MODELS_DIR, device
    )

    # ── Stage 2: Regressor ────────────────────────────────────────────────────
    regressor = train_regressor(
        X_train, y_reg_train, X_val, y_reg_val, cfg, MODELS_DIR, device
    )

    # ── Evaluate on test set ──────────────────────────────────────────────────
    classifier.eval()
    regressor.eval()

    with torch.no_grad():
        xt = torch.tensor(X_test).to(device)
        p_event   = classifier(xt).cpu().numpy()
        log1p_mag = regressor(xt).cpu().numpy()

    # Classifier metrics
    y_pred_cls = (p_event >= 0.5).astype(int)
    f1  = f1_score(y_cls_test, y_pred_cls, zero_division=0)
    auc_roc = roc_auc_score(y_cls_test, p_event) if y_cls_test.sum() > 0 else float("nan")
    auc_pr  = average_precision_score(y_cls_test, p_event) if y_cls_test.sum() > 0 else float("nan")

    # Combined prediction
    y_pred_mm = np.expm1(log1p_mag) * p_event
    obs_mm    = df["runoff_mm"].values[lookback:][t2:]
    combined_nse = nse(obs_mm, y_pred_mm)

    # Regressor NSE on event days only
    event_mask = y_cls_test == 1
    if event_mask.sum() > 0:
        obs_ev  = obs_mm[event_mask]
        pred_ev = y_pred_mm[event_mask]
        reg_nse = nse(obs_ev, pred_ev)
    else:
        reg_nse = float("nan")

    log.info("=" * 60)
    log.info("TEST SET RESULTS")
    log.info("  Classifier  F1     = %.3f  (floor: 0.41)", f1)
    log.info("  Classifier  AUC-ROC= %.3f", auc_roc)
    log.info("  Classifier  AUC-PR = %.3f  (floor: 0.25)", auc_pr)
    log.info("  Regressor   NSE    = %.3f  (floor: 0.20)", reg_nse)
    log.info("  Combined    NSE    = %.3f  (floor: 0.00)", combined_nse)
    log.info("=" * 60)

    # Pass/fail
    passed = (
        f1 > 0.41 and reg_nse > 0.20 and combined_nse > 0.00 and auc_pr > 0.25
    )
    log.info("ACCEPTANCE: %s", "✅ PASSED" if passed else "❌ NOT YET — review metrics above")


if __name__ == "__main__":
    main()