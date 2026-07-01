#!/usr/bin/env python
"""
DEBUG SCRIPT — Why is NSE negative?

For Junior Developer: This script diagnoses why the LSTM is failing to learn.
Run this BEFORE tweaking hyperparameters. Most bugs are in data, not models.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from pathlib import Path

# Configuration
DATA_PATH = Path("data/interim/walnut_gulch_daily.parquet")
SCALERS_PATH = Path("models/scalers/walnut_gulch.joblib")

print("=" * 80)
print("DIAGNOSTIC: Walnut Gulch LSTM Training Failure")
print("=" * 80)

# ============================================================================
# 1. DATA DISTRIBUTION — The "enemy" of LSTM training
# ============================================================================
print("\n[1] DATA DISTRIBUTION ANALYSIS")
print("-" * 80)

df = pd.read_parquet(DATA_PATH)
runoff = df["runoff_mm"].values
precip = df["precip_mm"].values

print(f"Dataset: {len(df)} days ({df.index.min().date()} to {df.index.max().date()})")
print(f"\nRunoff (target variable) — CRITICAL:")
print(f"  Mean:              {runoff.mean():.4f} mm")
print(f"  Std Dev:           {runoff.std():.4f} mm")
print(f"  Min/Max:           {runoff.min():.4f} / {runoff.max():.4f} mm")
print(f"  Median:            {np.median(runoff):.4f} mm")
print(f"  % Zero days:       {100 * (runoff == 0).sum() / len(runoff):.1f}%")
print(f"  % Near-zero (<0.1 mm): {100 * (runoff < 0.1).sum() / len(runoff):.1f}%")

pct_50 = np.percentile(runoff, 50)
pct_90 = np.percentile(runoff, 90)
pct_95 = np.percentile(runoff, 95)
pct_99 = np.percentile(runoff, 99)

print(f"\nPercentiles (shows extreme skewness):")
print(f"  50th (median):     {pct_50:.4f} mm")
print(f"  90th:              {pct_90:.4f} mm")
print(f"  95th:              {pct_95:.4f} mm")
print(f"  99th:              {pct_99:.4f} mm")
print(f"  Ratio (99th/median): {pct_99 / max(pct_50, 1e-6):.1f}x (huge skew!)")

print(f"\nPrecipitation (main driver):")
print(f"  Mean:              {precip.mean():.4f} mm")
print(f"  Std Dev:           {precip.std():.4f} mm")
print(f"  % Zero days:       {100 * (precip == 0).sum() / len(precip):.1f}%")
print(f"  Max single day:    {precip.max():.4f} mm")

print(f"\nKey insight: {100 * (runoff == 0).sum() / len(runoff):.1f}% zero runoff days means:")
print(f"  → Model can naively predict 0 and be correct {100 * (runoff == 0).sum() / len(runoff):.1f}% of the time")
print(f"  → But these zeros are NOT predictable from the 4 features alone")
print(f"  → The LSTM learns 'just predict the mean' because that's easiest")

# ============================================================================
# 2. FEATURE-TARGET CORRELATION — "Can we learn anything?"
# ============================================================================
print("\n[2] FEATURE-TARGET CORRELATION")
print("-" * 80)

features = ["precip_mm", "tmax_c", "tmin_c", "et0_mm"]
correlations = {}
for feat in features:
    corr = np.corrcoef(df[feat].values, runoff)[0, 1]
    correlations[feat] = corr
    strength = "WEAK ⚠" if abs(corr) < 0.3 else "MODERATE" if abs(corr) < 0.6 else "STRONG"
    print(f"  {feat:15s} ↔ runoff_mm:   {corr:+.4f}   {strength}")

max_corr = max(abs(v) for v in correlations.values())
if max_corr < 0.3:
    print(f"\n⚠️  WARNING: ALL correlations are WEAK (<0.3)")
    print(f"   This is the PRIMARY problem. The LSTM has no clear pattern to learn.")
    print(f"   Without strong input-output correlation, no ML model can perform well.")
elif max_corr < 0.5:
    print(f"\n⚠️  MODERATE: Correlations are weak-to-moderate. The signal is noisy.")

# ============================================================================
# 3. TEMPORAL DYNAMICS — "Do recent days matter?"
# ============================================================================
print("\n[3] TEMPORAL STRUCTURE (lagged correlations)")
print("-" * 80)

# Compute lag-1 autocorrelation of runoff
runoff_lag1 = np.corrcoef(runoff[:-1], runoff[1:])[0, 1]
precip_lag1 = np.corrcoef(precip[:-1], precip[1:])[0, 1]

print(f"Runoff autocorr (t → t+1): {runoff_lag1:+.4f}")
print(f"  → Low autocorr (<0.3) means day-to-day runoff is chaotic, hard to predict")

print(f"\nPrecipitation autocorr (t → t+1): {precip_lag1:+.4f}")
print(f"  → Low autocorr means rainfall is sparse and intermittent")

print(f"\nImplication for lookback=30:")
print(f"  → If runoff is chaotic, 30-day history may be too long")
print(f"  → Consider testing lookback=7 or lookback=14 instead")
print(f"  → For flashy watersheds, recent days (last 3-7) matter most")

# ============================================================================
# 4. SCALED SPACE INSPECTION — "Did the preprocessing break things?"
# ============================================================================
print("\n[4] SCALING & LOG-TRANSFORM CHECK")
print("-" * 80)

import joblib
if SCALERS_PATH.exists():
    scalers = joblib.load(SCALERS_PATH)
    
    # Apply log1p + scale to runoff
    runoff_log = np.log1p(runoff.reshape(-1, 1))
    runoff_scaled = scalers.target.transform(runoff_log)
    
    print(f"Original runoff: mean={runoff.mean():.4f}, std={runoff.std():.4f}")
    print(f"After log1p:     mean={runoff_log.mean():.4f}, std={runoff_log.std():.4f}")
    print(f"After scaling:   mean={runoff_scaled.mean():.4f}, std={runoff_scaled.std():.4f}")
    print(f"\nScaler denominator (from training log): {scalers.config}")
    
    # Check basin_std calculation
    print(f"\n⚠️  Check this number matches training log output:")
    print(f"   Training printed: 'basin train target std (scaled space): 0.9474'")
    print(f"   Actual std(runoff_scaled): {runoff_scaled.std():.4f}")
    if abs(runoff_scaled.std() - 0.9474) < 0.05:
        print(f"   ✓ Match! Scaling is correct.")
    else:
        print(f"   ✗ MISMATCH! Possible scaling bug.")
else:
    print(f"Scalers file not found at {SCALERS_PATH}")

# ============================================================================
# 5. BASELINE COMPARISON — "Is the LSTM even necessary?"
# ============================================================================
print("\n[5] NAIVE BASELINES (for context)")
print("-" * 80)

# Baseline 1: Mean predictor
mean_pred = np.full_like(runoff, runoff.mean())
mse_mean = np.mean((mean_pred - runoff) ** 2)
nse_mean = 1.0 - np.sum((mean_pred - runoff)**2) / np.sum((runoff - runoff.mean())**2)
print(f"Baseline 1 — Always predict mean ({runoff.mean():.4f}):")
print(f"  NSE = {nse_mean:.4f} (this is the reference line)")

# Baseline 2: Persistence (predict previous day's runoff)
persist_pred = np.concatenate([[runoff.mean()], runoff[:-1]])
nse_persist = 1.0 - np.sum((persist_pred - runoff)**2) / np.sum((runoff - runoff.mean())**2)
print(f"\nBaseline 2 — Persistence (predict t-1 as t):")
print(f"  NSE = {nse_persist:.4f}")

# Baseline 3: Precipitation rule (runoff ~ precip)
precip_rule = 0.5 * precip  # naive: runoff = 50% of precip
nse_precip = 1.0 - np.sum((precip_rule - runoff)**2) / np.sum((runoff - runoff.mean())**2)
print(f"\nBaseline 3 — Simple rule (runoff = 0.5 × precip):")
print(f"  NSE = {nse_precip:.4f}")

print(f"\n✓ Your LSTM NSE (-0.0519) should beat these baselines.")
print(f"  If even the mean (NSE=0) is hard to beat, the problem is DATA not MODEL.")

# ============================================================================
# 6. DIAGNOSIS & RECOMMENDATIONS
# ============================================================================
print("\n[6] DIAGNOSIS & FIXES")
print("=" * 80)

if max_corr < 0.3:
    print(f"\n🔴 PRIMARY ISSUE: Weak feature-target correlation")
    print(f"\nROOT CAUSE:")
    print(f"  Walnut Gulch is a FLASHY ARID BASIN. Runoff depends on:")
    print(f"    • Antecedent soil moisture (not observed!)")
    print(f"    • Storm intensity & timing (averaged to daily precip)")
    print(f"    • Basin saturation state (hysteresis)")
    print(f"  Your 4 features (precip, tmax, tmin, et0) are weak predictors alone.")
    print(f"\nFIXES TO TRY (in order):")
    print(f"\n  1. ADD DERIVED FEATURES:")
    print(f"     - Cumulative precip last 7/14/30 days (memory)")
    print(f"     - Daily precip intensity (high-intensity storms matter more)")
    print(f"     - Seasonal indicator (monsoon vs dry season)")
    print(f"     - Lagged runoff itself (t-1, t-2, ..., t-7)")
    print(f"\n  2. ARCHITECTURE CHANGES:")
    print(f"     - Reduce hidden_size from 128 → 32 (was overfitting noise)")
    print(f"     - Reduce num_layers from 2 → 1 (Occam's razor)")
    print(f"     - Increase dropout from 0.3 → 0.5 (more regularization)")
    print(f"\n  3. TRAINING CHANGES:")
    print(f"     - Reduce lookback from 30 → 7 (arid basin doesn't need 30 days)")
    print(f"     - Increase learning rate back to 1e-3 (current 5e-4 may be too small)")
    print(f"     - Remove early stopping patience (let it train longer)")
    print(f"\n  4. DATA INVESTIGATION:")
    print(f"     - Plot: Does precip spikes align with runoff peaks?")
    print(f"     - Check: Are there NaN or suspicious values?")
    print(f"     - Check: Is the USGS data quality-controlled (QC flags)?")

elif max_corr < 0.5:
    print(f"\n🟡 MODERATE ISSUE: Weak-to-moderate feature correlation")
    print(f"\nFIXES TO TRY:")
    print(f"  1. Reduce model capacity (hidden=64, layers=1)")
    print(f"  2. Increase regularization (dropout=0.4)")
    print(f"  3. Add lagged features (previous days' values)")
    print(f"  4. Test shorter lookback (7-14 days)")

else:
    print(f"\n🟢 GOOD: Feature correlation is reasonable ({max_corr:.2f})")
    print(f"\nThe issue is likely in MODEL or TRAINING setup:")
    print(f"  1. Check learning rate schedule (ReduceLROnPlateau working?)")
    print(f"  2. Try different hidden sizes: 32, 64, 128, 256")
    print(f"  3. Check if log1p transform is appropriate")

print("\n" + "=" * 80)
print("NEXT STEP: Run this script. Find the colored diagnostics above.")
print("Then apply the corresponding fixes in order.")
print("=" * 80)
