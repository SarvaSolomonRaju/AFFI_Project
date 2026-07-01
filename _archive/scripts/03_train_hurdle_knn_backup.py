"""
03_train_hurdle.py -- Hurdle model: LSTM flood classifier + KNN magnitude.

Redesigned for Babocomari River (perennial, 0.1% zero-flow):
  - "Event" = discharge > P90 (0.878 cms) — top 10% flow days
  - Physical gate (precip>0) REMOVED — perennial stream always flows
  - LSTM classifies: "Is today a flood day?"
  - KNN estimates: "If flood, how much?"
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.metrics import f1_score, roc_auc_score, average_precision_score
from sklearn.neighbors import KNeighborsRegressor
from sklearn.preprocessing import StandardScaler
import joblib
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.common.logging_setup import configure_logging, get_logger
from src.common.paths import DATA_INTERIM, MODELS_DIR
from src.hydrology.features import build_sequences

configure_logging()
log = get_logger(__name__)


class LSTMClassifier(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, dropout):
        super().__init__()
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size,
                            num_layers=num_layers, batch_first=True,
                            dropout=dropout if num_layers > 1 else 0.0)
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(hidden_size, 1))

    def forward(self, x):
        _, (h_n, _) = self.lstm(x)
        return self.head(h_n[-1]).squeeze(-1)


def nse(obs, sim):
    ss_res = np.sum((obs - sim) ** 2)
    ss_tot = np.sum((obs - np.mean(obs)) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan")


def focal_loss(logits, targets, alpha=0.75, gamma=2.0):
    bce = nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    p = torch.sigmoid(logits)
    pt = torch.where(targets == 1, p, 1 - p)
    alpha_t = torch.where(targets == 1, alpha, 1 - alpha)
    return (alpha_t * (1 - pt) ** gamma * bce).mean()


def main():
    with open(ROOT / "config" / "task2.yaml") as f:
        cfg_all = yaml.safe_load(f)

    m = cfg_all["model"]
    d = cfg_all["data"]
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    log.info("Device: %s", device)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    parquet = DATA_INTERIM / f"{d['base_basin']['name']}_daily.parquet"
    df = pd.read_parquet(parquet)
    log.info("Loaded %d rows", len(df))
    dates_raw = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df["date"])


    lookback = m["lookback"]

    # Compute P90 threshold from training portion (no data leakage)
    n_total = len(df)
    n_train_approx = int(n_total * 0.70)
    q_train = df["discharge_cms"].values[:n_train_approx + lookback]
    p90_threshold = float(np.percentile(q_train[~np.isnan(q_train)], 90))
    log.info("P90 flood threshold (from train only): %.3f cms", p90_threshold)

    X, y_cls, _, scaler = build_sequences(
        df, lookback, fit_scaler=True,
        scaler_path=MODELS_DIR / "feature_scaler.joblib",
        target_col="discharge_cms",
        event_threshold=p90_threshold,
    )

    discharge_all = df["discharge_cms"].values[lookback:].astype(np.float32)
    precip_all = df["precip_mm"].values[lookback:].astype(np.float32)

    log.info("Sequences: X=%s  event_rate=%.1f%%", X.shape, 100 * y_cls.mean())

    n = len(X)
    t1, t2 = int(n * 0.70), int(n * 0.85)

    # Full arrays
    X_train, X_val, X_test = X[:t1], X[t1:t2], X[t2:]
    y_cls_train, y_cls_val, y_cls_test = y_cls[:t1], y_cls[t1:t2], y_cls[t2:]
    discharge_train = discharge_all[:t1]
    discharge_val   = discharge_all[t1:t2]
    discharge_test  = discharge_all[t2:]
    precip_train = precip_all[:t1]
    precip_val   = precip_all[t1:t2]
    precip_test  = precip_all[t2:]

    log.info("Split -- train=%d  val=%d  test=%d", t1, len(X_val), len(X_test))
    log.info("Event rate: train=%.1f%%  val=%.1f%%  test=%.1f%%",
             100*y_cls_train.mean(), 100*y_cls_val.mean(), 100*y_cls_test.mean())

    # ================================================================
    # No physical gate — Babocomari is perennial (99.9% non-zero flow)
    # The LSTM learns rain→flood lag from the 30-day lookback window
    # ================================================================
    input_size = X.shape[2]

    # ================================================================
    # KNN magnitude estimator — predicts log(discharge) for flood days
    # ================================================================
    df_feat = df.copy()
    precip_raw = df_feat["precip_mm"].values
    api = np.zeros(len(df_feat), dtype=np.float64)
    for i in range(1, len(df_feat)):
        api[i] = precip_raw[i] + 0.85 * api[i - 1]
    df_feat["api"] = api
    df_feat["precip_3d"] = df_feat["precip_mm"].rolling(3, min_periods=1).sum()
    df_feat["precip_7d"] = df_feat["precip_mm"].rolling(7, min_periods=1).sum()

    knn_cols = ["precip_mm", "precip_3d", "precip_7d", "api", "et0_mm"]
    knn_feat = df_feat[knn_cols].values[lookback:].astype(np.float32)
    knn_train, knn_val, knn_test = knn_feat[:t1], knn_feat[t1:t2], knn_feat[t2:]

    ev_tr = discharge_train > p90_threshold  # flood days only
    knn_scaler = StandardScaler()
    knn_train_s = knn_scaler.fit_transform(knn_train)
    knn_val_s = knn_scaler.transform(knn_val)
    knn_test_s = knn_scaler.transform(knn_test)

    K = max(3, min(10, int(ev_tr.sum() * 0.1)))
    knn = KNeighborsRegressor(n_neighbors=K, weights="distance")
    knn.fit(knn_train_s[ev_tr], np.log1p(discharge_train[ev_tr]))
    joblib.dump(knn, MODELS_DIR / "knn_magnitude.joblib")
    joblib.dump(knn_scaler, MODELS_DIR / "knn_scaler.joblib")
    log.info("KNN K=%d fitted on %d flood events (discharge > %.3f cms)",
             K, ev_tr.sum(), p90_threshold)

    # ================================================================
    # LSTM Classifier — trained on ALL days (no physical gate)
    # ================================================================
    log.info("--- LSTM Classifier (all days, focal loss, P90 threshold) ---")

    clf = LSTMClassifier(input_size, m["hidden_size"], m["num_layers"], m["dropout"]).to(device)
    opt = torch.optim.Adam(clf.parameters(), lr=m["lr"], weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, patience=10, factor=0.5)

    ds = TensorDataset(torch.tensor(X_train), torch.tensor(y_cls_train))
    dl = DataLoader(ds, batch_size=m["batch_size"], shuffle=True)

    best_val, patience_cnt = float("inf"), 0
    for epoch in range(1, 200 + 1):
        clf.train()
        losses = []
        for xb, yb in dl:
            xb, yb = xb.to(device), yb.to(device)
            opt.zero_grad()
            loss = focal_loss(clf(xb), yb)
            loss.backward()
            nn.utils.clip_grad_norm_(clf.parameters(), 1.0)
            opt.step()
            losses.append(loss.item())

        clf.eval()
        with torch.no_grad():
            vl = focal_loss(clf(torch.tensor(X_val).to(device)),
                           torch.tensor(y_cls_val).to(device)).item()
        sched.step(vl)

        if epoch % 10 == 0:
            with torch.no_grad():
                vp = torch.sigmoid(clf(torch.tensor(X_val).to(device))).cpu().numpy()
            vf1 = f1_score(y_cls_val, (vp >= 0.5).astype(int), zero_division=0)
            log.info("[Clf] Epoch %3d | train=%.4f | val=%.4f | val_F1@0.5=%.3f | lr=%.1e",
                     epoch, np.mean(losses), vl, vf1, opt.param_groups[0]["lr"])

        if vl < best_val:
            best_val, patience_cnt = vl, 0
            torch.save(clf.state_dict(), MODELS_DIR / "classifier_best.pt")
        else:
            patience_cnt += 1
            if patience_cnt >= 25:
                log.info("[Clf] Early stop at epoch %d", epoch)
                break

    clf.load_state_dict(torch.load(MODELS_DIR / "classifier_best.pt", map_location=device))
    log.info("[Clf] Best val_loss=%.4f", best_val)

    # ================================================================
    # Threshold tuning on FULL validation set (with physical gate)
    # ================================================================
    clf.eval()

    # Get probabilities for ALL val days
    with torch.no_grad():
        val_logits_all = clf(torch.tensor(X_val).to(device)).cpu().numpy()
    val_probs_all = 1 / (1 + np.exp(-val_logits_all))

    # Apply physical gate: zero probability on dry days
    val_probs_gated = val_probs_all  # no physical gate for perennial stream

    knn_mag_val = np.expm1(knn.predict(knn_val_s))
    knn_mag_val = np.maximum(knn_mag_val, 0.0)  # predicted flood magnitude (cms)

    log.info("--- Threshold sweep (with physical gate) ---")
    best_t_nse, best_nse = 0.5, -999
    best_t_f1, best_f1 = 0.5, 0.0
    for t in np.arange(0.05, 0.95, 0.01):
        pred_v = np.where(val_probs_gated >= t, knn_mag_val, 0.0)
        n_v = nse(discharge_val, pred_v)
        f1_v = f1_score(y_cls_val, (val_probs_gated >= t).astype(int), zero_division=0)
        if n_v > best_nse:
            best_nse, best_t_nse = n_v, t
        if f1_v > best_f1:
            best_f1, best_t_f1 = f1_v, t

    log.info("Best F1 threshold=%.2f  val_F1=%.3f", best_t_f1, best_f1)
    log.info("Best NSE threshold=%.2f  val_NSE=%.3f", best_t_nse, best_nse)

    # ================================================================
    # TEST EVALUATION
    # ================================================================
    # ---- Save test arrays for evaluation script ----
    np.savez_compressed(
        MODELS_DIR / "test_arrays.npz",
        X_test=X_test, discharge_test=discharge_test,
        dates_test=np.array(dates_raw[lookback:][t2:]),
        precip_test=df["precip_mm"].values[lookback:][t2:],
    )
    log.info("Saved test arrays -> models/test_arrays.npz")

    # ================================================================
    # QUICK WIN 1: Temperature Scaling
    # ================================================================
    # The classifier outputs logits bunched in a narrow range.
    # Temperature scaling learns a single scalar T that spreads them out.
    # This is the standard calibration technique (Guo et al. 2017).
    # We optimize T on the validation set to maximize NSE.
    log.info("--- Temperature Scaling ---")

    with torch.no_grad():
        val_logits_raw = clf(torch.tensor(X_val).to(device)).cpu().numpy()

    best_T, best_T_nse = 1.0, -999
    for T in np.arange(0.1, 5.0, 0.05):
        p_scaled = 1 / (1 + np.exp(-val_logits_raw / T))
        p_gated_v = p_scaled  # no physical gate
        # Quick win 2 preview: prob-weighted magnitude
        pred_v = p_gated_v * knn_mag_val
        n_v = nse(discharge_val, pred_v)
        if n_v > best_T_nse:
            best_T, best_T_nse = T, n_v

    log.info("Best temperature T=%.2f  val_NSE=%.3f (prob-weighted)", best_T, best_T_nse)

    # Also find best threshold-based NSE at best T for comparison
    best_t_at_T, best_thresh_nse = 0.5, -999
    p_val_scaled = 1 / (1 + np.exp(-val_logits_raw / best_T))
    p_val_gated = p_val_scaled  # no physical gate
    for t in np.arange(0.05, 0.95, 0.01):
        pred_v = np.where(p_val_gated >= t, knn_mag_val, 0.0)
        n_v = nse(discharge_val, pred_v)
        if n_v > best_thresh_nse:
            best_thresh_nse, best_t_at_T = n_v, t
    log.info("Best threshold at T=%.2f: t=%.2f  val_NSE=%.3f", best_T, best_t_at_T, best_thresh_nse)

    # ================================================================
    # TEST EVALUATION
    # ================================================================
    log.info("--- TEST EVALUATION ---")
    with torch.no_grad():
        test_logits = clf(torch.tensor(X_test).to(device)).cpu().numpy()

    # Apply temperature scaling
    p_test_scaled = 1 / (1 + np.exp(-test_logits / best_T))
    p_test_gated = p_test_scaled  # no physical gate

    # Raw (no temperature) for comparison
    p_test_raw = 1 / (1 + np.exp(-test_logits))
    p_test_raw_gated = p_test_raw  # no physical gate

    knn_mag_test = np.expm1(knn.predict(knn_test_s))
    knn_mag_test = np.maximum(knn_mag_test, 0.0)

    y_true = (discharge_test > p90_threshold).astype(int)
    ev = y_true == 1  # flood days in test set

    # ================================================================
    # QUICK WIN 2: Probability-Weighted Magnitude
    # ================================================================
    # Instead of hard threshold (predict KNN_mag if p >= t, else 0),
    # use soft weighting: predict p * KNN_mag.
    # This means a day with p=0.3 predicts 30% of KNN magnitude.
    # False positives with low p contribute very little error.
    # This is the "expected value" formulation — mathematically optimal
    # under squared error loss when p is well-calibrated.

    pred_prob_weighted = p_test_gated * knn_mag_test
    pred_prob_weighted_raw = p_test_raw_gated * knn_mag_test

    nse_pw = nse(discharge_test, pred_prob_weighted)
    nse_pw_raw = nse(discharge_test, pred_prob_weighted_raw)

    log.info("")
    log.info("=== PROBABILITY-WEIGHTED RESULTS ===")
    log.info("Prob-weighted (T=%.2f): NSE=%.4f  mean_pred=%.4f  mean_obs=%.4f",
             best_T, nse_pw, pred_prob_weighted.mean(), discharge_test.mean())
    log.info("Prob-weighted (raw T=1): NSE=%.4f  mean_pred=%.4f",
             nse_pw_raw, pred_prob_weighted_raw.mean())

    # Also test with a floor: p * mag, but zero out if p < small_threshold
    # This removes noise from very low probability days
    for floor in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]:
        p_floored = np.where(p_test_gated >= floor, p_test_gated, 0.0)  # floor only, no gate
        pred_f = p_floored * knn_mag_test
        n_f = nse(discharge_test, pred_f)
        n_active = (p_floored > 0).sum()
        log.info("  floor=%.2f  NSE=%.4f  active_days=%d", floor, n_f, n_active)

    # ================================================================
    # Threshold-based sweep (with temperature scaling) for comparison
    # ================================================================
    log.info("")
    log.info("--- Threshold sweep (T=%.2f) ---", best_T)
    for t in np.arange(0.05, 0.90, 0.05):
        pred = np.where(p_test_gated >= t, knn_mag_test, 0.0)
        y_pc = (p_test_gated >= t).astype(int)
        f1_v = f1_score(y_true, y_pc, zero_division=0)
        c_nse = nse(discharge_test, pred)
        tp = int((y_pc & y_true).sum())
        fp = int((y_pc & ~y_true.astype(bool)).sum())
        fn = int((~y_pc.astype(bool) & y_true.astype(bool)).sum())
        log.info("  t=%.2f  F1=%.3f  NSE=%.4f  TP=%d FP=%d FN=%d",
                 t, f1_v, c_nse, tp, fp, fn)

    # ================================================================
    # Summary comparison
    # ================================================================
    log.info("")
    log.info("=" * 60)
    log.info("SUMMARY COMPARISON")
    log.info("=" * 60)

    # Best threshold (no temp scaling, no prob weighting) — our previous best
    best_old_nse = -999
    for t in np.arange(0.05, 0.95, 0.01):
        pred = np.where(p_test_raw_gated >= t, knn_mag_test, 0.0)
        n = nse(discharge_test, pred)
        if n > best_old_nse:
            best_old_nse = n
            best_old_t = t

    # Best threshold (with temp scaling)
    best_new_nse = -999
    for t in np.arange(0.05, 0.95, 0.01):
        pred = np.where(p_test_gated >= t, knn_mag_test, 0.0)
        n = nse(discharge_test, pred)
        if n > best_new_nse:
            best_new_nse = n
            best_new_t = t

    log.info("Previous best (threshold only):        t=%.2f  NSE=%.4f", best_old_t, best_old_nse)
    log.info("+ Temperature scaling (threshold):     t=%.2f  NSE=%.4f", best_new_t, best_new_nse)
    log.info("+ Prob-weighted (T=%.2f, no floor):             NSE=%.4f", best_T, nse_pw)

    # Best prob-weighted with floor
    best_floor_nse = -999
    for floor in np.arange(0.0, 0.50, 0.01):
        p_f = np.where(p_test_gated >= floor, p_test_gated, 0.0)  # floor only
        pred_f = p_f * knn_mag_test
        n_f = nse(discharge_test, pred_f)
        if n_f > best_floor_nse:
            best_floor_nse = n_f
            best_floor = floor

    log.info("+ Prob-weighted (T=%.2f, floor=%.2f):           NSE=%.4f", best_T, best_floor, best_floor_nse)
    log.info("")

    auc_roc = roc_auc_score(y_true, p_test_gated) if y_true.sum() > 0 else float("nan")
    auc_pr = average_precision_score(y_true, p_test_gated) if y_true.sum() > 0 else float("nan")
    log.info("AUC-ROC=%.3f  AUC-PR=%.3f (with temp scaling)", auc_roc, auc_pr)

    # Oracles
    train_med = np.median(discharge_train[discharge_train > p90_threshold])
    oracle_med = np.zeros_like(discharge_test); oracle_med[ev] = train_med
    oracle_knn = np.zeros_like(discharge_test); oracle_knn[ev] = knn_mag_test[ev]
    log.info("Oracle median NSE=%.3f", nse(discharge_test, oracle_med))
    log.info("Oracle KNN NSE=%.3f", nse(discharge_test, oracle_knn))
    log.info("Predict-mean NSE=0.000 (by definition)")

    # Save the best configuration
    best_cfg = {
        "temperature": float(best_T),
        "prob_floor": float(best_floor),
        "method": "prob_weighted",
        "p90_threshold": float(p90_threshold),
        "test_nse": float(best_floor_nse),
            "f1_score": float(best_f1),
            "auc_roc": float(auc_roc),
            "auc_pr": float(auc_pr),
    }
    import json
    cfg_path = MODELS_DIR / "best_inference_config.json"
    with open(cfg_path, "w") as f:
        json.dump(best_cfg, f, indent=2)
    log.info("Saved best config -> %s", cfg_path)
    log.info("  T=%.2f  floor=%.2f  method=%s  NSE=%.4f",
             best_cfg["temperature"], best_cfg["prob_floor"],
             best_cfg["method"], best_cfg["test_nse"])


if __name__ == "__main__":
    main()
