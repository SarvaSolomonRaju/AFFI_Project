from __future__ import annotations
import logging
from typing import Optional

import numpy as np
import torch
from torch.utils.data import Dataset

from hydraulics.terrain import (
    generate_synthetic_dem,
    compute_flood_depth,
    GRID_SIZE,
)

log = logging.getLogger(__name__)


def generate_scenarios(
    n_scenarios: int = 80,
    q_min: float = 1.0,
    q_max: float = 300.0,
    seed: int = 42,
) -> np.ndarray:
    n_low = n_scenarios // 4
    n_high = n_scenarios - n_low
    low = np.geomspace(q_min, 10.0, n_low)
    high = np.linspace(10.0, q_max, n_high + 1)[1:]
    return np.concatenate([low, high]).astype(np.float32)


def build_training_arrays(
    terrain: dict,
    discharges: np.ndarray,
    noise_std: float = 0.05,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = len(discharges)
    gs = terrain["grid_size"]

    dem_norm = terrain["dem_norm"]
    slope = terrain["slope"]
    chan_dist_norm = terrain["channel_distance_norm"]

    dem_norm_n = (dem_norm - dem_norm.mean()) / (dem_norm.std() + 1e-8)
    slope_n = (slope - slope.mean()) / (slope.std() + 1e-8)
    chan_n = (chan_dist_norm - chan_dist_norm.mean()) / (chan_dist_norm.std() + 1e-8)

    q_log_max = np.log1p(discharges.max())

    inputs = np.zeros((n, 4, gs, gs), dtype=np.float32)
    labels = np.zeros((n, 1, gs, gs), dtype=np.float32)

    for i, q in enumerate(discharges):
        q_noisy = q * (1.0 + rng.normal(0, noise_std))
        q_noisy = max(q_noisy, 0.01)

        inputs[i, 0] = np.log1p(q_noisy) / q_log_max
        inputs[i, 1] = dem_norm_n
        inputs[i, 2] = slope_n
        inputs[i, 3] = chan_n

        depth = compute_flood_depth(terrain, q_noisy)
        labels[i, 0] = depth

    log.info("Built %d training samples: inputs %s, labels %s",
             n, inputs.shape, labels.shape)
    log.info("  Discharge range: [%.2f, %.2f] cms", discharges.min(), discharges.max())
    log.info("  Max depth in labels: %.2f m", labels.max())

    return inputs, labels


class FloodDepthDataset(Dataset):
    def __init__(
        self,
        inputs: np.ndarray,
        labels: np.ndarray,
        augment: bool = False,
        seed: int = 42,
    ):
        self.inputs = torch.from_numpy(inputs)
        self.labels = torch.from_numpy(labels)
        self.augment = augment
        self.rng = np.random.default_rng(seed)

    def __len__(self) -> int:
        return len(self.inputs)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        x = self.inputs[idx]
        y = self.labels[idx]

        if self.augment:
            if self.rng.random() > 0.5:
                x = torch.flip(x, [-1])
                y = torch.flip(y, [-1])
            k = self.rng.integers(0, 4)
            if k > 0:
                x = torch.rot90(x, k, [-2, -1])
                y = torch.rot90(y, k, [-2, -1])

        return x, y


def create_datasets(
    terrain: dict,
    n_scenarios: int = 80,
    val_fraction: float = 0.2,
    seed: int = 42,
) -> tuple[FloodDepthDataset, FloodDepthDataset, np.ndarray]:
    discharges = generate_scenarios(n_scenarios, seed=seed)

    inputs, labels = build_training_arrays(terrain, discharges, seed=seed)

    n_val = max(1, int(n_scenarios * val_fraction))
    n_train = n_scenarios - n_val

    rng = np.random.default_rng(seed)
    idx = rng.permutation(n_scenarios)
    train_idx = idx[:n_train]
    val_idx = idx[n_train:]

    train_ds = FloodDepthDataset(inputs[train_idx], labels[train_idx], augment=True, seed=seed)
    val_ds = FloodDepthDataset(inputs[val_idx], labels[val_idx], augment=False)

    log.info("Datasets: %d train, %d val", len(train_ds), len(val_ds))

    return train_ds, val_ds, discharges
