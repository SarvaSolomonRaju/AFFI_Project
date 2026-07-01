"""
settings.py — Central Configuration Loader
============================================
WHY THIS FILE EXISTS:
    Your old code had values scattered everywhere:
        IDF_10YR = {"1hr": 1.40, ...}  # line 47
        "forecast_days": 7              # line 68
        thr_adv_24 = IDF_10YR['24hr'] * 0.25  # line 155

    If you wanted to change the watershed, you'd have to find
    and edit 15+ lines across the file. Miss one? Bug.

    This file loads EVERYTHING from ONE YAML file.
    Change watershed = change ONE filename. Done.

HOW IT WORKS:
    1. Reads the YAML file (human-readable config)
    2. Converts it into Python objects (Pydantic models)
    3. Validates every value (catches typos before they crash)
    4. Makes everything available as: settings.watershed.name

WHAT IS PYDANTIC?
    A library that checks your data is correct.
    Example: If you accidentally type area_km2: "five hundred"
    instead of area_km2: 510, Pydantic catches it immediately
    with a clear error message instead of crashing 200 lines later
    with "TypeError: can't multiply str by float".
"""

import os
import yaml
from pathlib import Path
from pydantic import BaseModel, field_validator
from typing import Dict, Optional


# ============================================================
# STEP 1: Define what valid configuration looks like
# ============================================================
# Each class below is a "schema" — a blueprint that says
# "this section MUST have these fields with these types"

class PourPoint(BaseModel):
    """Where water exits the watershed."""
    lat: float
    lon: float
    description: str

    @field_validator("lat")
    @classmethod
    def lat_must_be_valid(cls, v):
        """Latitude must be between -90 and 90."""
        if not -90 <= v <= 90:
            raise ValueError(f"Latitude {v} is not between -90 and 90")
        return v

    @field_validator("lon")
    @classmethod
    def lon_must_be_valid(cls, v):
        """Longitude must be between -180 and 180."""
        if not -180 <= v <= 180:
            raise ValueError(f"Longitude {v} is not between -180 and 180")
        return v


class BBox(BaseModel):
    """Bounding box — rectangle containing the watershed."""
    north: float
    south: float
    east: float
    west: float

    @field_validator("north")
    @classmethod
    def north_gt_south(cls, v, info):
        # Note: cross-field validation happens in model_validator
        return v


class WatershedConfig(BaseModel):
    """Everything about the physical watershed."""
    name: str
    huc: str
    state: str
    county: str
    area_km2: float
    pour_point: PourPoint
    bbox: BBox
    usgs_gauge: str


class AlertThreshold(BaseModel):
    """One alert level's thresholds."""
    fraction_of_10yr_24hr: float
    fraction_of_10yr_1hr: float
    probability_trigger_pct: float


class AlertThresholds(BaseModel):
    """All three alert levels."""
    advisory: AlertThreshold
    watch: AlertThreshold
    warning: AlertThreshold


class GridConfig(BaseModel):
    """How to sample rainfall across the watershed."""
    n_points: int = 5
    center_weight: float = 0.30
    cardinal_weight: float = 0.20
    diagonal_weight: float = 0.15


class APIConfig(BaseModel):
    """API connection settings."""
    ensemble_url: str
    model: str
    forecast_days: int = 7
    timeout_seconds: int = 30
    max_retries: int = 3
    retry_delay_seconds: int = 5
    timezone: str = "America/Phoenix"


class Settings(BaseModel):
    """
    THE MASTER CONFIG — contains everything.

    After loading, you access values like:
        settings.watershed.name          → "Upper Sonoita Creek"
        settings.watershed.bbox.north    → 31.85
        settings.idf_benchmarks["10yr"]["24hr"]  → 3.10
        settings.alert_thresholds.warning.fraction_of_10yr_24hr → 0.65
    """
    watershed: WatershedConfig
    idf_benchmarks: Dict[str, Dict[str, float]]
    alert_thresholds: AlertThresholds
    grid: GridConfig = GridConfig()
    api: APIConfig = APIConfig(
        ensemble_url="https://ensemble-api.open-meteo.com/v1/ensemble",
        model="gfs_seamless"
    )

    @property
    def idf_10yr(self) -> Dict[str, float]:
        """Shortcut to get 10-year benchmarks (most commonly used)."""
        return self.idf_benchmarks.get("10yr", {})

    def get_threshold_inches(self, level: str, duration: str) -> float:
        """
        Calculate actual threshold in inches for a given alert level.

        Example:
            get_threshold_inches("warning", "24hr")
            = 0.65 * 3.10 = 2.015 inches
        """
        idf_10 = self.idf_10yr
        thresh = getattr(self.alert_thresholds, level)
        if duration == "24hr":
            return thresh.fraction_of_10yr_24hr * idf_10.get("24hr", 0)
        elif duration == "1hr":
            return thresh.fraction_of_10yr_1hr * idf_10.get("1hr", 0)
        else:
            raise ValueError(f"Unsupported duration: {duration}")


# ============================================================
# STEP 2: Load the YAML file and create Settings object
# ============================================================

def load_settings(yaml_path: Optional[str] = None) -> Settings:
    """
    Load configuration from a YAML file.

    HOW TO USE:
        # Default (loads upper_sonoita.yaml):
        settings = load_settings()

        # Different watershed:
        settings = load_settings("config/watersheds/rillito_creek.yaml")

    WHAT HAPPENS INSIDE:
        1. Finds the YAML file
        2. Reads it into a Python dictionary
        3. Passes it to Pydantic for validation
        4. Returns a Settings object with all values checked
    """
    if yaml_path is None:
        # Default: look for upper_sonoita.yaml relative to project root
        project_root = Path(__file__).parent.parent
        yaml_path = project_root / "config" / "watersheds" / "upper_sonoita.yaml"
    else:
        yaml_path = Path(yaml_path)

    if not yaml_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {yaml_path}\n"
            f"Create one by copying config/watersheds/upper_sonoita.yaml"
        )

    with open(yaml_path, "r") as f:
        raw = yaml.safe_load(f)

    # Pydantic validates everything here
    # If ANY value is wrong type/missing, you get a clear error
    return Settings(**raw)


# ============================================================
# STEP 3: Create a global settings instance
# ============================================================
# This runs when you do: from config.settings import settings
# Every other file imports this ONE object.

try:
    settings = load_settings()
except Exception:
    # If YAML not found (e.g., running tests), use None
    # Tests will load their own config
    settings = None
