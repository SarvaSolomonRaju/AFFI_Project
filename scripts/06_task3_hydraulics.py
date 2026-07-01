"""
06_task3_hydraulics.py — Task 3: Hydraulic Surrogate Model (v2)
================================================================================
Project: AFFI (AI Flood Forecasting Initiative)
Version: 2.0 — June 2026

PIPELINE:
    1. Build Manning's discharge-depth lookup table
    2. Generate synthetic DEM terrain for Sonoita Creek
    3. Create training dataset (80 discharge scenarios via Manning's equation)
    4. Train ResUNet model on synthetic data
    5. Evaluate model (depth RMSE, CSI, inundation F1)
    6. Apply to Task 2 discharge predictions -> spatial flood maps
    7. Save all artifacts and update summary
"""
from __future__ import annotations
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("task3_hydraulics")

MODELS_DIR  = ROOT / "models" / "task3"
OUTPUTS_DIR = ROOT / "outputs" / "task3"
REPORTS_DIR = ROOT / "reports" / "figures"
TERRAIN_DIR = ROOT / "data" / "terrain"

for d in [MODELS_DIR, OUTPUTS_DIR, REPORTS_DIR, TERRAIN_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def load_task2_outputs() -> dict:
    cfg_path = ROOT / "models" / "sonoita" / "inference_config.json"
    arr_path = ROOT / "models" / "sonoita" / "test_arrays.npz"

    if not cfg_path.exists():
        log.error("Task 2 inference config not found: %s", cfg_path)
        raise FileNotFoundError(str(cfg_path))

    cfg = json.loads(cfg_path.read_text())
    log.info("Task 2 config loaded:")
    log.info("  Basin: %s (USGS %s)", cfg.get("basin"), cfg.get("usgs_id"))
    log.info("  NSE=%.4f  PBIAS=%+.1f%%  F1=%.3f  Recall=%.3f",
             cfg.get("test_nse", 0), cfg.get("test_pbias", 0),
             cfg.get("f1_score", 0), cfg.get("recall", 0))
    log.info("  Model quality: %s",
             cfg.get("model_quality", {}).get("moriasi_class", "unknown"))

    result = {"config": cfg}

    if arr_path.exists():
        arrs = np.load(arr_path)
        result["y_obs"]   = arrs["y_obs"]
        result["y_pred"]  = arrs["y_pred"]
        result["p_flood"] = arrs["p_flood"]
        result["dates"]   = pd.to_datetime(arrs["dates"])
        result["precip"]  = arrs.get("precip_test", None)
        log.info("  Test arrays: %d samples (%s to %s)",
                 len(result["y_obs"]),
                 result["dates"][0].date(), result["dates"][-1].date())
        log.info("  Discharge range: [%.2f, %.2f] cms",
                 result["y_pred"].min(), result["y_pred"].max())

    return result


def compute_mannings_depth(Q_cms, width_m, n_manning, slope):
    rhs = Q_cms * n_manning / (width_m * np.sqrt(slope))
    return np.power(rhs, 3.0 / 5.0)


def build_discharge_depth_lookup(cfg: dict) -> dict:
    CHANNEL_WIDTH    = 15.0
    BANKFULL_WIDTH   = 30.0
    FLOODPLAIN_WIDTH = 200.0
    SLOPE            = 0.008
    MANNINGS_N_CHAN  = 0.045
    MANNINGS_N_FP    = 0.080

    p90 = cfg.get("p90_threshold", 1.67)

    discharge_levels = np.concatenate([
        np.arange(0.1, 2.0, 0.1),
        np.arange(2.0, 10.0, 0.5),
        np.arange(10.0, 50.0, 2.0),
        np.arange(50.0, 200.0, 5.0),
        np.arange(200.0, 501.0, 25.0),
    ])

    lookup = []
    for Q in discharge_levels:
        if Q <= p90 * 1.5:
            depth = compute_mannings_depth(Q, CHANNEL_WIDTH, MANNINGS_N_CHAN, SLOPE)
            extent = CHANNEL_WIDTH
            velocity = Q / (CHANNEL_WIDTH * depth) if depth > 0 else 0
            zone = "in_channel"
        elif Q <= p90 * 15.0:
            depth_chan = compute_mannings_depth(p90 * 1.5, CHANNEL_WIDTH, MANNINGS_N_CHAN, SLOPE)
            Q_excess = Q - p90 * 1.5
            depth_fp = compute_mannings_depth(Q_excess, BANKFULL_WIDTH, MANNINGS_N_FP, SLOPE)
            depth = depth_chan + depth_fp
            frac = min((Q - p90 * 1.5) / (p90 * 13.5), 1.0)
            extent = BANKFULL_WIDTH + frac * (FLOODPLAIN_WIDTH - BANKFULL_WIDTH)
            velocity = Q / (extent * depth) if depth > 0 else 0
            zone = "floodplain"
        else:
            depth_chan = compute_mannings_depth(p90 * 1.5, CHANNEL_WIDTH, MANNINGS_N_CHAN, SLOPE)
            Q_bankfull = p90 * 15.0 - p90 * 1.5
            depth_bf = compute_mannings_depth(Q_bankfull, BANKFULL_WIDTH, MANNINGS_N_FP, SLOPE)
            Q_excess = Q - p90 * 15.0
            depth_extra = compute_mannings_depth(Q_excess, FLOODPLAIN_WIDTH, MANNINGS_N_FP * 1.3, SLOPE)
            depth = depth_chan + depth_bf + depth_extra
            extent = FLOODPLAIN_WIDTH * 1.5
            velocity = Q / (extent * depth) if depth > 0 else 0
            zone = "major_flood"

        lookup.append({
            "discharge_cms": float(Q),
            "depth_m": float(depth),
            "extent_m": float(extent),
            "velocity_ms": float(velocity),
            "zone": zone,
        })

    log.info("Manning's lookup: %d entries (Q=%.1f to %.1f cms)",
             len(lookup), discharge_levels[0], discharge_levels[-1])
    log.info("  Max in-channel depth: %.2f m at Q=%.1f cms",
             max(e["depth_m"] for e in lookup if e["zone"] == "in_channel"),
             max(e["discharge_cms"] for e in lookup if e["zone"] == "in_channel"))

    return {
        "channel_geometry": {
            "channel_width_m": CHANNEL_WIDTH,
            "bankfull_width_m": BANKFULL_WIDTH,
            "floodplain_width_m": FLOODPLAIN_WIDTH,
            "slope_m_per_m": SLOPE,
            "mannings_n_channel": MANNINGS_N_CHAN,
            "mannings_n_floodplain": MANNINGS_N_FP,
        },
        "entries": lookup,
    }


def define_resunet_architecture() -> dict:
    return {
        "model_name": "ResUNet-Hydraulic",
        "version": "2.0",
        "description": "Residual U-Net for discharge-to-depth mapping",
        "input_channels": {
            "ch0": "discharge_cms (scalar broadcast to grid)",
            "ch1": "DEM_normalized (elevation relative to channel bed)",
            "ch2": "slope (local terrain slope)",
            "ch3": "channel_distance (distance to nearest channel, m)",
        },
        "output_channels": {
            "ch0": "flood_depth_m (predicted water depth)",
        },
        "spatial_resolution_m": 10.0,
        "grid_size": [256, 256],
        "coverage_km2": 6.55,
        "encoder": {
            "blocks": [
                {"name": "enc1", "in_ch": 4, "out_ch": 32, "stride": 1},
                {"name": "enc2", "in_ch": 32, "out_ch": 64, "stride": 2},
                {"name": "enc3", "in_ch": 64, "out_ch": 128, "stride": 2},
                {"name": "enc4", "in_ch": 128, "out_ch": 256, "stride": 2},
            ],
        },
        "bottleneck": {"in_ch": 256, "out_ch": 512},
        "decoder": {
            "blocks": [
                {"name": "dec4", "in_ch": 512, "out_ch": 256, "skip_ch": 256},
                {"name": "dec3", "in_ch": 256, "out_ch": 128, "skip_ch": 128},
                {"name": "dec2", "in_ch": 128, "out_ch": 64, "skip_ch": 64},
                {"name": "dec1", "in_ch": 64, "out_ch": 32, "skip_ch": 32},
            ],
        },
        "head": {"in_ch": 32, "out_ch": 1, "activation": "ReLU"},
        "total_params_estimate": "~4.2M",
        "loss_function": "MSE + 5.0 * peak_depth_penalty + 0.1 * volume_conservation",
        "optimizer": "AdamW (lr=1e-3, weight_decay=1e-4)",
        "training": {
            "epochs": 200,
            "batch_size": 16,
            "lr_schedule": "CosineAnnealing(T_max=200)",
            "data_augmentation": ["horizontal_flip", "rotation_90", "noise_injection"],
        },
    }


def build_training_plan(task2_cfg: dict, lookup: dict) -> dict:
    p90 = task2_cfg.get("p90_threshold", 1.67)
    p99 = task2_cfg.get("p99_threshold", 18.48)

    return {
        "project": "AFFI Task 3 — Hydraulic Surrogate",
        "basin": "sonoita_creek",
        "usgs_id": "09481500",
        "created": datetime.now(tz=None).isoformat(),
        "phases": [
            {
                "phase": 1,
                "name": "Manning's Synthetic Training",
                "status": "complete",
                "description": "Synthetic depth maps via Manning's equation on synthetic DEM",
                "n_scenarios": 80,
                "discharge_range_cms": [0.1, 300.0],
                "data_source": "Manning's equation + synthetic DEM",
                "estimated_time_hours": 0.5,
            },
            {
                "phase": 2,
                "name": "HEC-RAS 2D Simulation Library",
                "status": "planned",
                "description": "Run HEC-RAS 2D unsteady simulations for training data",
                "n_scenarios": 250,
                "discharge_range_cms": [0.5, 500.0],
                "return_periods": ["Q2", "Q5", "Q10", "Q25", "Q50", "Q100"],
                "data_source": "HEC-RAS 2D with 3DEP LiDAR terrain",
                "estimated_time_hours": 48,
                "prerequisites": [
                    "HEC-RAS model geometry",
                    "Cross-section surveys",
                    "Manning's n calibration",
                    "Boundary conditions from USGS 09481500",
                ],
            },
            {
                "phase": 3,
                "name": "Real-Event Calibration",
                "status": "future",
                "description": "Calibrate with USGS high-water marks and post-flood surveys",
                "n_events": 5,
                "data_source": "USGS field surveys, satellite imagery",
                "estimated_time_hours": 24,
            },
        ],
        "validation_strategy": {
            "method": "spatial_cross_validation",
            "hold_out_reaches": 2,
            "metrics": ["RMSE_depth", "bias_depth", "CSI_inundation", "F1_inundation"],
            "target_RMSE_m": 0.30,
            "target_CSI": 0.70,
        },
        "task2_input_quality": {
            "nse": task2_cfg.get("test_nse"),
            "pbias": task2_cfg.get("test_pbias"),
            "recall": task2_cfg.get("recall"),
            "moriasi_class": task2_cfg.get("model_quality", {}).get("moriasi_class"),
            "ready": task2_cfg.get("model_quality", {}).get("ready_for_task3"),
        },
        "uncertainty_propagation": {
            "method": "Monte Carlo ensemble (N=100)",
            "discharge_noise_pct": abs(task2_cfg.get("test_pbias", 10)),
            "manning_n_range": [0.035, 0.060],
            "dem_vertical_accuracy_m": 0.15,
        },
    }


def generate_architecture_diagram():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    import matplotlib.patches as mpatches

    dark_bg  = "#0f1923"
    panel_bg = "#1a2535"
    blue     = "#4fc3f7"
    orange   = "#ff6b35"
    green    = "#69f0ae"
    yellow   = "#ffd54f"
    purple   = "#ce93d8"
    red      = "#ef5350"

    fig, ax = plt.subplots(1, 1, figsize=(18, 10), facecolor=dark_bg)
    ax.set_facecolor(dark_bg)
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 10)
    ax.axis("off")

    fig.suptitle(
        "AFFI Pipeline Architecture — Task 1 -> Task 2 -> Task 3",
        color="white", fontsize=16, fontweight="bold", y=0.96
    )

    def draw_box(x, y, w, h, color, label, sublabel="", alpha=0.85):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                              facecolor=color, alpha=alpha, edgecolor="white", linewidth=1.5)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2 + 0.15, label, ha="center", va="center",
                color="white", fontsize=10, fontweight="bold")
        if sublabel:
            ax.text(x + w/2, y + h/2 - 0.25, sublabel, ha="center", va="center",
                    color="white", fontsize=7, alpha=0.8)

    def draw_arrow(x1, y1, x2, y2, color="white"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=2))

    draw_box(0.5, 7.5, 3.0, 1.5, "#1565c0", "Task 1", "Precipitation Forecast\nNWM + GridMET + PRISM")
    draw_box(4.5, 7.5, 3.0, 1.5, "#2e7d32", "Task 2", "Streamflow Prediction\nXGBoost Hurdle v2")
    draw_box(8.5, 7.5, 3.0, 1.5, orange, "Task 3", "Hydraulic Surrogate\nResUNet Depth Map")
    draw_box(12.5, 7.5, 3.0, 1.5, red, "Task 4-6", "Risk Assessment\nAlert + Comms")

    draw_arrow(3.5, 8.25, 4.5, 8.25, blue)
    draw_arrow(7.5, 8.25, 8.5, 8.25, green)
    draw_arrow(11.5, 8.25, 12.5, 8.25, yellow)

    ax.text(4.0, 8.6, "precip_mm", color=blue, fontsize=7, ha="center")
    ax.text(8.0, 8.6, "Q (cms)", color=green, fontsize=7, ha="center")
    ax.text(12.0, 8.6, "depth (m)", color=yellow, fontsize=7, ha="center")

    t3_y = 1.0
    draw_box(1.0, t3_y + 3.5, 2.5, 1.2, "#37474f", "Input Layer", "4 channels\nQ, DEM, slope, dist")
    draw_box(4.0, t3_y + 3.5, 2.5, 1.2, "#1565c0", "Encoder", "Conv+BN+ReLU\n32->64->128->256")
    draw_box(7.0, t3_y + 3.5, 2.5, 1.2, "#6a1b9a", "Bottleneck", "512 channels\nResidual blocks")
    draw_box(10.0, t3_y + 3.5, 2.5, 1.2, "#2e7d32", "Decoder", "TransConv+Skip\n256->128->64->32")
    draw_box(13.0, t3_y + 3.5, 2.5, 1.2, orange, "Output", "1 channel\nflood_depth_m")

    draw_arrow(3.5, t3_y + 4.1, 4.0, t3_y + 4.1, blue)
    draw_arrow(6.5, t3_y + 4.1, 7.0, t3_y + 4.1, blue)
    draw_arrow(9.5, t3_y + 4.1, 10.0, t3_y + 4.1, green)
    draw_arrow(12.5, t3_y + 4.1, 13.0, t3_y + 4.1, green)

    ax.annotate("", xy=(10.5, t3_y + 3.5), xytext=(5.0, t3_y + 3.5),
                arrowprops=dict(arrowstyle="->", color=yellow, lw=1.5,
                                connectionstyle="arc3,rad=-0.3", linestyle="--"))
    ax.text(7.5, t3_y + 2.8, "Skip Connections", color=yellow, fontsize=8, ha="center",
            style="italic")

    draw_box(1.0, t3_y, 3.5, 1.5, "#37474f", "Training Data", "Phase 1: Manning's (80 scen.)\nPhase 2: HEC-RAS (250 scen.)\nPhase 3: Real events (5)")
    draw_box(5.5, t3_y, 3.5, 1.5, "#37474f", "Validation", "Spatial CV (2 hold-out)\nTarget: RMSE<0.30m\nTarget: CSI>0.70")
    draw_box(10.0, t3_y, 3.5, 1.5, "#37474f", "Uncertainty", "MC Ensemble (N=100)\nQ noise + Manning's n\nDEM accuracy 0.15m")

    metrics_text = (
        "Task 2 -> Task 3 Contract\n"
        "NSE = 0.657 (Good)\n"
        "PBIAS = -9.9%\n"
        "Recall = 0.628\n"
        "F1 = 0.645\n"
        "Status: READY"
    )
    ax.text(16.0, 5.0, metrics_text, color=green, fontsize=9, ha="center", va="center",
            family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor=panel_bg, edgecolor=green, alpha=0.8))

    plt.tight_layout(rect=[0, 0, 1, 0.93])
    out_path = REPORTS_DIR / "task3_architecture.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=dark_bg)
    plt.close()
    log.info("Architecture diagram saved -> %s", out_path)
    return str(out_path)


def run_manning_predictions(task2: dict, lookup: dict) -> dict:
    manning_metrics = {}
    if "y_pred" not in task2:
        return manning_metrics

    y_pred = task2["y_pred"]
    y_obs  = task2["y_obs"]
    dates  = task2["dates"]

    q_values = np.array([e["discharge_cms"] for e in lookup["entries"]])
    d_values = np.array([e["depth_m"] for e in lookup["entries"]])
    v_values = np.array([e["velocity_ms"] for e in lookup["entries"]])
    e_values = np.array([e["extent_m"] for e in lookup["entries"]])

    pred_depth    = np.interp(y_pred, q_values, d_values)
    pred_velocity = np.interp(y_pred, q_values, v_values)
    pred_extent   = np.interp(y_pred, q_values, e_values)
    obs_depth     = np.interp(y_obs, q_values, d_values)

    log.info("Predicted depth range:    [%.3f, %.3f] m", pred_depth.min(), pred_depth.max())
    log.info("Predicted velocity range: [%.3f, %.3f] m/s", pred_velocity.min(), pred_velocity.max())
    log.info("Predicted extent range:   [%.1f, %.1f] m", pred_extent.min(), pred_extent.max())

    depth_rmse = float(np.sqrt(np.mean((obs_depth - pred_depth)**2)))
    depth_bias = float(np.mean(pred_depth - obs_depth))
    log.info("Depth RMSE: %.3f m  Bias: %+.3f m", depth_rmse, depth_bias)

    flood_depth_threshold = 0.5
    obs_flooded  = (obs_depth >= flood_depth_threshold).astype(int)
    pred_flooded = (pred_depth >= flood_depth_threshold).astype(int)

    flood_f1 = flood_recall = flood_prec = 0.0
    if obs_flooded.sum() > 0:
        from sklearn.metrics import f1_score, recall_score, precision_score
        flood_f1     = f1_score(obs_flooded, pred_flooded, zero_division=0)
        flood_recall = recall_score(obs_flooded, pred_flooded, zero_division=0)
        flood_prec   = precision_score(obs_flooded, pred_flooded, zero_division=0)
        log.info("Inundation detection (depth>=%.1fm): F1=%.3f  Recall=%.3f  Precision=%.3f",
                 flood_depth_threshold, flood_f1, flood_recall, flood_prec)

    np.savez_compressed(
        OUTPUTS_DIR / "hydraulic_predictions.npz",
        dates=np.array(dates.values, dtype="datetime64[ns]"),
        discharge_pred_cms=y_pred,
        discharge_obs_cms=y_obs,
        depth_pred_m=pred_depth,
        depth_obs_m=obs_depth,
        velocity_pred_ms=pred_velocity,
        extent_pred_m=pred_extent,
    )
    log.info("Hydraulic predictions saved -> outputs/task3/hydraulic_predictions.npz")

    manning_metrics = {
        "depth_rmse_m": depth_rmse,
        "depth_bias_m": depth_bias,
        "inundation_f1": float(flood_f1),
        "inundation_recall": float(flood_recall),
        "inundation_precision": float(flood_prec),
    }
    return manning_metrics


def run_resunet_pipeline(task2: dict, device: str = "cpu") -> dict:
    from hydraulics.terrain import generate_synthetic_dem, save_terrain
    from hydraulics.dataset import create_datasets
    from hydraulics.trainer import train_resunet
    from hydraulics.evaluate import evaluate_model, save_evaluation, generate_spatial_predictions
    from hydraulics.resunet import ResUNet

    log.info("=" * 70)
    log.info("Step A: Generate synthetic terrain")
    log.info("=" * 70)

    terrain = generate_synthetic_dem(grid_size=256, resolution_m=10.0, seed=42)
    save_terrain(terrain, TERRAIN_DIR / "synthetic_dem_256.npz")

    log.info("=" * 70)
    log.info("Step B: Create training datasets")
    log.info("=" * 70)

    train_ds, val_ds, discharges = create_datasets(
        terrain, n_scenarios=80, val_fraction=0.2, seed=42
    )

    train_loader = DataLoader(train_ds, batch_size=16, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=16, shuffle=False, num_workers=0)

    log.info("=" * 70)
    log.info("Step C: Train ResUNet")
    log.info("=" * 70)

    result = train_resunet(
        train_loader=train_loader,
        val_loader=val_loader,
        device=device,
        epochs=200,
        lr=1e-3,
        weight_decay=1e-4,
        patience=30,
        save_dir=MODELS_DIR,
    )

    model = result["model"]
    history = result["history"]

    log.info("=" * 70)
    log.info("Step D: Evaluate ResUNet")
    log.info("=" * 70)

    metrics = evaluate_model(model, val_loader, device=device)
    save_evaluation(metrics, OUTPUTS_DIR / "resunet_evaluation.json")

    log.info("=" * 70)
    log.info("Step E: Generate spatial predictions for Task 2 discharges")
    log.info("=" * 70)

    if "y_pred" in task2:
        task2_discharges = task2["y_pred"]
        unique_q = np.unique(np.round(task2_discharges, 1))
        sample_q = unique_q[np.linspace(0, len(unique_q) - 1, min(20, len(unique_q)), dtype=int)]
        log.info("Generating spatial maps for %d sample discharges", len(sample_q))

        spatial = generate_spatial_predictions(model, terrain, sample_q, device=device)

        np.savez_compressed(
            OUTPUTS_DIR / "spatial_predictions.npz",
            discharges_cms=spatial["discharges_cms"],
            depth_maps=spatial["depth_maps"],
            grid_size=spatial["grid_size"],
            resolution_m=spatial["resolution_m"],
        )
        log.info("Spatial predictions saved -> outputs/task3/spatial_predictions.npz")
        log.info("  %d depth maps, each %dx%d",
                 len(spatial["discharges_cms"]), spatial["grid_size"], spatial["grid_size"])

    return {
        "metrics": metrics,
        "history": history,
        "model_params": model.count_parameters(),
    }


def main() -> None:
    log.info("=" * 70)
    log.info("Task 3: Hydraulic Surrogate Model (v2 — Full Pipeline)")
    log.info("=" * 70)

    task2 = load_task2_outputs()
    cfg = task2["config"]

    ready = cfg.get("model_quality", {}).get("ready_for_task3", False)
    if not ready:
        log.warning("Task 2 model NOT marked as ready for Task 3")
        log.warning("Proceeding but flagging quality concern")

    log.info("=" * 70)
    log.info("Step 1: Manning's discharge-depth lookup table")
    log.info("=" * 70)

    lookup = build_discharge_depth_lookup(cfg)
    lookup_path = MODELS_DIR / "mannings_lookup.json"
    with open(lookup_path, "w") as f:
        json.dump(lookup, f, indent=2)
    log.info("Lookup saved -> %s (%d entries)", lookup_path, len(lookup["entries"]))

    log.info("=" * 70)
    log.info("Step 2: ResUNet architecture definition")
    log.info("=" * 70)

    arch = define_resunet_architecture()
    arch_path = MODELS_DIR / "resunet_config.json"
    with open(arch_path, "w") as f:
        json.dump(arch, f, indent=2)
    log.info("Architecture config saved -> %s", arch_path)

    log.info("=" * 70)
    log.info("Step 3: Training plan")
    log.info("=" * 70)

    plan = build_training_plan(cfg, lookup)
    plan_path = MODELS_DIR / "training_plan.json"
    with open(plan_path, "w") as f:
        json.dump(plan, f, indent=2)
    log.info("Training plan saved -> %s", plan_path)

    log.info("=" * 70)
    log.info("Step 4: Architecture diagram")
    log.info("=" * 70)

    diagram_path = generate_architecture_diagram()

    log.info("=" * 70)
    log.info("Step 5: Manning's 1-D predictions")
    log.info("=" * 70)

    manning_metrics = run_manning_predictions(task2, lookup)

    log.info("=" * 70)
    log.info("Step 6: ResUNet training + evaluation pipeline")
    log.info("=" * 70)

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    log.info("Using device: %s", device)

    resunet_result = run_resunet_pipeline(task2, device=device)
    resunet_metrics = resunet_result["metrics"]

    summary = {
        "task": "Task 3 — Hydraulic Surrogate Model",
        "status": "phase1_complete",
        "version": "2.0",
        "timestamp": datetime.now(tz=None).isoformat(),
        "task2_quality": {
            "nse": cfg.get("test_nse"),
            "pbias": cfg.get("test_pbias"),
            "recall": cfg.get("recall"),
            "f1": cfg.get("f1_score"),
            "moriasi_class": cfg.get("model_quality", {}).get("moriasi_class"),
            "ready_for_task3": cfg.get("model_quality", {}).get("ready_for_task3"),
        },
        "artifacts": {
            "mannings_lookup": str(lookup_path),
            "resunet_config": str(arch_path),
            "resunet_model": str(MODELS_DIR / "resunet_best.pt"),
            "training_plan": str(plan_path),
            "training_history": str(MODELS_DIR / "training_history.json"),
            "architecture_diagram": diagram_path,
            "hydraulic_predictions": str(OUTPUTS_DIR / "hydraulic_predictions.npz"),
            "spatial_predictions": str(OUTPUTS_DIR / "spatial_predictions.npz"),
            "resunet_evaluation": str(OUTPUTS_DIR / "resunet_evaluation.json"),
        },
        "manning_proxy_metrics": manning_metrics,
        "resunet_metrics": resunet_metrics,
        "model_info": {
            "parameters": resunet_result["model_params"],
            "best_epoch": resunet_result["history"]["best_epoch"],
            "best_val_loss": resunet_result["history"]["best_val_loss"],
            "training_time_s": resunet_result["history"]["training_time_s"],
        },
        "next_steps": [
            "Acquire USGS 3DEP 10m LiDAR DEM for real terrain",
            "Retrain ResUNet on real DEM (replace synthetic)",
            "Build HEC-RAS 2D model for Phase 2 training data",
            "Validate against historical flood extents (FEMA, Sentinel-1 SAR)",
        ],
    }

    summary_path = OUTPUTS_DIR / "hydraulic_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    log.info("Summary saved -> %s", summary_path)

    log.info("=" * 70)
    log.info("Task 3 v2 COMPLETE")
    log.info("  Status: %s", summary["status"])
    log.info("  Manning's proxy depth RMSE: %.3f m", manning_metrics.get("depth_rmse_m", 0))
    log.info("  ResUNet depth RMSE: %.3f m (target <0.30m: %s)",
             resunet_metrics["depth_rmse_m"], resunet_metrics["target_rmse_met"])
    log.info("  ResUNet CSI: %.3f (target >0.70: %s)",
             resunet_metrics["csi"], resunet_metrics["target_csi_met"])
    log.info("  ResUNet inundation F1: %.3f", resunet_metrics["inundation_f1"])
    log.info("  Model parameters: %s", f"{resunet_result['model_params']:,}")
    log.info("=" * 70)


if __name__ == "__main__":
    main()
