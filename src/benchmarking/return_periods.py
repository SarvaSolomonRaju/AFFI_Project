"""NOAA Atlas-14 return-period benchmarks for Sonoita Creek / Patagonia, AZ.

Atlas-14 point-precipitation frequency estimates (24-hour duration) sourced
from NOAA Precipitation Frequency Data Server (PFDS) for Patagonia, AZ
(approx. 31.54N, -110.75W). Values are the median (50% confidence) annual
maxima depths in inches for the listed return periods.

Discharge return periods are estimated by log-linear interpolation against
the Task 2 training-set percentiles (USGS 09481500 daily Q).
"""
from __future__ import annotations
from typing import Dict, List, Tuple

import math

# --------- NOAA Atlas-14 24-hr point precipitation, Patagonia AZ ----------
# (Return-period years, depth in inches, 24-hr duration, 50% confidence)
ATLAS14_24HR_PATAGONIA_AZ: List[Tuple[int, float]] = [
    (1,    1.49),
    (2,    1.83),
    (5,    2.45),
    (10,   2.97),
    (25,   3.71),
    (50,   4.32),
    (100,  4.97),
    (200,  5.66),
    (500,  6.63),
]


def nws_atlas14_sonoita() -> Dict[str, float]:
    """Return Atlas-14 24-hr return-period depths (inches) as a dict."""
    return {f"{rp}yr": depth for rp, depth in ATLAS14_24HR_PATAGONIA_AZ}


def _loglin_interp(x: float, table: List[Tuple[float, float]]) -> float:
    """Log-linear interpolation: x in linear, y in log space."""
    xs = [t[0] for t in table]
    ys = [t[1] for t in table]
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            x_lo, x_hi = xs[i], xs[i + 1]
            y_lo, y_hi = math.log(max(ys[i], 1e-9)), math.log(max(ys[i + 1], 1e-9))
            w = (x - x_lo) / (x_hi - x_lo)
            return math.exp(y_lo + w * (y_hi - y_lo))
    return ys[-1]


def rainfall_to_return_period(rainfall_inches: float) -> dict:
    """Map 24-hr rainfall depth to nearest Atlas-14 return period."""
    p = float(rainfall_inches)
    # Find bracket
    if p < ATLAS14_24HR_PATAGONIA_AZ[0][1]:
        return {"nearest_rp_yr": "< 1yr", "rp_yr_estimate": 0.5,
                "rainfall_inches": p}
    for i in range(len(ATLAS14_24HR_PATAGONIA_AZ) - 1):
        rp_lo, d_lo = ATLAS14_24HR_PATAGONIA_AZ[i]
        rp_hi, d_hi = ATLAS14_24HR_PATAGONIA_AZ[i + 1]
        if d_lo <= p <= d_hi:
            # log-linear interp on return period
            w = (p - d_lo) / (d_hi - d_lo)
            log_rp = math.log(rp_lo) + w * (math.log(rp_hi) - math.log(rp_lo))
            return {"nearest_rp_yr": f"{rp_lo}-{rp_hi}yr",
                    "rp_yr_estimate": float(math.exp(log_rp)),
                    "rainfall_inches": p}
    return {"nearest_rp_yr": "> 500yr", "rp_yr_estimate": 1000.0,
            "rainfall_inches": p}


# --------- Discharge return periods (USGS 09481500, training-set anchors) ----------
# Calibrated against the Task 2 training percentiles:
#   p90 = 1.67 cms,  p95 = 4.04 cms,  p99 = 18.48 cms (daily mean)
# Peak/daily ratio for flashy semi-arid basin ~3-5x. Anchor table below
# blends Atlas-14 storm depths with Sonoita's training distribution to give
# approximate Q vs return-period mapping for daily-mean discharge:
Q_RETURN_TABLE_CMS: List[Tuple[int, float]] = [
    (1,    0.5),
    (2,    1.5),
    (5,    4.0),
    (10,   9.0),
    (25,  20.0),
    (50,  35.0),
    (100, 60.0),
    (200, 90.0),
    (500, 150.0),
]


def discharge_to_return_period(q_cms: float, table: List[Tuple[int, float]] = None) -> dict:
    """Map a discharge to an approximate return period (years).

    `table` defaults to Q_RETURN_TABLE_CMS (a "daily-mean discharge" scale
    blending Atlas-14 with Task 2 training percentiles). Pass the flood
    library's own return_periods table (LP-III peak discharge, e.g.
    Q2=83.6 cms -- see data/flood_library_real/manifest.json) instead when
    comparing against something measured on a peak-discharge scale, such
    as the historical event catalog's peak_q_cms -- mixing the two scales
    silently compares apples to oranges (peak Q is naturally much larger
    than daily-mean Q for a flashy ephemeral stream).
    """
    tbl = table if table is not None else Q_RETURN_TABLE_CMS
    q = float(q_cms)
    if q <= tbl[0][1]:
        return {"nearest_rp_yr": f"< {tbl[0][0]}yr", "rp_yr_estimate": tbl[0][0] * 0.5, "q_cms": q}
    for i in range(len(tbl) - 1):
        rp_lo, q_lo = tbl[i]
        rp_hi, q_hi = tbl[i + 1]
        if q_lo <= q <= q_hi:
            w = (q - q_lo) / (q_hi - q_lo)
            log_rp = math.log(rp_lo) + w * (math.log(rp_hi) - math.log(rp_lo))
            return {"nearest_rp_yr": f"{rp_lo}-{rp_hi}yr",
                    "rp_yr_estimate": float(math.exp(log_rp)),
                    "q_cms": q}
    top_rp = tbl[-1][0]
    return {"nearest_rp_yr": f"> {top_rp}yr", "rp_yr_estimate": float(top_rp * 2), "q_cms": q}


def return_period_table() -> List[dict]:
    """Combined Atlas-14 rainfall + estimated Q return-period table."""
    rows = []
    for (rp_p, p), (rp_q, q) in zip(ATLAS14_24HR_PATAGONIA_AZ, Q_RETURN_TABLE_CMS):
        rows.append({
            "return_period_yr": rp_p,
            "atlas14_24hr_in": p,
            "estimated_peak_q_cms": q,
        })
    return rows
