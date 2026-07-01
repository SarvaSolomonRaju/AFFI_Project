"""
trainer.py — Two-stage hurdle model training.

Key fixes vs previous version:
  1. Classifier uses model.forward() — not raw lstm+head (was bypassing sigmoid)
  2. Focal loss replaces BCE+label_smoothing — purpose-built for 3% event rate
  3. Regressor uses all training days with NaN mask (not pre-filtered)
  4. Threshold found from val PR curve (unchanged — was correct)
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from pathlib import Path

from common.logging_setup import get_logger
from hydrology.model import LSTMClassifier, LSTMRegressor

log = get_logger(__name__)


# ── Focal Loss ────────────────────────────────────────────────────────────────
class FocalLoss(nn.Module):
    """
    Focal Loss (Lin et al. 2017) — down-weights easy negatives.
    gamma=2 is the standard for highly imbalanced classification.
    alpha=0.75 gives extra weight to the rare positive class.

    Why not BCE? BCE treats every sample equally.
    With 97% zeros, the model learns "always predict 0" and gets 97% accuracy.
    Focal loss forces the model to focus on the hard, rare events.
    """
    def __init__(self, alpha: float = 0.75, gamma: float = 2.0) -> None:
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, probs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        # probs are already sigmoid outputs from model.forward()
        probs   = probs.clamp(1e-6, 1 - 1e-6)
        bce     = -(targets * torch.log(probs) + (1 - targets) * torch.log(1 - probs))
        pt      = torch.where(targets == 1, probs, 1 - probs)
        alpha_t = torch.where(targets == 1,
                              torch.full_like(pt, self.alpha),
                              torch.full_like(pt, 1 - self.alpha))
        return (alpha_t * (1 - pt) ** self.gamma * bce).mean()


# ── Weighted sampler ──────────────────────────────────────────────────────────
def _make_weighted_sampler(y_cls: np.ndarray) -> WeightedRandomSampler:
    """Oversample event days so each batch is ~50% events."""
    n_event = int(y_cls.sum())
    n_zero  = len(y_cls) - n_event
    w_event = 1.0 / max(n_event, 1)
    w_zero  = 1.0 / max(n_zero,  1)
    weights = np.where(y_cls == 1, w_event, w_zero)
    return WeightedRandomSampler(
        weights=torch.tensor(weights, dtype=torch.float32),
        num_samples=len(weights),
        replacement=True,
    )


# ── Threshold search ──────────────────────────────────────────────────────────
def _find_best_threshold(model: LSTMClassifier,
                         X_val: np.ndarray,
                         y_val: np.ndarray,
                         device: torch.device) -> float:
    """
    Sweep thresholds on val set; pick threshold that maximizes
    COMBINED NSE (not F1). Why: F1 rewards recall, but every false
    positive destroys NSE on zero-flow days. We need precision.
    """
    from sklearn.metrics import f1_score, precision_score
    model.eval()
    with torch.no_grad():
        probs = model(torch.tensor(X_val, dtype=torch.float32).to(device)).cpu().numpy()

    # For threshold search, assume regressor predicts mean event magnitude
    obs_proxy = np.where(y_val == 1, 0.25, 0.0)  # approximate
    mean_obs = obs_proxy.mean()

    best_t, best_nse = 0.5, -999.0
    for t in np.arange(0.10, 0.95, 0.01):
        pred = np.where(probs >= t, 0.25, 0.0)
        ss_res = np.sum((obs_proxy - pred) ** 2)
        ss_tot = np.sum((obs_proxy - mean_obs) ** 2)
        nse_val = 1 - ss_res / ss_tot if ss_tot > 0 else -999
        if nse_val > best_nse:
            best_nse, best_t = nse_val, t

    f1 = f1_score(y_val, (probs >= best_t).astype(int), zero_division=0)
    prec = precision_score(y_val, (probs >= best_t).astype(int), zero_division=0)
    log.info("[Classifier] Best val threshold=%.2f  val_F1=%.3f  val_Prec=%.3f  val_NSE_proxy=%.3f",
             best_t, f1, prec, best_nse)
    return float(best_t)


# ── Stage 1: Classifier ───────────────────────────────────────────────────────
def train_classifier(
    X_train: np.ndarray,
    y_cls_train: np.ndarray,
    X_val: np.ndarray,
    y_cls_val: np.ndarray,
    cfg: dict,
    models_dir: Path,
    device: torch.device,
) -> tuple[LSTMClassifier, float]:
    """Train binary classifier. Returns (model, best_threshold)."""
    input_size = X_train.shape[2]
    model = LSTMClassifier(
        input_size=input_size,
        hidden_size=cfg["hidden_size"],
        num_layers=cfg["num_layers"],
        dropout=cfg["dropout"],
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = FocalLoss(alpha=0.75, gamma=2.0)

    sampler  = _make_weighted_sampler(y_cls_train)
    ds_train = TensorDataset(
        torch.tensor(X_train, dtype=torch.float32),
        torch.tensor(y_cls_train, dtype=torch.float32),
    )
    dl_train = DataLoader(ds_train, batch_size=cfg["batch_size"], sampler=sampler)

    best_val_loss, patience_counter = float("inf"), 0

    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        train_losses = []
        for xb, yb in dl_train:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            probs = model(xb)          # uses model.forward() → sigmoid output
            loss  = criterion(probs, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_losses.append(loss.item())

        model.eval()
        with torch.no_grad():
            val_probs = model(torch.tensor(X_val, dtype=torch.float32).to(device))
            val_loss  = criterion(
                val_probs,
                torch.tensor(y_cls_val, dtype=torch.float32).to(device)
            ).item()

        scheduler.step(val_loss)

        if epoch % 10 == 0:
            log.info("[Classifier] Epoch %3d | train=%.4f | val=%.4f",
                     epoch, np.mean(train_losses), val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(model.state_dict(), models_dir / "classifier_best.pt")
        else:
            patience_counter += 1
            if patience_counter >= cfg["early_stop_patience"]:
                log.info("[Classifier] Early stop at epoch %d", epoch)
                break

    model.load_state_dict(torch.load(models_dir / "classifier_best.pt", map_location=device))
    log.info("[Classifier] Best val_loss=%.4f", best_val_loss)
    best_threshold = _find_best_threshold(model, X_val, y_cls_val, device)
    return model, best_threshold


# ── Stage 2: Regressor ────────────────────────────────────────────────────────
def train_regressor(
    X_train: np.ndarray,
    y_reg_train: np.ndarray,
    X_val: np.ndarray,
    y_reg_val: np.ndarray,
    cfg: dict,
    models_dir: Path,
    device: torch.device,
) -> LSTMRegressor:
    """Train magnitude regressor on event days only (NaN = zero-flow day)."""
    train_mask = ~np.isnan(y_reg_train)
    val_mask   = ~np.isnan(y_reg_val)
    X_tr_ev, y_tr_ev = X_train[train_mask], y_reg_train[train_mask]
    X_va_ev, y_va_ev = X_val[val_mask],     y_reg_val[val_mask]

    log.info("[Regressor] Event days — train=%d  val=%d", len(X_tr_ev), len(X_va_ev))

    input_size = X_train.shape[2]
    model = LSTMRegressor(
        input_size=input_size,
        hidden_size=cfg["hidden_size"],
        num_layers=cfg["num_layers"],
        dropout=cfg["dropout"],
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=5, factor=0.5)
    criterion = nn.HuberLoss(delta=1.0)   # robust to 5.47mm outlier

    ds_train = TensorDataset(
        torch.tensor(X_tr_ev, dtype=torch.float32),
        torch.tensor(y_tr_ev, dtype=torch.float32),
    )
    dl_train = DataLoader(ds_train,
                          batch_size=min(cfg["batch_size"], len(X_tr_ev)),
                          shuffle=True)

    best_val_loss, patience_counter = float("inf"), 0

    for epoch in range(1, cfg["epochs"] + 1):
        model.train()
        train_losses = []
        for xb, yb in dl_train:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            loss = criterion(model(xb), yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            train_losses.append(loss.item())

        model.eval()
        with torch.no_grad():
            val_loss = criterion(
                model(torch.tensor(X_va_ev, dtype=torch.float32).to(device)),
                torch.tensor(y_va_ev, dtype=torch.float32).to(device)
            ).item()

        scheduler.step(val_loss)

        if epoch % 10 == 0:
            log.info("[Regressor] Epoch %3d | train=%.4f | val=%.4f",
                     epoch, np.mean(train_losses), val_loss)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            patience_counter = 0
            torch.save(model.state_dict(), models_dir / "regressor_best.pt")
        else:
            patience_counter += 1
            if patience_counter >= cfg["early_stop_patience"]:
                log.info("[Regressor] Early stop at epoch %d", epoch)
                break

    model.load_state_dict(torch.load(models_dir / "regressor_best.pt", map_location=device))
    log.info("[Regressor] Best val_loss=%.4f", best_val_loss)
    return model


def train_regressor_gbm(
    X_train: np.ndarray,
    y_reg_train: np.ndarray,
    X_val: np.ndarray,
    y_reg_val: np.ndarray,
    models_dir: Path,
):
    """
    Stage 2 with sklearn GradientBoostingRegressor.
    Why: 492 events is too few for a 200k-param LSTM.
    Flatten (N, 30, 8) → (N, 240). GBM handles small N natively.
    """
    from sklearn.ensemble import GradientBoostingRegressor
    import joblib

    mask_tr = ~np.isnan(y_reg_train)
    mask_va = ~np.isnan(y_reg_val)

    X_tr = X_train[mask_tr].reshape(mask_tr.sum(), -1)
    y_tr = y_reg_train[mask_tr]
    X_va = X_val[mask_va].reshape(mask_va.sum(), -1)
    y_va = y_reg_val[mask_va]

    log.info("[Regressor-GBM] train=%d  val=%d", len(X_tr), len(X_va))

    model = GradientBoostingRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        loss="huber",
        validation_fraction=0.2,
        n_iter_no_change=20,
        random_state=42,
    )
    model.fit(X_tr, y_tr)

    val_score = model.score(X_va, y_va)
    log.info("[Regressor-GBM] val R²=%.4f  n_estimators_used=%d", val_score, model.n_estimators_)

    joblib.dump(model, models_dir / "regressor_gbm.joblib")
    return model
