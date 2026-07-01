"""Probability-of-Inundation raster + scenario classification."""
from __future__ import annotations
from typing import List, Sequence, Tuple

import numpy as np

# Default percentile weighting for the 3-scenario ensemble.
# P10 / P50 / P90 are treated as 25% / 50% / 25% probability mass
# (a standard 3-point ensemble weighting; the trapezoidal Pearson-Tukey rule).
DEFAULT_ENSEMBLE_WEIGHTS = (0.25, 0.50, 0.25)


def probability_of_inundation(depth_maps: Sequence[np.ndarray],
                              weights: Sequence[float] | None = None,
                              threshold_m: float = 0.01) -> np.ndarray:
    """Compute Probability-of-Inundation raster across an ensemble.

    Each cell PoI = sum_k w_k * 1[depth_k >= threshold].
    """
    if weights is None:
        if len(depth_maps) == 3:
            weights = DEFAULT_ENSEMBLE_WEIGHTS
        else:
            weights = [1.0 / len(depth_maps)] * len(depth_maps)
    w = np.asarray(weights, dtype=np.float64)
    w = w / w.sum()
    poi = np.zeros_like(np.asarray(depth_maps[0]), dtype=np.float32)
    for wi, dm in zip(w, depth_maps):
        poi = poi + wi * (np.asarray(dm) >= threshold_m).astype(np.float32)
    return np.clip(poi, 0.0, 1.0)


def expected_depth(depth_maps: Sequence[np.ndarray],
                   weights: Sequence[float] | None = None) -> np.ndarray:
    """Weighted expected depth raster across the ensemble."""
    if weights is None:
        weights = (DEFAULT_ENSEMBLE_WEIGHTS
                   if len(depth_maps) == 3
                   else [1.0 / len(depth_maps)] * len(depth_maps))
    w = np.asarray(weights, dtype=np.float64)
    w = w / w.sum()
    out = np.zeros_like(np.asarray(depth_maps[0]), dtype=np.float32)
    for wi, dm in zip(w, depth_maps):
        out = out + wi * np.asarray(dm, dtype=np.float32)
    return out


# Severity classification thresholds (calibrated to Sonoita Creek)
# Based on peak Q + max depth + wet area extent.
_SEVERITY_BANDS: List[Tuple[str, float, float, str]] = [
    # (label, max_q_cms, max_depth_m, caption_template)
    ("None",     0.5,   0.05,
     "No meaningful flooding expected. Creek remains within its low-flow channel."),
    ("Minor",    5.0,   0.4,
     "Minor flooding possible: water may reach the creek banks and lap onto low-lying floodplain areas."),
    ("Moderate", 20.0,  1.0,
     "Moderate flooding likely: the creek will overtop its banks and inundate the immediate floodplain near Hwy 82."),
    ("Major",    80.0,  2.0,
     "Major flooding expected: wide floodplain inundation, road crossings unsafe, evacuate low-lying property near Patagonia."),
    ("Severe",   1e9,   1e9,
     "Severe / catastrophic flooding: extensive inundation across the entire floodplain corridor. Life-threatening conditions."),
]


def classify_scenario(q_cms: float, max_depth_m: float,
                      wet_area_km2: float) -> dict:
    """Return severity label + plain-English caption for a single scenario."""
    q = float(q_cms)
    d = float(max_depth_m)
    for label, q_thr, d_thr, caption in _SEVERITY_BANDS:
        if q <= q_thr and d <= d_thr:
            return {
                "severity": label,
                "caption": caption,
                "q_cms": q,
                "max_depth_m": d,
                "wet_area_km2": float(wet_area_km2),
            }
    label, _, _, caption = _SEVERITY_BANDS[-1]
    return {
        "severity": label,
        "caption": caption,
        "q_cms": q,
        "max_depth_m": d,
        "wet_area_km2": float(wet_area_km2),
    }
