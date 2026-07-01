"""
contracts/schemas.py
====================
The DATA CONTRACT between Task 1 (rainfall forecast) and Task 2 (LSTM discharge).

Why this file exists:
    Task 1 produces a JSON alert packet. Task 2 needs hourly rainfall to feed
    the LSTM. Without a CONTRACT, every change to Task 1 breaks Task 2.
    
    This file defines the EXACT shape of data flowing between stages.
    Pydantic validates it automatically — bad data is caught at the boundary,
    not deep inside the LSTM where errors are impossible to debug.

Author: Solman Raju Sarva
Project: AFFI (Arizona Flash Flood Inundation AI)
"""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS — Fixed vocabularies. Cannot accept invalid strings.
# ─────────────────────────────────────────────────────────────────────────────

class AlertLevel(str, Enum):
    """The 4 alert states defined in the AFFI white paper Section 4.7."""
    GREEN = "GREEN"
    ADVISORY = "ADVISORY"
    WATCH = "WATCH"
    WARNING = "WARNING"


class ReturnPeriod(str, Enum):
    """NOAA Atlas 14 return period brackets used for Storm Severity Index."""
    BELOW_2YR = "<2yr"
    BRACKET_2_5 = "2-5yr"
    BRACKET_5_10 = "5-10yr"
    BRACKET_10_25 = "10-25yr"
    BRACKET_25_50 = "25-50yr"
    BRACKET_50_100 = "50-100yr"
    ABOVE_100YR = ">100yr"


# ─────────────────────────────────────────────────────────────────────────────
# CORE GEOSPATIAL CONTRACT
# ─────────────────────────────────────────────────────────────────────────────

class WatershedAOI(BaseModel):
    """
    Watershed Area of Interest — the spatial domain for ALL calculations.
    Used by Task 1 (precipitation grid), Task 2 (LSTM static attributes),
    Task 3 (terrain DEM), Tasks 4-6 (output maps).
    """
    model_config = ConfigDict(frozen=True)  # Immutable — AOI never changes mid-pipeline.

    watershed_id: str = Field(..., description="Stable ID, e.g., 'upper_sonoita_creek'")
    huc_code: str = Field(..., min_length=8, max_length=12, description="USGS HUC code")
    name: str = Field(..., description="Human-readable name")
    
    # Bounding box — strict validation prevents bad coordinates.
    north: float = Field(..., ge=-90, le=90)
    south: float = Field(..., ge=-90, le=90)
    east: float = Field(..., ge=-180, le=180)
    west: float = Field(..., ge=-180, le=180)
    
    area_km2: float = Field(..., gt=0, description="Drainage area, square kilometers")

    @field_validator("north")
    @classmethod
    def north_must_exceed_south(cls, v: float, info) -> float:
        if "south" in info.data and v <= info.data["south"]:
            raise ValueError(f"north ({v}) must be > south ({info.data['south']})")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 OUTPUT CONTRACT — What Task 1 PRODUCES
# ─────────────────────────────────────────────────────────────────────────────

class EnsembleStatistics(BaseModel):
    """Statistics across 31 GFS ensemble members for ONE accumulation duration."""
    duration_hours: int = Field(..., ge=1, le=168, description="1, 3, 6, 12, 24, 48, 72, 168")
    mean_mm: float = Field(..., ge=0)
    p10_mm: float = Field(..., ge=0, description="10th percentile — driest scenario")
    p50_mm: float = Field(..., ge=0, description="Median scenario")
    p90_mm: float = Field(..., ge=0, description="90th percentile — wettest scenario")
    return_period: ReturnPeriod
    storm_severity_index: float = Field(..., ge=0, description="MAP / MAP_10yr")


class HourlyForecast(BaseModel):
    """One hour of ensemble rainfall forecast — the ATOMIC unit Task 2 consumes."""
    timestamp_utc: datetime
    lead_hours: int = Field(..., ge=0, le=168)
    p10_mm_hr: float = Field(..., ge=0)
    p50_mm_hr: float = Field(..., ge=0)
    p90_mm_hr: float = Field(..., ge=0)


class Task1AlertPacket(BaseModel):
    """
    The COMPLETE output of Task 1 — what gets written to task1_alert_packet.json.
    This is the EXACT object Task 2's adapter consumes as input.
    """
    # Provenance — every packet must be traceable
    schema_version: str = Field(default="1.0.0")
    generated_at_utc: datetime
    forecast_init_utc: datetime
    
    # Spatial context
    aoi: WatershedAOI
    
    # The forecast itself
    hourly_forecast: List[HourlyForecast] = Field(..., min_length=1)
    ensemble_stats: List[EnsembleStatistics] = Field(..., min_length=1)
    
    # Decision outputs
    current_alert: AlertLevel
    peak_lead_hours: Optional[int] = Field(None, description="Hours to peak rainfall")
    
    # Audit trail
    data_source: str = Field(default="Open-Meteo GFS Ensemble")
    notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 INPUT CONTRACT — What Task 2 LSTM CONSUMES
# ─────────────────────────────────────────────────────────────────────────────

class StaticAttributes(BaseModel):
    """
    The 6 watershed attributes from USGS GAGES-II.
    These are the LSTM's "physical fingerprint" of each watershed.
    """
    drainage_area_km2: float = Field(..., gt=0)
    mean_slope_pct: float = Field(..., ge=0, le=100)
    soil_permeability_cm_hr: float = Field(..., ge=0)
    ndvi: float = Field(..., ge=-1, le=1, description="Vegetation index")
    mean_elevation_m: float
    aridity_index: float = Field(..., gt=0, description="PET / Precip ratio")


class Task2InferenceInput(BaseModel):
    """
    EXACTLY what the LSTM expects at inference time.
    Built by contracts/adapters.py from a Task1AlertPacket.
    """
    watershed_id: str
    
    # Hourly time series — at least 30 days (LSTM lookback) plus forecast
    timestamps_utc: List[datetime]
    rainfall_mm_hr: List[float] = Field(..., description="Hourly MAP, length = timestamps")
    temperature_c: List[float]
    
    # Static features (broadcast to every timestep inside the model)
    static_attrs: StaticAttributes
    
    # Which percentile of the ensemble this represents
    ensemble_percentile: int = Field(..., ge=10, le=90, description="10, 50, or 90")

    @field_validator("rainfall_mm_hr")
    @classmethod
    def lengths_must_match(cls, v: List[float], info) -> List[float]:
        if "timestamps_utc" in info.data and len(v) != len(info.data["timestamps_utc"]):
            raise ValueError("rainfall_mm_hr length must match timestamps_utc")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 OUTPUT CONTRACT — What Task 2 LSTM PRODUCES (feeds Task 3)
# ─────────────────────────────────────────────────────────────────────────────

class Task2DischargeForecast(BaseModel):
    """LSTM output — hourly discharge prediction. Consumed by Task 3 U-Net."""
    watershed_id: str
    generated_at_utc: datetime
    
    timestamps_utc: List[datetime]
    discharge_p10_cms: List[float]
    discharge_p50_cms: List[float]
    discharge_p90_cms: List[float]
    
    peak_p50_cms: float = Field(..., ge=0)
    peak_p90_cms: float = Field(..., ge=0)
    time_to_peak_hours: int = Field(..., ge=0)
    
    # Provenance
    model_version: str = Field(..., description="e.g., 'lstm_base_walnutgulch_v1.0'")
    used_finetuned: bool = Field(default=False, description="True if Task 2b model was used")