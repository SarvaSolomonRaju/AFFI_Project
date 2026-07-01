"""
config.py — Typed configuration loader with Pydantic validation.

WHY PYDANTIC INSTEAD OF JUST yaml.safe_load()?
    yaml.safe_load() returns a dict. If you typo `hidden_sze: 128` the
    dict will happily contain that misspelled key, your model will use
    the default value of 64, you'll wonder why training is so slow, and
    you'll lose a day debugging.

    Pydantic validates every field's TYPE and PRESENCE at load time.
    Typo? → ValidationError at line 1 of your script. You fix it in
    30 seconds instead of 1 day. This is non-negotiable in production.

USAGE:
    from common.config import load_config
    cfg = load_config()
    cfg.model.hidden_size       # IDE autocomplete works!
    cfg.data.base_basin.usgs_id # type-checked!
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from common.paths import TASK2_CONFIG


# ============================================================================
# Schemas — one class per YAML section.
# `model_config = ConfigDict(extra='forbid')` rejects unknown keys → typos die early.
# ============================================================================
class BasinConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    usgs_id: str = Field(min_length=3, max_length=15)
    huc: str | None = None
    area_km2: float = Field(gt=0)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class DataConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    base_basin: BasinConfig
    finetune_basin: BasinConfig
    start_date: str
    end_date: str
    train_end: str | None = None
    val_end: str | None = None


class FeaturesConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    dynamic: list[str] = Field(default_factory=list)
    static: list[str] = Field(default_factory=list)
    target: str | None = None
    lookback_days: int | None = None
    forecast_horizon: int | None = None


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    hidden_size: int = Field(gt=0)
    num_layers: int = Field(gt=0, le=8)
    dropout: float = Field(ge=0.0, lt=1.0)
    bidirectional: bool = False


class SchedulerConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: Literal["reduce_on_plateau", "cosine", "none"] = "none"
    factor: float = Field(default=0.5, gt=0, lt=1)
    patience: int = Field(default=10, ge=0)


class TrainingConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    batch_size: int | None = None
    num_epochs: int | None = None
    learning_rate: float | None = None
    weight_decay: float = Field(default=0.0, ge=0)
    loss: Literal["nse", "mse", "kge"] = "mse"
    gradient_clip: float = Field(default=1.0, gt=0)
    early_stop_patience: int = Field(default=10, ge=0)
    early_stop_min_delta: float = Field(default=0.0, ge=0)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    num_workers: int = Field(default=0, ge=0)
    pin_memory: bool = False


class LoggingConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    to_file: bool = False
    log_dir: str = "outputs/logs"


class CheckpointConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    save_dir: str = "models"
    save_best_only: bool = True
    save_last: bool = False


class EvaluationConfig(BaseModel):
    model_config = ConfigDict(extra="allow")
    figures_dir: str = "outputs/figures"
    metrics: list[str] = Field(default_factory=list)


class Task2Config(BaseModel):
    """Root config — mirrors the structure of config/task2.yaml."""
    model_config = ConfigDict(extra="allow")

    seed: int
    device: Literal["auto", "cpu", "cuda", "mps"]
    data: DataConfig
    model: ModelConfig
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    checkpoints: CheckpointConfig = Field(default_factory=CheckpointConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)


# ============================================================================
# Loader
# ============================================================================
def load_config(path: Path = TASK2_CONFIG) -> Task2Config:
    """
    Load + validate config/task2.yaml.

    Raises pydantic.ValidationError if any field is missing, mistyped,
    or has an unknown key. This means: misconfigured → fail fast at line 1.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")

    with path.open("r") as f:
        raw = yaml.safe_load(f)

    return Task2Config(**raw)


if __name__ == "__main__":
    cfg = load_config()
    print(f"✓ Config loaded successfully")
    print(f"  base basin:    {cfg.data.base_basin.name} ({cfg.data.base_basin.usgs_id})")
    print(f"  date range:    {cfg.data.start_date} → {cfg.data.end_date}")
    print(f"  LSTM:          hidden={cfg.model.hidden_size}, layers={cfg.model.num_layers}")
    print(f"  device:        {cfg.device}")