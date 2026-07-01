"""Task 4 - Probabilistic Flood Mapping (end-to-end runner).

For the current 7-day rainfall forecast, identify which pre-computed
flood map (Task 3 library) applies, propagate P10/P50/P90 rainfall
uncertainty into best/likely/worst depth maps, and render PNGs for
the dashboard's User tab.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, BoundaryNorm
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import argparse
from src.probabilistic import (
    FloodMapLibrary,
    propagate_ensemble,
    probability_of_inundation,
    classify_scenario,
)
from src.probabilistic.flood_library import load_real_library
from src.probabilistic.risk_map import expected_depth
from src.probabilistic import manager_products as mgr

# -------------------- Paths --------------------
LIBRARY_PATH = ROOT / "outputs/task3/spatial_predictions.npz"
ALERT_PATH = ROOT / "outputs/task1_alert_packet.json"
OUT_DIR = ROOT / "outputs/task4"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# -------------------- Plotting helpers --------------------
# Flood depth colormap (white = dry, blue ramp = depth)
DEPTH_LEVELS = [0.0, 0.01, 0.1, 0.3, 0.6, 1.0, 1.5, 2.5]
DEPTH_COLORS = [
    "#f7fbff",  # dry
    "#deebf7",  # < 10 cm
    "#9ecae1",  # ankle
    "#4292c6",  # knee
    "#2171b5",  # waist
    "#08519c",  # chest
    "#08306b",  # > 1.5 m
]
DEPTH_CMAP = ListedColormap(DEPTH_COLORS)
DEPTH_NORM = BoundaryNorm(DEPTH_LEVELS, ncolors=len(DEPTH_COLORS))

# PoI colormap (white -> orange -> red)
POI_CMAP = LinearSegmentedColormap.from_list(
    "poi", ["#ffffff", "#fee090", "#fdae61", "#f46d43", "#d73027", "#a50026"]
)


def _draw_depth(ax, depth, title):
    im = ax.imshow(depth, cmap=DEPTH_CMAP, norm=DEPTH_NORM,
                   origin="upper", interpolation="nearest")
    ax.set_title(title, fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])
    return im


def save_depth_png(depth, path, title, dpi=120):
    fig, ax = plt.subplots(figsize=(5, 5))
    im = _draw_depth(ax, depth, title)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04,
                        ticks=DEPTH_LEVELS)
    cbar.set_label("Depth (m)")
    plt.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def save_poi_png(poi, path, title="Probability of Inundation", dpi=120):
    fig, ax = plt.subplots(figsize=(5, 5))
    im = ax.imshow(poi, cmap=POI_CMAP, vmin=0.0, vmax=1.0,
                   origin="upper", interpolation="nearest")
    ax.set_title(title, fontsize=11)
    ax.set_xticks([]); ax.set_yticks([])
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("PoI (0-1)")
    plt.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def save_thumbnail(depth, path, dpi=80):
    fig, ax = plt.subplots(figsize=(2.2, 2.2))
    ax.imshow(depth, cmap=DEPTH_CMAP, norm=DEPTH_NORM,
              origin="upper", interpolation="nearest")
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)
    plt.tight_layout(pad=0.1)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


# -------------------- Main --------------------
def main():
    print("=" * 70)
    print("Task 4: Probabilistic Flood Mapping (library lookup + ensemble)")
    print("=" * 70)

    ap = argparse.ArgumentParser()
    ap.add_argument('--library', choices=['real','synthetic'], default='real',
                    help='real = FEMA+USGS+3DEP library; synthetic = Task-3 .npz (legacy)')
    args, _ = ap.parse_known_args()
    if args.library == 'real':
        library = load_real_library(ROOT/'data/flood_library_real')
        print(f'[1/4] REAL flood library loaded (FEMA NFHL + FEMA BFE + USGS 3DEP + USGS LP-III)')
    else:
        library = FloodMapLibrary.load(LIBRARY_PATH)
        print(f'[1/4] Synthetic (legacy) library loaded from {LIBRARY_PATH}')
    print(f"[1/4] Library loaded: {library.n_maps} maps, "
          f"Q range [{library.q_min_cms:.2f}, {library.q_max_cms:.2f}] cms, "
          f"grid {library.depth_maps.shape[1]}x{library.depth_maps.shape[2]} @ {library.resolution_m} m")

    alert = json.loads(ALERT_PATH.read_text())
    forecast_days = alert["forecast_days"]
    print(f"[2/4] Alert packet loaded: current={alert['current_alert']}, "
          f"{len(forecast_days)} day(s) of forecast")

    # ---- Today (day 0) ensemble ----
    day0 = forecast_days[0]
    today = propagate_ensemble(day0, library)
    print(f"[3/4] Today ({day0['date']}) ensemble propagation:")
    for name in ("best", "likely", "worst"):
        sc = today["scenarios"][name]
        q = sc["lookup"].q_requested_cms
        s = sc["stats"]
        print(f"      {name:6s}: Q={q:6.2f} cms  max_depth={s['max_depth_m']:.3f} m  "
              f"wet={s['wet_area_km2']:.4f} km2")

    # Save PNGs for the 3 scenarios
    save_depth_png(today["scenarios"]["best"]["lookup"].depth_map,
                   OUT_DIR / "today_best.png",
                   f"Best Case (P10 rain={day0['p10_24hr']:.2f}\")")
    save_depth_png(today["scenarios"]["likely"]["lookup"].depth_map,
                   OUT_DIR / "today_likely.png",
                   f"Most Likely (P50 rain={day0['p50_24hr']:.2f}\")")
    save_depth_png(today["scenarios"]["worst"]["lookup"].depth_map,
                   OUT_DIR / "today_worst.png",
                   f"Worst Case (P90 rain={day0['p90_24hr']:.2f}\")")

    # PoI raster
    maps_3 = [today["scenarios"][k]["lookup"].depth_map
              for k in ("best", "likely", "worst")]
    poi = probability_of_inundation(maps_3)
    save_poi_png(poi, OUT_DIR / "today_poi.png",
                 title=f"PoI - {day0['date']}")
    exp_depth = expected_depth(maps_3)
    save_depth_png(exp_depth, OUT_DIR / "today_expected.png",
                   "Expected Depth (weighted)")
    np.savez_compressed(OUT_DIR / "today_rasters.npz",
                        best=maps_3[0], likely=maps_3[1], worst=maps_3[2],
                        poi=poi.astype(np.float32),
                        expected=exp_depth.astype(np.float32))

    # ---- Whitepaper Table-3 manager products ----
    print("[3.5/4] Building Flood-Control-Manager products (P>0.5m, uncertainty, hydrograph, Tp)...")
    mgr_out = mgr.build_all(
        rasters_npz=OUT_DIR / "today_rasters.npz",
        out_dir=OUT_DIR,
        rainfall_inches_p50=float(day0["p50_24hr"]),
        q_ens_cms=today["discharge_cms"],
    )
    print(f"      Tp(p50) = {mgr_out['time_to_peak_hours']['p50_hours']} h ; "
          f"sigma_max = {mgr_out['uncertainty_max_m']:.3f} m ; "
          f"P(>0.5m)_max = {mgr_out['prob_gt_05m_max']:.3f}")

    # ---- 7-day per-day output ----
    print("[4/4] Per-day forecast loop...")
    per_day = []
    for d in forecast_days:
        ens = propagate_ensemble(d, library)
        likely = ens["scenarios"]["likely"]
        worst = ens["scenarios"]["worst"]
        cls_likely = classify_scenario(
            ens["discharge_cms"]["p50"],
            likely["stats"]["max_depth_m"],
            likely["stats"]["wet_area_km2"],
        )
        cls_worst = classify_scenario(
            ens["discharge_cms"]["p90"],
            worst["stats"]["max_depth_m"],
            worst["stats"]["wet_area_km2"],
        )
        # day thumbnail (likely)
        thumb_name = f"day{d['day']}_likely.png"
        save_thumbnail(likely["lookup"].depth_map, OUT_DIR / thumb_name)
        per_day.append({
            "day": d["day"],
            "date": d["date"],
            "alert_level": d["alert_level"],
            "rainfall_inches": {
                "p10": float(d["p10_24hr"]),
                "p50": float(d["p50_24hr"]),
                "p90": float(d["p90_24hr"]),
            },
            "discharge_cms": ens["discharge_cms"],
            "likely": {
                "max_depth_m": likely["stats"]["max_depth_m"],
                "wet_area_km2": likely["stats"]["wet_area_km2"],
                "scenario_class": cls_likely["severity"],
                "caption": cls_likely["caption"],
                "thumbnail": thumb_name,
            },
            "worst": {
                "max_depth_m": worst["stats"]["max_depth_m"],
                "wet_area_km2": worst["stats"]["wet_area_km2"],
                "scenario_class": cls_worst["severity"],
                "caption": cls_worst["caption"],
            },
        })

    today_likely_cls = classify_scenario(
        today["discharge_cms"]["p50"],
        today["scenarios"]["likely"]["stats"]["max_depth_m"],
        today["scenarios"]["likely"]["stats"]["wet_area_km2"],
    )
    today_worst_cls = classify_scenario(
        today["discharge_cms"]["p90"],
        today["scenarios"]["worst"]["stats"]["max_depth_m"],
        today["scenarios"]["worst"]["stats"]["wet_area_km2"],
    )

    summary = {
        "generated_utc": alert["generated_utc"],
        "watershed": alert["watershed"]["name"],
        "current_alert": alert["current_alert"],
        "method": "Discharge-indexed flood-map library lookup with "
                  "P10/P50/P90 rainfall ensemble (advisor's plan).",
        "library": library.index_summary(),
        "today": {
            "date": day0["date"],
            "rainfall_inches": {
                "p10": float(day0["p10_24hr"]),
                "p50": float(day0["p50_24hr"]),
                "p90": float(day0["p90_24hr"]),
            },
            "discharge_cms": today["discharge_cms"],
            "likely_classification": today_likely_cls,
            "worst_classification": today_worst_cls,
            "scenarios_stats": {
                k: today["scenarios"][k]["stats"]
                for k in ("best", "likely", "worst")
            },
            "poi_max": float(poi.max()),
            "poi_mean_in_wet_envelope":
                float(poi[poi > 0].mean()) if (poi > 0).any() else 0.0,
        },
        "manager_products": mgr_out,
        "forecast_7day": per_day,
        "artifacts": {
            "today_best_png": "today_best.png",
            "today_likely_png": "today_likely.png",
            "today_worst_png": "today_worst.png",
            "today_poi_png": "today_poi.png",
            "today_expected_png": "today_expected.png",
            "today_rasters_npz": "today_rasters.npz",
            "today_prob_gt_05m_png": "today_prob_gt_05m.png",
            "today_uncertainty_png": "today_uncertainty.png",
            "today_ensemble_hydrograph_png": "today_ensemble_hydrograph.png",
            "day_thumbnails": [f"day{d['day']}_likely.png"
                               for d in forecast_days],
        },
    }
    (OUT_DIR / "forecast_7day.json").write_text(json.dumps(summary, indent=2))
    (OUT_DIR / "library_index.json").write_text(
        json.dumps(library.index_summary(), indent=2))

    print(f"\nSaved artifacts to {OUT_DIR.relative_to(ROOT)}/")
    print(f"  today_likely.png  ({today_likely_cls['severity']}: "
          f"{today_likely_cls['caption']})")
    print(f"  Worst case today: {today_worst_cls['severity']}")
    print("DONE.")


if __name__ == "__main__":
    main()
