"""
alert_engine.py — Alert Classification Engine
================================================
WHAT THIS DOES:
    Takes daily rainfall statistics and decides:
    GREEN     → No significant rainfall expected
    ADVISORY  → Light rainfall, be aware
    WATCH     → Moderate rainfall, prepare for possible flooding
    WARNING   → Heavy rainfall, flooding likely

HOW ALERTS ARE DETERMINED:
    Step 1: Calculate thresholds from IDF benchmarks
        Advisory threshold = 25% of 10-year 24hr storm
        Watch threshold    = 40% of 10-year 24hr storm
        Warning threshold  = 65% of 10-year 24hr storm

    Step 2: Count how many ensemble members exceed each threshold
        "Probability of Exceedance" (PoE)
        If 15 out of 31 members exceed Warning threshold:
        PoE = 15/31 = 48.4%

    Step 3: Compare PoE against trigger percentages
        WARNING:  PoE ≥ 30% for warning threshold
        WATCH:    PoE ≥ 30% for watch threshold
        ADVISORY: PoE ≥ 20% for advisory threshold
        GREEN:    None of the above

WHY PROBABILITY-BASED (not just "will it rain X inches")?
    Single-value forecasts are WRONG most of the time.
    "It will rain 2.5 inches" — but what if it rains 0.5 or 5.0?

    Probability-based: "There's a 45% chance of >2 inches"
    This is HONEST about uncertainty. Emergency managers can
    make better decisions with probabilities than point forecasts.

    This is how the National Weather Service issues watches/warnings.

WHAT IS "STORM INDEX"?
    Storm Index = P50_24hr / IDF_10yr_24hr

    If Storm Index = 0.5 → forecast is half a 10-year storm
    If Storm Index = 1.0 → forecast equals a 10-year storm
    If Storm Index = 2.0 → forecast is TWICE a 10-year storm

    This normalizes rainfall to a universal scale.
    A Storm Index of 0.5 means the same thing whether you're
    in Patagonia AZ or Houston TX — "half of what a 10-year
    storm would produce here."
"""

import numpy as np
from typing import Dict, List, Any

from common.logging_setup import get_logger

logger = get_logger(__name__)


class AlertEngine:
    """
    Classifies daily forecasts into alert levels.

    HOW TO USE:
        engine = AlertEngine(idf_10yr, alert_thresholds)
        classified_days = engine.classify_days(daily_stats, accumulations)
    """

    def __init__(self, idf_10yr: Dict[str, float], 
                 alert_config: Any):
        """
        Initialize with IDF benchmarks and threshold configuration.

        Parameters
        ----------
        idf_10yr : dict
            10-year IDF values: {"1hr": 1.40, "24hr": 3.10, ...}
        alert_config : AlertThresholds (from settings)
            Contains advisory/watch/warning fraction and trigger values
        """
        self.idf_10yr = idf_10yr
        self.config = alert_config

        # Pre-compute actual thresholds in inches
        self.thresholds = {
            "advisory": {
                "24hr": alert_config.advisory.fraction_of_10yr_24hr * idf_10yr["24hr"],
                "1hr":  alert_config.advisory.fraction_of_10yr_1hr * idf_10yr["1hr"],
                "trigger_pct": alert_config.advisory.probability_trigger_pct,
            },
            "watch": {
                "24hr": alert_config.watch.fraction_of_10yr_24hr * idf_10yr["24hr"],
                "1hr":  alert_config.watch.fraction_of_10yr_1hr * idf_10yr["1hr"],
                "trigger_pct": alert_config.watch.probability_trigger_pct,
            },
            "warning": {
                "24hr": alert_config.warning.fraction_of_10yr_24hr * idf_10yr["24hr"],
                "1hr":  alert_config.warning.fraction_of_10yr_1hr * idf_10yr["1hr"],
                "trigger_pct": alert_config.warning.probability_trigger_pct,
            },
        }

        logger.info("Alert thresholds (inches):")
        for level, vals in self.thresholds.items():
            logger.info("  %s: 24hr=%.2f\" 1hr=%.2f\" trigger=%.0f%%",
                       level.upper(), vals["24hr"], vals["1hr"], vals["trigger_pct"])

    @staticmethod
    def probability_of_exceedance(member_values, threshold: float) -> float:
        """
        Calculate what percentage of ensemble members exceed a threshold.

        Parameters
        ----------
        member_values : array-like
            Values from all ensemble members (e.g., 31 values)
        threshold : float
            The threshold to check against (in inches or mm)

        Returns
        -------
        float
            Percentage (0-100) of members exceeding the threshold

        EXAMPLE:
            members = [0.1, 0.5, 1.2, 2.0, 3.5, ...]  (31 values)
            threshold = 1.0

            Members ≥ 1.0: [1.2, 2.0, 3.5, ...] = 15 members
            PoE = 15/31 × 100 = 48.4%
        """
        values = np.array(member_values)
        return float(np.mean(values >= threshold) * 100)

    def classify_day(self, day_stats: Dict, 
                     daily_24hr_members, 
                     daily_1hr_members) -> Dict:
        """
        Classify a single day into an alert level.

        Parameters
        ----------
        day_stats : dict
            Pre-computed statistics (p10, p50, p90, etc.)
        daily_24hr_members : array-like
            Max 24-hr accumulation for each ensemble member
        daily_1hr_members : array-like
            Max 1-hr intensity for each ensemble member

        Returns
        -------
        dict
            day_stats enriched with alert classification
        """
        result = dict(day_stats)  # Copy, don't modify original

        # Compute PoE for each alert level
        for level_name, level_thresh in self.thresholds.items():
            poe_24 = self.probability_of_exceedance(
                daily_24hr_members, level_thresh["24hr"]
            )
            poe_1h = self.probability_of_exceedance(
                daily_1hr_members, level_thresh["1hr"]
            )
            result[f"thr_{level_name}_24hr_in"] = round(level_thresh["24hr"], 2)
            result[f"thr_{level_name}_1hr_in"] = round(level_thresh["1hr"], 2)
            result[f"poe_{level_name}_24hr"] = round(poe_24, 1)
            result[f"poe_{level_name}_1hr"] = round(poe_1h, 1)

        # Storm Index (fraction of 10-year storm)
        result["storm_index_24hr"] = round(
            day_stats["p50_24hr"] / self.idf_10yr["24hr"], 3
        )
        result["storm_index_1hr"] = round(
            day_stats.get("p90_1hr", 0) / self.idf_10yr["1hr"], 3
        )

        # Determine alert level (highest triggered wins)
        # Check WARNING first (most severe), then WATCH, then ADVISORY
        warn = self.thresholds["warning"]
        watch = self.thresholds["watch"]
        adv = self.thresholds["advisory"]

        if (result["poe_warning_24hr"] >= warn["trigger_pct"] or 
            result["poe_warning_1hr"] >= warn["trigger_pct"]):
            result["alert_level"] = "WARNING"
        elif (result["poe_watch_24hr"] >= watch["trigger_pct"] or 
              result["poe_watch_1hr"] >= watch["trigger_pct"]):
            result["alert_level"] = "WATCH"
        elif result["poe_advisory_24hr"] >= adv["trigger_pct"]:
            result["alert_level"] = "ADVISORY"
        else:
            result["alert_level"] = "GREEN"

        return result

    def classify_all_days(self, daily_stats: List[Dict],
                          accumulations: Dict,
                          map_matrix) -> List[Dict]:
        """
        Classify all forecast days.

        Parameters
        ----------
        daily_stats : list of dict
            From map_calculator.compute_daily_statistics()
        accumulations : dict
            Rolling accumulations from map_calculator
        map_matrix : pd.DataFrame
            The MAP matrix (needed to extract per-member values)

        Returns
        -------
        list of dict
            Each day enriched with alert classification
        """
        import pandas as pd

        # accumulations is raw mm (see map_calculator.compute_rolling_
        # accumulations) but every threshold in self.thresholds is in
        # inches (built from idf_10yr, an inches table) -- convert here,
        # same fix as map_calculator.compute_daily_statistics, since this
        # method re-derives its own per-member arrays from `accumulations`
        # rather than reusing that function's already-converted output.
        MM_TO_IN = 25.4
        roll_24hr = accumulations["24hr"] / MM_TO_IN
        roll_1hr = accumulations["1hr"] / MM_TO_IN

        classified = []
        for day_info in daily_stats:
            day_offset = day_info["day"]
            day_start = map_matrix.index[0].normalize() + pd.Timedelta(days=day_offset)
            day_end = day_start + pd.Timedelta(days=1)
            mask = (map_matrix.index >= day_start) & (map_matrix.index < day_end)

            if mask.sum() == 0:
                day_info["alert_level"] = "GREEN"
                classified.append(day_info)
                continue

            daily_24hr_max = roll_24hr[mask].max()  # Max per member
            daily_1hr_max = roll_1hr[mask].max()

            result = self.classify_day(day_info, daily_24hr_max, daily_1hr_max)
            classified.append(result)

            logger.debug("Day %d (%s): %s (SI=%.3f, PoE_warn=%.1f%%)",
                        day_offset, day_info["date"], result["alert_level"],
                        result["storm_index_24hr"], result["poe_warning_24hr"])

        # Summary
        alert_counts = {}
        for d in classified:
            level = d["alert_level"]
            alert_counts[level] = alert_counts.get(level, 0) + 1

        logger.info("Alert classification complete: %s", alert_counts)

        return classified


def build_return_period_comparison(day_stats: Dict, 
                                   idf_all: Dict[str, Dict[str, float]]) -> Dict:
    """
    Compare a day's forecast against ALL return periods (2yr to 100yr).

    This is for Task 5 (benchmarking) but we include it here
    because it uses the same alert engine logic.

    Parameters
    ----------
    day_stats : dict
        One day's classified statistics
    idf_all : dict
        Full IDF table: {"2yr": {"24hr": 1.90}, "10yr": {"24hr": 3.10}, ...}

    Returns
    -------
    dict
        Return period classification for this day

    EXAMPLE OUTPUT:
        {
            "p50_24hr": 2.5,
            "nearest_return_period": "5yr",
            "exceeds_10yr": False,
            "exceeds_100yr": False,
            "severity_class": "Moderate (5-10yr range)"
        }
    """
    p50 = day_stats.get("p50_24hr", 0)
    p90 = day_stats.get("p90_24hr", 0)

    # Find which return period bracket the forecast falls in
    periods_ordered = ["2yr", "5yr", "10yr", "25yr", "50yr", "100yr"]

    nearest = "< 2yr"
    for period in periods_ordered:
        if period in idf_all and "24hr" in idf_all[period]:
            if p50 >= idf_all[period]["24hr"]:
                nearest = period

    # Severity class
    if p50 < idf_all.get("2yr", {}).get("24hr", 999):
        severity = "Minor (< 2-year storm)"
    elif p50 < idf_all.get("10yr", {}).get("24hr", 999):
        severity = "Moderate (2-10yr range)"
    elif p50 < idf_all.get("50yr", {}).get("24hr", 999):
        severity = "Severe (10-50yr range)"
    else:
        severity = "Extreme (≥ 50-year storm)"

    return {
        "p50_24hr": p50,
        "p90_24hr": p90,
        "nearest_return_period": nearest,
        "exceeds_10yr": p50 >= idf_all.get("10yr", {}).get("24hr", 999),
        "exceeds_100yr": p50 >= idf_all.get("100yr", {}).get("24hr", 999),
        "severity_class": severity,
    }
