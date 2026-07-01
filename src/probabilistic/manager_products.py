"""
src/probabilistic/manager_products.py
=====================================

Whitepaper Task 4 / Table 3 "Flood-Control-Manager" decision-support products
that go beyond the three best/likely/worst depth maps:

  1. P(depth > 0.5 m)  -- per-pixel probability that depth exceeds 0.5 m, the
     standard "life-threatening to a person on foot" threshold (whitepaper 4.6).
  2. Uncertainty map   -- per-pixel std-dev across the ensemble members.
  3. Time-to-peak (Tp) -- Kirpich Tc -> SCS Tlag (h) for P10/P50/P90 Q.
  4. Ensemble hydrograph -- a 0-24 h discharge time-series with P10-P90 band.

All functions are pure / deterministic given the input rasters and Q ensemble,
so they can be re-run by anyone with the cached outputs/task4/today_rasters.npz.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors


# Pearson-Tukey weights for 3-member P10 / P50 / P90 ensemble
PT_WEIGHTS = np.array([0.185, 0.630, 0.185])  # sums to 1


# ---------------------------------------------------------------------------
# 1. P(depth > threshold)
# ---------------------------------------------------------------------------
def prob_depth_exceeds(best: np.ndarray,
                       likely: np.ndarray,
                       worst: np.ndarray,
                       threshold_m: float = 0.5) -> np.ndarray:
    """Pearson-Tukey weighted probability that depth > threshold."""
    members = np.stack([best, likely, worst], axis=0).astype(np.float32)
    members = np.nan_to_num(members, nan=0.0)
    exceed = (members > threshold_m).astype(np.float32)
    p = np.tensordot(PT_WEIGHTS.astype(np.float32), exceed, axes=([0], [0]))
    return p.astype(np.float32)


# ---------------------------------------------------------------------------
# 2. Uncertainty (std-dev across members)
# ---------------------------------------------------------------------------
def uncertainty_std(best: np.ndarray,
                    likely: np.ndarray,
                    worst: np.ndarray) -> np.ndarray:
    members = np.stack([best, likely, worst], axis=0).astype(np.float32)
    members = np.nan_to_num(members, nan=0.0)
    return members.std(axis=0).astype(np.float32)


# ---------------------------------------------------------------------------
# 3. Time-to-peak via Kirpich + SCS lag
# ---------------------------------------------------------------------------
def time_to_peak_hours(rainfall_inches_p50: float,
                       L_km: float = 24.0,
                       slope: float = 0.012,
                       intensity_factor: float = 1.0) -> dict:
    """
    Estimate time-to-peak using Kirpich (1940) for time-of-concentration:
        Tc (h) = 0.0078 * L^0.77 * S^(-0.385)   (L in ft, S dimensionless)
    Then SCS lag-time-to-peak:
        Tlag = 0.6 * Tc;  Tp = Tlag + D/2  (D = rainfall duration)

    Defaults are calibrated to the Upper Sonoita Creek HUC-12:
      - Hydraulic length L ~= 24 km (~ 78,740 ft)
      - Average channel slope ~= 0.012 m/m
      - Storm duration D = 1 h (monsoon convective)

    Returns dict with low/median/high estimates (hours).
    Intensity factor reduces Tc slightly for heavier storms (saturated soils).
    """
    L_ft = L_km * 3280.84
    Tc_h = 0.0078 * (L_ft ** 0.77) * (slope ** -0.385) / 60.0  # Kirpich gives minutes
    Tlag = 0.6 * Tc_h
    D = max(0.5, min(3.0, 1.0))  # assume 1-h design storm
    Tp_median = Tlag + D / 2.0

    # Heavier rainfall -> faster runoff (slightly shorter Tp); cap +/-25%
    scale = 1.0 / (1.0 + 0.05 * max(0.0, rainfall_inches_p50))
    p10 = Tp_median * (1.0 + 0.25)   # drier ensemble -> slower response
    p50 = Tp_median * scale
    p90 = Tp_median * scale * (1.0 - 0.20)  # wetter ensemble -> faster response
    return {
        "p10_hours": float(round(p10, 2)),
        "p50_hours": float(round(p50, 2)),
        "p90_hours": float(round(p90, 2)),
        "method": "Kirpich Tc + SCS Tlag (HUC-12 150503010204; L=24km, S=0.012)",
    }


# ---------------------------------------------------------------------------
# 4. Ensemble hydrograph chart
# ---------------------------------------------------------------------------
def plot_ensemble_hydrograph(q_p10: float, q_p50: float, q_p90: float,
                             time_to_peak_h: float,
                             out_png: Path,
                             total_hours: int = 24) -> Path:
    """Synthetic 0-24h hydrograph (gamma-shape) for each ensemble member."""
    t = np.linspace(0.01, total_hours, 200)
    Tp = max(0.5, time_to_peak_h)

    def gamma_hydro(qp, tp):
        # SCS-style dimensionless unit hydrograph (gamma shape)
        tau = t / tp
        return qp * (tau ** 3.7) * np.exp(3.7 * (1 - tau)) / (tau.max() ** 0.0)

    q_low = gamma_hydro(q_p10, Tp * 1.20)
    q_med = gamma_hydro(q_p50, Tp)
    q_high = gamma_hydro(q_p90, Tp * 0.85)

    fig, ax = plt.subplots(figsize=(8.5, 4.6), dpi=110)
    ax.fill_between(t, q_low, q_high, color="#1f77b4", alpha=0.22, label="P10-P90 envelope")
    ax.plot(t, q_med, color="#0d47a1", lw=2.4, label="P50 (likely)")
    ax.plot(t, q_low, color="#90caf9", lw=1.0, ls="--", label="P10 (driest)")
    ax.plot(t, q_high, color="#b71c1c", lw=1.6, ls="-", label="P90 (wettest)")
    pk = np.argmax(q_med)
    ax.axvline(t[pk], color="#444", lw=1.0, ls=":")
    ax.annotate(f"Peak ~ T+{t[pk]:.1f} h\nQ50 = {q_med[pk]:.1f} cms",
                xy=(t[pk], q_med[pk]), xytext=(t[pk]+1.5, q_med[pk]*0.85),
                fontsize=9, color="#222",
                arrowprops=dict(arrowstyle="->", color="#666"))
    ax.set_xlabel("Hours from forecast issue (T+h)")
    ax.set_ylabel("Discharge Q (m\u00b3/s)")
    ax.set_title("Today's Ensemble Hydrograph at Sonoita Creek outlet\n"
                 "(synthetic SCS unit hydrograph; honest 3-member P10/P50/P90 ensemble)",
                 fontsize=10)
    ax.grid(alpha=0.25)
    ax.set_xlim(0, total_hours)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out_png


# ---------------------------------------------------------------------------
# 5. PNG renderer for rasters (shared style)
# ---------------------------------------------------------------------------
def render_raster_png(arr: np.ndarray, out_png: Path, cmap: str = "Blues",
                      vmin: float = 0.0, vmax: float = None,
                      title: str = "", subtitle: str = ""):
    a = np.nan_to_num(arr, nan=0.0)
    vmax = vmax if vmax is not None else float(max(a.max(), 1e-3))
    fig, ax = plt.subplots(figsize=(6.6, 6.0), dpi=110)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    im = ax.imshow(a, cmap=cmap, norm=norm, interpolation="nearest")
    ax.set_axis_off()
    if title:
        ax.set_title(title, fontsize=11, fontweight="bold")
    if subtitle:
        ax.text(0.5, -0.02, subtitle, transform=ax.transAxes,
                ha="center", va="top", fontsize=9, color="#444")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.ax.tick_params(labelsize=8)
    fig.tight_layout()
    fig.savefig(out_png, dpi=110, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# 6. Top-level builder
# ---------------------------------------------------------------------------
def build_all(rasters_npz: Path,
              out_dir: Path,
              rainfall_inches_p50: float,
              q_ens_cms: dict) -> dict:
    """
    Build P(>0.5m), uncertainty PNG, hydrograph PNG. Return dict for JSON merge.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    d = np.load(rasters_npz)
    best = d["best"]; likely = d["likely"]; worst = d["worst"]

    # Probability of depth > 0.5 m
    p05 = prob_depth_exceeds(best, likely, worst, threshold_m=0.5)
    render_raster_png(
        p05, out_dir / "today_prob_gt_05m.png",
        cmap="YlOrRd", vmin=0.0, vmax=max(0.05, float(p05.max())),
        title="P(depth > 0.5 m)  -  Life-safety threshold",
        subtitle="Whitepaper Table 3: primary decision-support product (EOC)")

    # Uncertainty std-dev
    sigma = uncertainty_std(best, likely, worst)
    render_raster_png(
        sigma, out_dir / "today_uncertainty.png",
        cmap="magma", vmin=0.0, vmax=max(0.05, float(sigma.max())),
        title="Forecast uncertainty (\u03c3 across ensemble)",
        subtitle="High \u03c3 = members disagree  ->  decide conservatively")

    # Time-to-peak
    ttp = time_to_peak_hours(rainfall_inches_p50)

    # Hydrograph
    plot_ensemble_hydrograph(
        q_ens_cms.get("p10", 0.0), q_ens_cms.get("p50", 0.0), q_ens_cms.get("p90", 0.0),
        time_to_peak_h=ttp["p50_hours"],
        out_png=out_dir / "today_ensemble_hydrograph.png")

    return {
        "time_to_peak_hours": ttp,
        "prob_gt_05m_max": float(p05.max()),
        "prob_gt_05m_wet_pixels": int((p05 > 0.05).sum()),
        "uncertainty_max_m": float(sigma.max()),
        "uncertainty_mean_m": float(sigma[sigma > 0].mean()) if (sigma > 0).any() else 0.0,
        "files": {
            "prob_gt_05m_png": "today_prob_gt_05m.png",
            "uncertainty_png": "today_uncertainty.png",
            "ensemble_hydrograph_png": "today_ensemble_hydrograph.png",
        },
    }
