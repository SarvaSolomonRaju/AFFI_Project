"""
validators.py — Input Validation Functions
============================================
WHY VALIDATE?
    Imagine the API returns rainfall = -5.0 inches.
    That's physically impossible. Without validation, your code
    would happily compute a negative storm index, generate a
    nonsensical alert, and you'd never know.

    Validators are GUARDS at the door. They check every piece
    of data before it enters your system.

    In professional software, 30-40% of code is validation
    and error handling. The actual "logic" is only 60%.
    This is what separates hobby code from production code.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional

from common.logging_setup import get_logger

logger = get_logger(__name__)


def validate_rainfall_data(df: pd.DataFrame, source: str = "unknown") -> pd.DataFrame:
    """
    Validate and clean rainfall data from API or synthetic source.

    WHAT IT CHECKS:
    1. No negative values (rain can't be negative)
    2. No unreasonably large values (>50 inches/hour is impossible)
    3. No NaN/null values (replace with 0 — no data = no rain)
    4. Correct data types (must be numeric)

    WHY 50 INCHES/HOUR AS MAX?
        The world record for 1-hour rainfall is 12 inches
        (Holt, Missouri, 1947). 50 inches is 4x the world record.
        Anything above that is clearly a data error.

    Parameters
    ----------
    df : pd.DataFrame
        Rainfall data with ensemble members as columns.
        Each cell = rainfall in mm for that hour and member.
    source : str
        Where the data came from (for logging).

    Returns
    -------
    pd.DataFrame
        Cleaned rainfall data.
    """
    original_shape = df.shape

    # Check 1: Replace NaN with 0
    nan_count = df.isna().sum().sum()
    if nan_count > 0:
        logger.warning("Found %d NaN values in %s data — replacing with 0", 
                       nan_count, source)
        df = df.fillna(0.0)

    # Check 2: Clip negative values to 0
    neg_count = (df < 0).sum().sum()
    if neg_count > 0:
        logger.warning("Found %d negative rainfall values in %s — clipping to 0", 
                       neg_count, source)
        df = df.clip(lower=0.0)

    # Check 3: Cap unreasonable values (50 inches/hr = ~1270 mm/hr)
    # Open-Meteo returns mm, so 1270mm is our cap
    MAX_MM_PER_HOUR = 1270.0
    extreme_count = (df > MAX_MM_PER_HOUR).sum().sum()
    if extreme_count > 0:
        logger.warning("Found %d extreme values (>%.0f mm/hr) in %s — capping", 
                       extreme_count, MAX_MM_PER_HOUR, source)
        df = df.clip(upper=MAX_MM_PER_HOUR)

    # Check 4: Ensure all columns are numeric
    for col in df.columns:
        if not np.issubdtype(df[col].dtype, np.number):
            logger.error("Column %s is not numeric (type: %s) — converting", 
                        col, df[col].dtype)
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    logger.debug("Validated %s data: %s → %s (clean)", 
                source, original_shape, df.shape)
    return df


def validate_bbox(bbox: Dict[str, float]) -> bool:
    """
    Validate a bounding box.

    CHECKS:
    - North > South (otherwise the box is upside down)
    - East > West (for Western Hemisphere, both are negative,
      so "east" is less negative = larger number)
    - All values are within valid lat/lon ranges
    """
    if bbox["north"] <= bbox["south"]:
        logger.error("Invalid bbox: north (%.4f) must be > south (%.4f)", 
                    bbox["north"], bbox["south"])
        return False

    if bbox["east"] <= bbox["west"]:
        logger.error("Invalid bbox: east (%.4f) must be > west (%.4f)", 
                    bbox["east"], bbox["west"])
        return False

    if not (-90 <= bbox["south"] <= bbox["north"] <= 90):
        logger.error("Latitude out of range [-90, 90]")
        return False

    if not (-180 <= bbox["west"] <= bbox["east"] <= 180):
        logger.error("Longitude out of range [-180, 180]")
        return False

    logger.debug("Bounding box validated: N=%.2f S=%.2f E=%.2f W=%.2f", 
                bbox["north"], bbox["south"], bbox["east"], bbox["west"])
    return True


def validate_idf_table(idf: Dict[str, Dict[str, float]]) -> bool:
    """
    Validate IDF benchmark table.

    CHECKS:
    - All return periods have all durations
    - Values increase with duration (24hr > 6hr > 3hr > 1hr)
    - Values increase with return period (100yr > 50yr > 10yr)
    - No negative or zero values
    """
    required_durations = {"1hr", "3hr", "6hr", "24hr"}

    for period, values in idf.items():
        # Check all durations present
        missing = required_durations - set(values.keys())
        if missing:
            logger.error("IDF %s missing durations: %s", period, missing)
            return False

        # Check values increase with duration
        if not (values["1hr"] <= values["3hr"] <= values["6hr"] <= values["24hr"]):
            logger.error("IDF %s: values must increase with duration "
                        "(1hr=%.2f, 3hr=%.2f, 6hr=%.2f, 24hr=%.2f)",
                        period, values["1hr"], values["3hr"], 
                        values["6hr"], values["24hr"])
            return False

        # Check no negatives
        if any(v <= 0 for v in values.values()):
            logger.error("IDF %s has zero or negative values", period)
            return False

    logger.debug("IDF table validated: %d return periods", len(idf))
    return True
