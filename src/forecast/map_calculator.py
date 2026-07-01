"""
map_calculator.py — Mean Areal Precipitation Calculator
=========================================================
WHAT IS MAP (Mean Areal Precipitation)?
    Your watershed is 510 km². Rain doesn't fall uniformly.
    The north side might get 2 inches while the south gets 0.5.

    MAP = the AVERAGE rainfall over the ENTIRE watershed area.
    It's the single number that best represents "how much rain
    fell on this watershed."

WHY NOT JUST AVERAGE THE 5 POINTS?
    Because the points don't represent equal areas.
    The center point (near the outlet) represents a larger
    portion of the watershed than the edge points.

    Simple average: (2.0 + 0.5 + 1.0 + 0.3 + 0.8) / 5 = 0.92"
    Weighted MAP:   0.30×2.0 + 0.20×0.5 + 0.20×1.0 + 0.15×0.3 + 0.15×0.8
                  = 0.60 + 0.10 + 0.20 + 0.045 + 0.12 = 1.065"

    The weighted version gives MORE importance to the center
    (where the 2.0" fell), which is correct because that water
    reaches the outlet faster.

WHAT ARE ROLLING ACCUMULATIONS?
    Rainfall intensity matters over different time windows:

    1-hour:  Flash flood risk (arroyos, urban flooding)
    3-hour:  Short-duration storm total
    6-hour:  Moderate storm duration
    24-hour: Full-day storm total (river flooding)

    "Rolling" means a sliding window:
    Hour:  1  2  3  4  5  6  7  8
    Rain:  0  0  1  2  1  0  0  0

    3-hr rolling at hour 5 = rain[3]+rain[4]+rain[5] = 2+1+0 = 3
    3-hr rolling at hour 4 = rain[2]+rain[3]+rain[4] = 1+2+1 = 4  ← peak!

    The rolling window finds the WORST 3-hour period automatically.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple

from common.logging_setup import get_logger
from common.validators import validate_rainfall_data

logger = get_logger(__name__)


def compute_map(all_point_data: Dict[str, pd.DataFrame],
                grid_points: List[Dict]) -> pd.DataFrame:
    """
    Compute Mean Areal Precipitation from multiple grid points.

    Parameters
    ----------
    all_point_data : dict
        Keys = point IDs ("P1", "P2", ...), Values = DataFrames
        Each DataFrame: rows=hours, columns=ensemble members
    grid_points : list of dict
        Each dict has: id, lat, lon, weight, desc

    Returns
    -------
    pd.DataFrame
        MAP matrix: rows=hours, columns=ensemble members
        Each cell = weighted average precipitation across all points

    THE MATH:
        For each hour h and each ensemble member m:
        MAP[h,m] = Σ (weight_i × rainfall_i[h,m])

        Where i goes over all grid points (P1 through P5).
    """
    # Use the first point's index as reference
    first_id = grid_points[0]["id"]
    ref_index = all_point_data[first_id].index
    n_members = all_point_data[first_id].shape[1]
    member_cols = [f"member_{i:02d}" for i in range(n_members)]

    # Initialize MAP matrix with zeros
    map_matrix = pd.DataFrame(
        0.0, index=ref_index, columns=member_cols
    )

    # Weighted sum across all grid points
    total_weight = 0.0
    for pt in grid_points:
        pt_id = pt["id"]
        weight = pt["weight"]

        if pt_id not in all_point_data:
            logger.warning("Grid point %s has no data — skipping", pt_id)
            continue

        df = all_point_data[pt_id]

        # Validate the data before using it
        df = validate_rainfall_data(df, source=pt_id)

        # Align to reference index (in case some points have different times)
        df = df.reindex(ref_index, fill_value=0.0)
        df.columns = member_cols

        # Add weighted contribution
        map_matrix += weight * df
        total_weight += weight

    # Warn if weights don't sum to ~1.0
    if abs(total_weight - 1.0) > 0.01:
        logger.warning("Grid weights sum to %.3f (expected 1.0)", total_weight)

    logger.info("MAP computed: %d hours × %d members, "
                "total weight = %.3f",
                map_matrix.shape[0], map_matrix.shape[1], total_weight)

    return map_matrix


def compute_rolling_accumulations(map_matrix: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Compute rolling accumulations for standard durations.

    Parameters
    ----------
    map_matrix : pd.DataFrame
        MAP matrix from compute_map()

    Returns
    -------
    dict
        Keys: "1hr", "3hr", "6hr", "24hr"
        Values: DataFrames with rolling sums

    WHAT min_periods=1 MEANS:
        At the start of the data, a 24-hour window doesn't have
        24 hours of data yet. min_periods=1 means "compute the
        sum even if you only have 1 hour of data."

        Without this, the first 23 hours would be NaN (missing).
        With this, hour 1 = just hour 1, hour 2 = hour 1+2, etc.
    """
    accumulations = {
        "1hr":  map_matrix.copy(),
        "3hr":  map_matrix.rolling(3,  min_periods=1).sum(),
        "6hr":  map_matrix.rolling(6,  min_periods=1).sum(),
        "24hr": map_matrix.rolling(24, min_periods=1).sum(),
    }

    logger.info("Rolling accumulations computed: 1hr, 3hr, 6hr, 24hr")

    return accumulations


def compute_daily_statistics(map_matrix: pd.DataFrame,
                             accumulations: Dict[str, pd.DataFrame],
                             n_days: int = 7) -> List[Dict]:
    """
    Compute daily summary statistics from hourly ensemble data.

    For each day, we find:
    - P10, P50 (median), P90 of the max 24-hr accumulation
    - P50, P90 of the max 1-hr burst
    - P50 of the max 6-hr accumulation

    WHAT ARE PERCENTILES?
        31 ensemble members each predict different rainfall.
        Sort them from lowest to highest:

        Member values: [0, 0, 0.1, 0.2, 0.5, 0.8, 1.0, 1.2, ..., 5.0]

        P10 = 10th percentile = value where 10% of members are below
              → "optimistic" estimate (probably won't be this bad)
        P50 = 50th percentile = median = middle value
              → "most likely" estimate
        P90 = 90th percentile = value where 90% of members are below
              → "pessimistic" estimate (could be this bad)

        The SPREAD between P10 and P90 tells you UNCERTAINTY.
        Wide spread = very uncertain forecast.
        Narrow spread = high confidence.

    Returns
    -------
    list of dict
        One dict per day with all statistics.
    """
    roll_1hr = accumulations["1hr"]
    roll_6hr = accumulations["6hr"]
    roll_24hr = accumulations["24hr"]

    days_list = []

    for day_offset in range(n_days):
        day_start = map_matrix.index[0].normalize() + pd.Timedelta(days=day_offset)
        day_end = day_start + pd.Timedelta(days=1)
        mask = (map_matrix.index >= day_start) & (map_matrix.index < day_end)

        if mask.sum() == 0:
            continue

        # Max accumulation in each member for this day
        daily_24hr = roll_24hr[mask].max()
        daily_1hr = roll_1hr[mask].max()
        daily_6hr = roll_6hr[mask].max()

        # Percentiles across ensemble members
        day_stats = {
            "day": day_offset,
            "date": day_start.strftime("%Y-%m-%d"),
            "p10_24hr": round(float(np.percentile(daily_24hr, 10)), 3),
            "p50_24hr": round(float(np.percentile(daily_24hr, 50)), 3),
            "p90_24hr": round(float(np.percentile(daily_24hr, 90)), 3),
            "p50_1hr":  round(float(np.percentile(daily_1hr, 50)), 3),
            "p90_1hr":  round(float(np.percentile(daily_1hr, 90)), 3),
            "p50_6hr":  round(float(np.percentile(daily_6hr, 50)), 3),
        }

        days_list.append(day_stats)

    logger.info("Daily statistics computed for %d days", len(days_list))
    return days_list
