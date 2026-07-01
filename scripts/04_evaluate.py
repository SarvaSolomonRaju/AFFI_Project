"""
scripts/04_evaluate.py
======================
Evaluation plots for the Task 2 Hurdle Model.
Reads models/test_arrays.npz (saved by 03_train_hurdle.py).

Panels:
  1. Scatter  — Observed vs Predicted (log scale, flood/no-flood colored)
  2. Hydrograph — Full test period time series
  3. Hydrograph zoom — Monsoon 2020 (best flood season in test set)
  4. Confusion matrix — Classifier at best threshold

Run:
  python scripts/04_evaluate.py
Output:
  reports/figures/task2_evaluation.png
"""
from __future__ import annotations
import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.colors import ListedColormap
from pathlib import Path
from sklearn.metrics import confusion_matrix, ConfusionMatrixDisplay
import pandas as pd

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT        = Path(__file__).resolve().parents[1]
MODELS_DIR  = ROOT / "models"
REPORTS_DIR = ROOT / "reports" / "figures"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILE   = MODELS_DIR / "test_arrays.npz"
CFG_FILE    = MODELS_DIR / "best_inference_config.json"

# ── Load arrays ──────────────────────────────────────────────────────────────
print("Loading test arrays...")
arrs = np.load(DATA_FILE)
y_obs  = arrs["y_obs"]        # observed discharge (cms)
y_pred = arrs["y_pred"]       # predicted discharge (cms)
p_flood = arrs["p_flood"]     # classifier flood probability
dates  = pd.to_datetime(arrs["dates"])

cfg = json.loads(CFG_FILE.read_text())
threshold  = cfg["threshold"]   # classifier threshold at best NSE
p90        = cfg["p90_threshold"]  # flood onset threshold (cms)

print(f"  Test samples : {len(y_obs)}")
print(f"  Date range   : {dates[0].date()} → {dates[-1].date()}")
print(f"  Threshold    : p={threshold:.2f}  P90={p90:.3f} cms")

# Derived masks
flood_obs  = y_obs  >= p90
flood_pred = (p_flood >= threshold) 

# ── NSE helper ───────────────────────────────────────────────────────────────
def nse(obs, pred):
    denom = np.sum((obs - obs.mean())**2)
    return 1.0 - np.sum((obs - pred)**2) / denom if denom > 0 else np.nan

# ── Figure layout ─────────────────────────────────────────────────────────────
fig = plt.figure(figsize=(16, 14), facecolor="#0f1923")
fig.suptitle(
    "Task 2 — Hurdle Model Evaluation\n"
    "Babocomari River @ USGS-09471000  |  LSTM Classifier + XGBoost Regressor",
    color="white", fontsize=14, fontweight="bold", y=0.98
)

# Grid: 2 rows × 2 cols
ax1 = fig.add_subplot(2, 2, 1)   # scatter
ax2 = fig.add_subplot(2, 2, 2)   # confusion matrix
ax3 = fig.add_subplot(2, 1, 2)   # full hydrograph (bottom row spans both cols)

dark_bg = "#0f1923"
panel_bg = "#1a2535"
for ax in [ax1, ax2, ax3]:
    ax.set_facecolor(panel_bg)
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#3a4a5a")

# ════════════════════════════════════════════════════════════════════════════
# PANEL 1: Scatter — Observed vs Predicted
# ════════════════════════════════════════════════════════════════════════════
eps = 0.01  # avoid log(0)
colors = np.where(flood_obs, "#ff6b35", "#4fc3f7")  # orange=flood, blue=normal

ax1.scatter(np.maximum(y_obs, eps), np.maximum(y_pred, eps),
            c=colors, alpha=0.55, s=18, linewidths=0)

# 1:1 line
mn = eps; mx = max(y_obs.max(), y_pred.max()) * 1.1
ax1.plot([mn, mx], [mn, mx], "w--", lw=1, alpha=0.5, label="1:1 line")
ax1.set_xscale("log"); ax1.set_yscale("log")
ax1.set_xlim(mn, mx); ax1.set_ylim(mn, mx)
ax1.set_xlabel("Observed discharge (cms)", color="white", fontsize=10)
ax1.set_ylabel("Predicted discharge (cms)", color="white", fontsize=10)
ax1.set_title(f"Scatter  |  NSE = {nse(y_obs, y_pred):.4f}", color="white", fontsize=11)

# legend patches
from matplotlib.patches import Patch
ax1.legend(handles=[
    Patch(color="#ff6b35", label=f"Flood (≥P90={p90:.2f} cms)"),
    Patch(color="#4fc3f7", label="Normal flow"),
], facecolor=panel_bg, labelcolor="white", fontsize=8, loc="upper left")

# Annotate PBIAS
pbias = 100 * np.sum(y_pred - y_obs) / np.sum(y_obs)
ax1.text(0.97, 0.05, f"PBIAS = {pbias:+.1f}%",
         transform=ax1.transAxes, ha="right", color="#ffd54f", fontsize=9)

# ════════════════════════════════════════════════════════════════════════════
# PANEL 2: Confusion Matrix
# ════════════════════════════════════════════════════════════════════════════
cm = confusion_matrix(flood_obs.astype(int), flood_pred.astype(int))
disp = ConfusionMatrixDisplay(confusion_matrix=cm,
                               display_labels=["No Flood", "Flood"])
disp.plot(ax=ax2, colorbar=False, cmap="Blues")
ax2.set_title(f"Confusion Matrix  |  threshold = {threshold:.2f}",
              color="white", fontsize=11)
ax2.set_facecolor(panel_bg)
ax2.xaxis.label.set_color("white")
ax2.yaxis.label.set_color("white")
ax2.tick_params(colors="white")
for text in disp.text_.ravel():
    text.set_color("black")

# Metrics annotation
TP, FN = cm[1,1], cm[1,0]
FP, TN = cm[0,1], cm[0,0]
prec = TP / (TP + FP + 1e-9)
rec  = TP / (TP + FN + 1e-9)
f1   = 2 * prec * rec / (prec + rec + 1e-9)
ax2.text(0.5, -0.18,
         f"Precision={prec:.3f}  Recall={rec:.3f}  F1={f1:.3f}",
         transform=ax2.transAxes, ha="center", color="#ffd54f", fontsize=9)

# ════════════════════════════════════════════════════════════════════════════
# PANEL 3: Hydrograph — full test period
# ════════════════════════════════════════════════════════════════════════════
ax3.fill_between(dates, 0, y_obs,  alpha=0.35, color="#4fc3f7", label="Observed")
ax3.plot(dates, y_obs,  color="#4fc3f7", lw=0.8, alpha=0.9)
ax3.plot(dates, y_pred, color="#ff6b35", lw=1.2, alpha=0.9, label="Predicted")

# Shade flood events
ax3.fill_between(dates, 0, y_obs.max() * 1.05,
                 where=flood_obs, alpha=0.12, color="#ff6b35",
                 label=f"Observed flood (≥{p90:.2f} cms)")

# P90 line
ax3.axhline(p90, color="#ffd54f", lw=0.8, ls="--", alpha=0.7, label=f"P90 = {p90:.2f} cms")

ax3.set_xlabel("Date", color="white", fontsize=10)
ax3.set_ylabel("Discharge (cms)", color="white", fontsize=10)
ax3.set_title(
    f"Test Hydrograph  |  NSE={nse(y_obs,y_pred):.4f}  "
    f"Monsoon-NSE={nse(y_obs[dates.month.isin([7,8,9])], y_pred[dates.month.isin([7,8,9])]):.4f}",
    color="white", fontsize=11
)
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
plt.setp(ax3.xaxis.get_majorticklabels(), rotation=30, ha="right", color="white")
ax3.legend(facecolor=panel_bg, labelcolor="white", fontsize=8, loc="upper right")
ax3.set_xlim(dates[0], dates[-1])
ax3.set_ylim(0, y_obs.max() * 1.1)

# ── Metrics text box ─────────────────────────────────────────────────────────
metrics_txt = (
    f"Overall NSE : {nse(y_obs,y_pred):.4f}\n"
    f"Dry NSE     : {nse(y_obs[~flood_obs], y_pred[~flood_obs]):.4f}\n"
    f"High NSE    : {nse(y_obs[flood_obs], y_pred[flood_obs]):.4f}\n"
    f"PBIAS       : {pbias:+.1f}%\n"
    f"MaxObs      : {y_obs.max():.1f} cms\n"
    f"MaxPred     : {y_pred.max():.1f} cms"
)
ax3.text(0.01, 0.97, metrics_txt,
         transform=ax3.transAxes, va="top", color="#ffd54f",
         fontsize=8, family="monospace",
         bbox=dict(boxstyle="round,pad=0.4", facecolor="#0f1923", alpha=0.7))

# ── Save ─────────────────────────────────────────────────────────────────────
plt.tight_layout(rect=[0, 0, 1, 0.96])
out = REPORTS_DIR / "task2_evaluation.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor=dark_bg)
print(f"\n✅ Saved → {out}")

print("\n" + "=" * 60)
print("Rebuilding unified dashboard...")
print("=" * 60)
try:
    import sys
    sys.path.insert(0, str(ROOT))
    from scripts.build_dashboard import generate_html
    html = generate_html()
    dashboard_path = ROOT / "outputs" / "dashboard.html"
    dashboard_path.write_text(html, encoding="utf-8")
    print(f"✅ Dashboard updated → {dashboard_path}")
except Exception as e:
    print(f"⚠️  Dashboard rebuild failed: {e}")
    import traceback
    traceback.print_exc()
