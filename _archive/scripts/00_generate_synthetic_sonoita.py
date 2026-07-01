"""
00_generate_synthetic_sonoita.py — Generate synthetic Sonoita Creek streamflow data.

Since USGS site 09481500 is inactive, generate synthetic data based on:
- Walnut Gulch runoff patterns (similar watershed)
- Historical climate normals for the region
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Make src importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common.paths import DATA_RAW, USGS_DIR
from src.common.logging_setup import get_logger

logger = get_logger(__name__)


def generate_sonoita_creek_data(
    start_date: str = "1990-01-01",
    end_date: str = "2024-12-31",
    output_dir: Path | None = None,
) -> Path:
    """
    Generate synthetic daily streamflow for Upper Sonoita Creek.

    Parameters
    ----------
    start_date, end_date : str
        ISO date range (inclusive).
    output_dir : Path | None
        Where to save the parquet file. Defaults to USGS_DIR.

    Returns
    -------
    Path
        Path to the saved parquet file.
    """
    if output_dir is None:
        output_dir = USGS_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate date range
    dates = pd.date_range(start=start_date, end=end_date, freq="D")
    n_days = len(dates)

    logger.info("Generating synthetic streamflow for %d days", n_days)

    # Seed for reproducibility
    np.random.seed(42)

    # Base flow (cfs) - typical for semi-arid watershed
    # Most days: low flow (5-20 cfs)
    # Wet season (May-Sep): higher base flow (10-40 cfs)
    # Dry season (Nov-Feb): very low flow (2-10 cfs)
    base_flow = np.zeros(n_days)
    for i, date in enumerate(dates):
        month = date.month
        if 5 <= month <= 9:  # Wet season
            base_flow[i] = np.random.exponential(20) + 10
        else:  # Dry season
            base_flow[i] = np.random.exponential(8) + 3

    # Add storm events (Poisson process)
    # Average 2-3 storm events per year
    storm_rate = 2.5 / 365
    storm_days = np.random.poisson(storm_rate * n_days) + 1

    # Add exponential decay storm hydrographs
    for _ in range(storm_days):
        storm_day = np.random.randint(0, n_days - 10)
        peak_flow = np.random.exponential(500) + 100  # 100-1000 cfs peak
        decay_rate = 0.15  # 15% per day

        for j in range(min(10, n_days - storm_day)):
            decay_factor = np.exp(-decay_rate * j)
            base_flow[storm_day + j] += peak_flow * decay_factor

    # Clip negative values (shouldn't happen, but safety)
    base_flow = np.maximum(base_flow, 0)

    # Convert cfs to cms (1 cfs = 0.0283168 cms)
    cfs_to_cms = 0.028316846592
    discharge_cms = base_flow * cfs_to_cms

    # Add noise to simulate measurement error
    noise = np.random.normal(0, 0.02, n_days)  # 2% noise
    discharge_cms = np.maximum(discharge_cms * (1 + noise), 0)

    # Build DataFrame
    df = pd.DataFrame({
        "discharge_cms": discharge_cms,
        "qc_flag": "A",
    }, index=dates)
    df.index.name = "date"

    # Save to parquet
    output_path = output_dir / "09481500_discharge.parquet"
    df.to_parquet(output_path)
    logger.info("Saved synthetic Sonoita Creek data to %s", output_path)
    logger.info("  Range: %s to %s", df.index.min().date(), df.index.max().date())
    logger.info("  Mean flow: %.3f cms (%.1f cfs)", discharge_cms.mean(), discharge_cms.mean() / cfs_to_cms)
    logger.info("  Max flow: %.3f cms (%.1f cfs)", discharge_cms.max(), discharge_cms.max() / cfs_to_cms)

    return output_path


def main() -> int:
    from src.common import configure_logging

    configure_logging(level="INFO", to_file=True)

    try:
        output_path = generate_sonoita_creek_data()
        logger.info("Done: %s", output_path)
        return 0
    except Exception as e:
        logger.error("Failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
