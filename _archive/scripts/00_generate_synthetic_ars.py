"""
00_generate_synthetic_ars.py — Generate synthetic ARS data for Walnut Gulch.

Produces 4 CSV files in data/raw/ars/ with realistic Walnut Gulch hydrology:
  - wg_precip_rg82_analog_pre2000.csv   (Year, Month, Day, Gage_1)
  - wg_precip_rg82_digital_2000_present.csv
  - wg1_runoff_analog_pre2000.csv       (Year, Month, Day, Flume_1)
  - wg1_runoff_digital_2000_present.csv

Climate: semi-arid SE Arizona, bimodal precip (winter + summer monsoon).
Period: 1990-01-01 through 2024-12-31, split at year 2000.

Run:  python scripts/00_generate_synthetic_ars.py
"""
from __future__ import annotations

import logging
import random
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s|%(name)s|%(message)s")
logger = logging.getLogger(__name__)

# Paths
ARS_DIR = Path("data/raw/ars")
ANALOG_PRE = 2000
SEED = 42

# Month-level precip probability (0=Jan … 11=Dec)
# Bimodal: winter peak (Dec-Feb) + monsoon peak (Jul-Sep)
MONTH_PRECIP_PROB = np.array([
    0.18, 0.16, 0.14, 0.09, 0.06, 0.08,  # Jan-Jun
    0.28, 0.38, 0.34, 0.16, 0.12, 0.14,   # Jul-Dec
])

# Monsoon months have heavier events (higher scale for exponential)
MONTH_PRECIP_SCALE = np.array([
    1.2, 1.0, 0.9, 0.5, 0.35, 0.5,
    2.8, 3.5, 2.6, 1.2, 0.8, 1.0,
])


def _generate_precip(rng: random.Random) -> pd.DataFrame:
    """Generate daily precip (sparse: only non-zero days written)."""
    start = pd.Timestamp("1990-01-01")
    end = pd.Timestamp("2024-12-31")
    dates = pd.date_range(start, end, freq="D")

    rows = []
    for dt in dates:
        month_idx = dt.month - 1
        if rng.random() < MONTH_PRECIP_PROB[month_idx]:
            # Exponential distribution for event depth, mean varies by month
            depth = round(rng.expovariate(1.0 / MONTH_PRECIP_SCALE[month_idx]), 2)
            # Cap at realistic max (150mm/day)
            depth = min(depth, 150.0)
            rows.append({"Year": dt.year, "Month": dt.month, "Day": dt.day, "Gage_1": depth})

    df = pd.DataFrame(rows)
    logger.info("Precip: %d event-days out of %d total days", len(df), len(dates))
    return df


def _generate_runoff(precip_df: pd.DataFrame, rng: random.Random) -> pd.DataFrame:
    """Generate runoff from precip. Runoff only on wet days with lag."""
    # Sort precip by date
    precip_df = precip_df.copy()
    precip_df["date"] = pd.to_datetime(precip_df[["Year", "Month", "Day"]])
    precip_df = precip_df.sort_values("date").set_index("date")

    rows = []
    # Simple unit-hydrograph-like response: runoff = alpha * precip + lagged contribution
    alpha = 0.15  # runoff coefficient for Walnut Gulch (semi-arid, low runoff ratio)
    lag1_runoff = 0.0

    for dt in sorted(precip_df.index):
        p = precip_df.loc[dt, "Gage_1"]
        if p > 0:
            # Direct runoff component
            runoff = alpha * p + lag1_runoff * 0.3
            # Add some noise
            runoff *= (1 + rng.gauss(0, 0.1))
            runoff = max(0.0, round(runoff, 2))
            # Occasionally produce flash flood (large runoff from moderate precip)
            if rng.random() < 0.02 and runoff > 1.0:
                runoff *= rng.uniform(1.5, 3.0)
                runoff = round(runoff, 2)
            rows.append({
                "Year": dt.year, "Month": dt.month, "Day": dt.day,
                "Flume_1": runoff,
            })
            lag1_runoff = runoff
        else:
            lag1_runoff *= 0.85  # recession

    df = pd.DataFrame(rows)
    logger.info("Runoff: %d event-days out of %d precip event-days", len(df), len(precip_df))
    return df


def split_by_year(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a DataFrame at year boundary (pre-2000 vs 2000+)."""
    df = df.copy()
    df["date"] = pd.to_datetime(df[["Year", "Month", "Day"]])
    pre = df[df["date"] < pd.Timestamp("2000-01-01")].drop(columns=["date"]).reset_index(drop=True)
    post = df[df["date"] >= pd.Timestamp("2000-01-01")].drop(columns=["date"]).reset_index(drop=True)
    return pre, post


def main() -> int:
    rng = random.Random(SEED)
    np.random.seed(SEED)

    ARS_DIR.mkdir(parents=True, exist_ok=True)

    # Generate precip
    precip_df = _generate_precip(rng)
    precip_pre, precip_post = split_by_year(precip_df)

    # Generate runoff from precip
    runoff_df = _generate_runoff(precip_df, rng)
    runoff_pre, runoff_post = split_by_year(runoff_df)

    # Write files
    files = {
        "wg_precip_rg82_analog_pre2000.csv": precip_pre,
        "wg_precip_rg82_digital_2000_present.csv": precip_post,
        "wg1_runoff_analog_pre2000.csv": runoff_pre,
        "wg1_runoff_digital_2000_present.csv": runoff_post,
    }

    for fname, df in files.items():
        path = ARS_DIR / fname
        df.to_csv(path, index=False)
        logger.info("Wrote %s (%d rows)", path, len(df))

    total_days = len(pd.date_range("1990-01-01", "2024-12-31"))
    total_precip_days = len(precip_df)
    total_runoff_days = len(runoff_df)
    logger.info(
        "Done. Period: %d years. Precip event-days: %d (%.1f%%). "
        "Runoff event-days: %d (%.1f%% of precip days).",
        total_days, total_precip_days,
        100 * total_precip_days / total_days,
        total_runoff_days, 100 * total_runoff_days / max(total_precip_days, 1),
    )
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
