from __future__ import annotations
import json
import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

from hydraulics.resunet import ResUNet

log = logging.getLogger(__name__)


class FloodDepthLoss(nn.Module):
    def __init__(self, wet_threshold_m: float = 0.01, depth_scale: float = 3.0):
        super().__init__()
        self.wet_threshold_m = wet_threshold_m
        self.depth_scale = depth_scale

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        pred_n = pred / self.depth_scale
        target_n = target / self.depth_scale

        wet_mask = (target > self.wet_threshold_m).float()
        n_wet = wet_mask.sum().clamp(min=1.0)
        n_dry = (1.0 - wet_mask).sum().clamp(min=1.0)

        err2 = (pred_n - target_n).pow(2)
        wet_mse = (err2 * wet_mask).sum() / n_wet
        dry_mse = (err2 * (1.0 - wet_mask)).sum() / n_dry
        balanced_mse = wet_mse + dry_mse

        pred_prob = torch.sigmoid(pred * 20.0 - 0.2)
        smooth = 1.0
        intersection = (pred_prob * wet_mask).sum()
        dice = (2.0 * intersection + smooth) / (pred_prob.sum() + wet_mask.sum() + smooth)
        dice_loss = 1.0 - dice

        return balanced_mse + 5.0 * dice_loss


def train_resunet(
    train_loader: DataLoader,
    val_loader: DataLoader,
    device: str = "cpu",
    epochs: int = 200,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    patience: int = 30,
    save_dir: Optional[Path] = None,
) -> dict:
    model = ResUNet(in_channels=4, out_channels=1).to(device)
    criterion = FloodDepthLoss()
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs)

    log.info("ResUNet parameters: %s", f"{model.count_parameters():,}")
    log.info("Training on device: %s", device)
    log.info("Epochs: %d, LR: %g, Patience: %d", epochs, lr, patience)

    best_val_loss = float("inf")
    best_epoch = 0
    no_improve = 0
    history = {"train_loss": [], "val_loss": [], "lr": []}

    t0 = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        train_losses = []
        for x_batch, y_batch in train_loader:
            x_batch = x_batch.to(device)
            y_batch = y_batch.to(device)

            pred = model(x_batch)
            loss = criterion(pred, y_batch)

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            train_losses.append(loss.item())

        scheduler.step()

        model.eval()
        val_losses = []
        with torch.no_grad():
            for x_batch, y_batch in val_loader:
                x_batch = x_batch.to(device)
                y_batch = y_batch.to(device)
                pred = model(x_batch)
                loss = criterion(pred, y_batch)
                val_losses.append(loss.item())

        train_loss = np.mean(train_losses)
        val_loss = np.mean(val_losses)
        current_lr = scheduler.get_last_lr()[0]

        history["train_loss"].append(float(train_loss))
        history["val_loss"].append(float(val_loss))
        history["lr"].append(float(current_lr))

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            no_improve = 0
            if save_dir:
                save_dir.mkdir(parents=True, exist_ok=True)
                torch.save(model.state_dict(), save_dir / "resunet_best.pt")
        else:
            no_improve += 1

        if epoch % 20 == 0 or epoch == 1:
            elapsed = time.time() - t0
            log.info("Epoch %3d/%d | train=%.5f val=%.5f | best=%.5f @%d | %.1fs",
                     epoch, epochs, train_loss, val_loss, best_val_loss, best_epoch, elapsed)

        if no_improve >= patience:
            log.info("Early stopping at epoch %d (patience=%d)", epoch, patience)
            break

    elapsed = time.time() - t0
    log.info("Training complete in %.1fs. Best val loss: %.5f @ epoch %d",
             elapsed, best_val_loss, best_epoch)

    if save_dir and (save_dir / "resunet_best.pt").exists():
        model.load_state_dict(torch.load(save_dir / "resunet_best.pt", weights_only=True))
        log.info("Loaded best model from epoch %d", best_epoch)

    history["best_epoch"] = best_epoch
    history["best_val_loss"] = float(best_val_loss)
    history["total_epochs"] = len(history["train_loss"])
    history["training_time_s"] = elapsed

    if save_dir:
        with open(save_dir / "training_history.json", "w") as f:
            json.dump(history, f, indent=2)

    return {"model": model, "history": history}
