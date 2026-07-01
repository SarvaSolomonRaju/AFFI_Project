"""
features.py -- Feature engineering for Task 2 hydrology model.
"""
from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import joblib


def build_sequences(
    df: pd.DataFrame,
    lookback: int = 30,
    fit_scaler: bool = True,
    scaler_path: Path | None = None,
    target_col: str = "discharge_cms",
    event_threshold: float = 0.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, StandardScaler]:
    """Build (X, y_cls, y_reg) sequences from daily dataframe.

    Parameters
    ----------
    target_col : str
        Column name for the target variable (default: discharge_cms).
    event_threshold : float
        Value above which a day is classified as a "flood event".
        For Babocomari P90 = 0.878 cms. Pass 0.0 to recover old behavior.

    Returns
    -------
    X        : float32 array (N, lookback, F)
    y_cls    : float32 array (N,)  — 1 if target > event_threshold
    y_reg    : float32 array (N,)  — log1p(target) if event, else NaN
    scaler   : fitted StandardScaler
    """
    df = df.copy()

    # ── Hydrology-informed features ──────────────────────────────────
    precip = df["precip_mm"].values

    # 1. Antecedent Precipitation Index (API) — exponential soil moisture proxy
    api = np.zeros(len(df), dtype=np.float64)
    k = 0.85
    for i in range(1, len(df)):
        api[i] = precip[i] + k * api[i - 1]
    df["api_085"] = api.astype(np.float32)

    # 2. Consecutive dry days (days since last rain > 0.5mm)
    cdd = np.zeros(len(df), dtype=np.float32)
    for i in range(1, len(df)):
        cdd[i] = 0.0 if precip[i] > 0.5 else cdd[i - 1] + 1.0
    df["consec_dry_days"] = cdd

    # 3. Monsoon flag (Jul-Sep when 95% of events occur in AZ)
    month = pd.to_datetime(df.index).month
    df["monsoon"] = ((month >= 7) & (month <= 9)).astype(np.float32)

    # 4. Cyclical day-of-year encoding
    doy = pd.to_datetime(df.index).dayofyear
    df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25).astype(np.float32)
    df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25).astype(np.float32)

    # 5. Rolling precipitation sums (3-day and 7-day accumulation)
    df["precip_3d"] = df["precip_mm"].rolling(3, min_periods=1).sum().astype(np.float32)
    df["precip_7d"] = df["precip_mm"].rolling(7, min_periods=1).sum().astype(np.float32)

    # 6. API x precip interaction (wet soil + rain = flood)
    df["api_x_precip"] = (df["api_085"] * df["precip_mm"]).astype(np.float32)

    # Exclude target + qc_flag from features
    exclude = {target_col, "qc_flag"}
    feature_cols = [c for c in df.columns if c not in exclude]
    print(f"[features] Using {len(feature_cols)} features: {feature_cols}")
    print(f"[features] Target: {target_col}, event_threshold: {event_threshold}")

    target = df[target_col].values.astype(np.float32)
    feat = df[feature_cols].values.astype(np.float32)

    # Scale features
    if fit_scaler:
        scaler = StandardScaler()
        feat = scaler.fit_transform(feat)
        if scaler_path:
            scaler_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(scaler, scaler_path)
            print(f"Scaler saved -> {scaler_path}")
    else:
        if scaler_path and scaler_path.exists():
            scaler = joblib.load(scaler_path)
            feat = scaler.transform(feat)
        else:
            raise FileNotFoundError(f"Scaler not found at {scaler_path}")

    # Build sliding windows
    N = len(feat) - lookback
    X = np.zeros((N, lookback, feat.shape[1]), dtype=np.float32)
    y_cls = np.zeros(N, dtype=np.float32)
    y_reg = np.full(N, np.nan, dtype=np.float32)

    for i in range(N):
        X[i] = feat[i : i + lookback]
        val = target[i + lookback]
        if val > event_threshold:
            y_cls[i] = 1.0
            y_reg[i] = np.log1p(val)

    return X, y_cls, y_reg, scaler
