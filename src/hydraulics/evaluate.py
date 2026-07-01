from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import torch
from torch.utils.data import DataLoader
from sklearn.metrics import f1_score, recall_score, precision_score

from hydraulics.resunet import ResUNet

log = logging.getLogger(__name__)


def evaluate_model(
    model: ResUNet,
    val_loader: DataLoader,
    device: str = "cpu",
) -> dict:
    model.eval()
    all_pred = []
    all_true = []

    with torch.no_grad():
        for x_batch, y_batch in val_loader:
            x_batch = x_batch.to(device)
            pred = model(x_batch).cpu().numpy()
            true = y_batch.numpy()
            all_pred.append(pred)
            all_true.append(true)

    pred = np.concatenate(all_pred, axis=0)
    true = np.concatenate(all_true, axis=0)

    depth_rmse = float(np.sqrt(np.mean((pred - true) ** 2)))
    depth_bias = float(np.mean(pred - true))
    depth_mae = float(np.mean(np.abs(pred - true)))

    pred_vol = pred.sum()
    true_vol = true.sum()
    volume_error_pct = float((pred_vol - true_vol) / (true_vol + 1e-8) * 100)

    wet_threshold = 0.01
    pred_wet = (pred > wet_threshold).flatten().astype(int)
    true_wet = (true > wet_threshold).flatten().astype(int)

    if true_wet.sum() > 0:
        inundation_f1 = float(f1_score(true_wet, pred_wet, zero_division=0))
        inundation_recall = float(recall_score(true_wet, pred_wet, zero_division=0))
        inundation_precision = float(precision_score(true_wet, pred_wet, zero_division=0))

        tp = ((pred_wet == 1) & (true_wet == 1)).sum()
        fp = ((pred_wet == 1) & (true_wet == 0)).sum()
        fn = ((pred_wet == 0) & (true_wet == 1)).sum()
        csi = float(tp / (tp + fp + fn + 1e-8))
    else:
        inundation_f1 = 0.0
        inundation_recall = 0.0
        inundation_precision = 0.0
        csi = 0.0

    deep_mask = true > 1.0
    if deep_mask.sum() > 0:
        peak_rmse = float(np.sqrt(np.mean((pred[deep_mask] - true[deep_mask]) ** 2)))
        peak_bias = float(np.mean(pred[deep_mask] - true[deep_mask]))
    else:
        peak_rmse = 0.0
        peak_bias = 0.0

    metrics = {
        "depth_rmse_m": depth_rmse,
        "depth_bias_m": depth_bias,
        "depth_mae_m": depth_mae,
        "volume_error_pct": volume_error_pct,
        "inundation_f1": inundation_f1,
        "inundation_recall": inundation_recall,
        "inundation_precision": inundation_precision,
        "csi": csi,
        "peak_depth_rmse_m": peak_rmse,
        "peak_depth_bias_m": peak_bias,
        "n_samples": len(pred),
        "target_rmse_met": depth_rmse < 0.30,
        "target_csi_met": csi > 0.70,
    }

    log.info("ResUNet Evaluation:")
    log.info("  Depth RMSE: %.3f m (target < 0.30m: %s)", depth_rmse, depth_rmse < 0.30)
    log.info("  Depth Bias: %+.3f m", depth_bias)
    log.info("  CSI: %.3f (target > 0.70: %s)", csi, csi > 0.70)
    log.info("  Inundation F1: %.3f  Recall: %.3f  Precision: %.3f",
             inundation_f1, inundation_recall, inundation_precision)
    log.info("  Volume Error: %+.1f%%", volume_error_pct)
    log.info("  Peak Depth RMSE: %.3f m  Bias: %+.3f m", peak_rmse, peak_bias)

    return metrics


def save_evaluation(metrics: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(metrics, f, indent=2)
    log.info("Evaluation saved -> %s", output_path)


def generate_spatial_predictions(
    model: ResUNet,
    terrain: dict,
    discharges: np.ndarray,
    device: str = "cpu",
) -> dict:
    model.eval()
    gs = terrain["grid_size"]
    dem_norm = terrain["dem_norm"]
    slope = terrain["slope"]
    chan_dist_norm = terrain["channel_distance_norm"]

    dem_norm_n = (dem_norm - dem_norm.mean()) / (dem_norm.std() + 1e-8)
    slope_n = (slope - slope.mean()) / (slope.std() + 1e-8)
    chan_n = (chan_dist_norm - chan_dist_norm.mean()) / (chan_dist_norm.std() + 1e-8)

    q_log_max = np.log1p(discharges.max())

    all_depths = []
    all_q = []

    with torch.no_grad():
        for q in discharges:
            inp = np.zeros((1, 4, gs, gs), dtype=np.float32)
            inp[0, 0] = np.log1p(q) / q_log_max
            inp[0, 1] = dem_norm_n
            inp[0, 2] = slope_n
            inp[0, 3] = chan_n

            pred = model(torch.from_numpy(inp).to(device)).cpu().numpy()[0, 0]
            all_depths.append(pred)
            all_q.append(q)

    return {
        "discharges_cms": np.array(all_q, dtype=np.float32),
        "depth_maps": np.stack(all_depths).astype(np.float32),
        "grid_size": gs,
        "resolution_m": terrain["resolution_m"],
    }
