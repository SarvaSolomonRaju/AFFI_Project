"""
losses.py — Hydrology losses & metrics, hardened for sparse/flashy regimes.

Key change from naive NSE: use a CONSTANT basin-scale denominator
(training-set target variance) instead of batch variance.
Reference: Kratzert et al. 2019, "NeuralHydrology" / EA-LSTM paper.
"""
from __future__ import annotations

import torch
import torch.nn as nn


class BasinNSELoss(nn.Module):
    """
    Basin-averaged NSE loss. Denominator is a precomputed constant
    (variance of training targets, scaled space). Stable on sparse data.

    Optional event-day upweighting: targets above `event_threshold` get
    `event_weight` × loss contribution. Default: 5× weight on event days.
    """

    def __init__(
        self,
        basin_target_std: float,
        eps: float = 0.1,
        event_threshold: float = 0.0,
        event_weight: float = 5.0,
    ) -> None:
        super().__init__()
        # Store as buffer so it moves with .to(device)
        self.register_buffer(
            "denom", torch.tensor((basin_target_std + eps) ** 2, dtype=torch.float32)
        )
        self.event_threshold = event_threshold
        self.event_weight = event_weight

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        sq_err = (pred - target) ** 2
        # Upweight rare event days
        weights = torch.where(
            target > self.event_threshold,
            torch.tensor(self.event_weight, device=target.device, dtype=target.dtype),
            torch.tensor(1.0, device=target.device, dtype=target.dtype),
        )
        return (weights * sq_err).mean() / self.denom


def nse(pred: torch.Tensor, target: torch.Tensor) -> float:
    num = torch.sum((pred - target) ** 2)
    den = torch.sum((target - target.mean()) ** 2)
    return float(1.0 - num / (den + 1e-12))


def kge(pred: torch.Tensor, target: torch.Tensor) -> float:
    p, t = pred.flatten(), target.flatten()
    r = torch.corrcoef(torch.stack([p, t]))[0, 1]
    alpha = p.std() / (t.std() + 1e-12)
    beta = p.mean() / (t.mean() + 1e-12)
    return float(1.0 - torch.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2))