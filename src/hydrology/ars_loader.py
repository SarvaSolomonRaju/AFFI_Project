"""
ars_loader.py — Walnut Gulch dataset builder (USDA-ARS DAP source).

Walnut Gulch is operated by USDA-ARS (NOT USGS), so it has no API.
We read pre-downloaded CSVs from data/raw/ars/, densify the sparse
event-day format into a regular daily series, fetch temperature from
Open-Meteo, compute ET0, and emit a clean parquet identical in schema
to the USGS pipeline output.

INPUT FILES (must exist before running):
    data/raw/ars/wg1_runoff_analog_pre2000.csv
    data/raw/ars/wg1_runoff_digital_2000_present.csv
    data/raw/ars/wg_precip_rg82_analog_pre2000.csv
    data/raw/ars/wg_precip_rg82_digital_2000_present.csv

OUTPUT:
    data/interim/walnut_gulch_daily.parquet
    Columns: date (idx), precip_mm, tmax_c, tmin_c, et0_mm, runoff_mm

JUNIOR-DEV LESSONS:
    1. Sparse files lie. ARS only writes rows for non-zero days.
       If you forget to reindex, your model thinks 99% of days are missing.
    2. Validate column names AT BOUNDARIES. Trusting a CSV header is how
       silent bugs ship to production.
    3. Inner-join on dates — never forward-fill weather across gaps.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from common.paths import DATA_INTERIM, DATA_RAW
from hydrology.data_loader import (
    compute_et0_hargreaves,
    fetch_openmeteo_forcing,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — pinned to actual filenames you have on disk
# ---------------------------------------------------------------------------
ARS_DIR = DATA_RAW / "ars"

RUNOFF_FILES = [
    ARS_DIR / "wg1_runoff_analog_pre2000.csv",
    ARS_DIR / "wg1_runoff_digital_2000_present.csv",
]
PRECIP_FILES = [
    ARS_DIR / "wg_precip_rg82_analog_pre2000.csv",
    ARS_DIR / "wg_precip_rg82_digital_2000_present.csv",
]

RUNOFF_VALUE_COL = "Flume_1"   # depth in mm at WG1 outlet flume
PRECIP_VALUE_COL = "Gage_1"    # depth in mm at Rg82 rain gauge


# ---------------------------------------------------------------------------
# CSV readers
# ---------------------------------------------------------------------------
def _read_ars_csv(path: Path, value_col: str, out_name: str) -> pd.Series:
    """
    Read one ARS DAP CSV (Year,Month,Day,<value_col>) → Series indexed by date.

    Hard-fails on:
      - missing file
      - missing columns (format drift)
      - duplicate (Year,Month,Day) rows

    Returns sparse series (only event days). Caller must densify.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Required ARS file missing: {path}\n"
            f"Download from https://www.tucson.ars.ag.gov/dap/ and place at this path."
        )

    df = pd.read_csv(path)

    expected = {"Year", "Month", "Day", value_col}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(
            f"{path.name} missing columns {missing}. "
            f"Found: {list(df.columns)}. "
            f"ARS may have changed export format — inspect file and update parser."
        )

    # Compose date column. errors='raise' so bad rows fail loudly.
    df["date"] = pd.to_datetime(df[["Year", "Month", "Day"]], errors="raise")

    # Detect duplicate dates BEFORE silently aggregating
    dup_mask = df["date"].duplicated(keep=False)
    if dup_mask.any():
        n_dup = int(dup_mask.sum())
        logger.warning(
            "%s: %d duplicate dates found — summing values for those days "
            "(typically multiple sub-events on same day).",
            path.name, n_dup,
        )
        df = df.groupby("date", as_index=True)[value_col].sum().to_frame()
    else:
        df = df.set_index("date")[[value_col]]

    series = df[value_col].astype("float64").rename(out_name)
    logger.info(
        "Loaded %s: %d event-day rows, %s → %s",
        path.name, len(series), series.index.min().date(), series.index.max().date(),
    )
    return series


def _load_concat_densify(files: list[Path], value_col: str, out_name: str) -> pd.Series:
    """Read multiple ARS CSVs, concatenate, densify (fill non-event days with 0)."""
    parts = [_read_ars_csv(f, value_col, out_name) for f in files]
    combined = pd.concat(parts).sort_index()

    # Concatenated files may overlap at boundaries — drop duplicate dates,
    # keeping the digital (last) record because it supersedes analog reprocessing.
    if combined.index.has_duplicates:
        n = combined.index.duplicated(keep="last").sum()
        logger.info("Dropped %d overlapping rows at analog/digital boundary.", n)
        combined = combined[~combined.index.duplicated(keep="last")]

    # CRITICAL: densify. Sparse → full daily range, fill 0.0 for dry days.
    full_range = pd.date_range(combined.index.min(), combined.index.max(), freq="D")
    dense = combined.reindex(full_range, fill_value=0.0)
    dense.index.name = "date"

    n_event = int((dense > 0).sum())
    n_total = len(dense)
    logger.info(
        "Densified %s: %d days total, %d event-days (%.2f%%), %.2f mm mean on event-days",
        out_name, n_total, n_event, 100 * n_event / n_total,
        dense[dense > 0].mean() if n_event else 0.0,
    )
    return dense


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WalnutGulchSpec:
    """Static descriptor for Walnut Gulch (mirrors BasinSpec for USGS path)."""
    name: str = "walnut_gulch"
    lat: float = 31.7244        # WGEW centroid (Tombstone, AZ)
    lon: float = -110.0581
    area_km2: float = 150.0     # WG1 outlet drainage = entire watershed


def build_walnut_gulch_dataset(
    start_date: str | None = None,
    end_date: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Build full daily dataset for Walnut Gulch.

    Args:
        start_date: ISO 'YYYY-MM-DD' clip start; None = use ARS earliest.
        end_date:   ISO 'YYYY-MM-DD' clip end; None = use ARS latest.
        force_refresh: if True, redownload Open-Meteo (ARS is local, never re-fetched).

    Returns:
        DataFrame indexed by date with columns:
            precip_mm, tmax_c, tmin_c, et0_mm, runoff_mm
    """
    spec = WalnutGulchSpec()
    out_path = DATA_INTERIM / f"{spec.name}_daily.parquet"

    if out_path.exists() and not force_refresh:
        logger.info("Cached interim dataset exists → %s (use force_refresh=True to rebuild)", out_path)
        return pd.read_parquet(out_path)

    logger.info("Building Walnut Gulch dataset from ARS sources …")

    # 1) Local ARS files — runoff (target) and precipitation (forcing)
    runoff = _load_concat_densify(RUNOFF_FILES, RUNOFF_VALUE_COL, "runoff_mm")
    precip = _load_concat_densify(PRECIP_FILES, PRECIP_VALUE_COL, "precip_mm")

    # 2) Open-Meteo for temperature only (ARS forcing decision: option iii)
    om_start = start_date or str(min(runoff.index.min(), precip.index.min()).date())
    om_end   = end_date   or str(max(runoff.index.max(), precip.index.max()).date())

    forcing = fetch_openmeteo_forcing(
    site_id=spec.name,
    lat=spec.lat,
    lon=spec.lon,
    start_date=om_start,
    end_date=om_end,
    force_refresh=force_refresh,
)
    # We only want temperature columns from Open-Meteo (precip comes from ARS Rg82)
    # Extract temperature DataFrame (keep original column names for ET0 helper)
    # Extract temperature DataFrame
    temps_raw = forcing[["temp_max_c", "temp_min_c"]].copy()

    # ADD THIS LINE (compute mean temp)
    temps_raw["temp_mean_c"] = (temps_raw["temp_max_c"] + temps_raw["temp_min_c"]) / 2

    # ET0 via Hargreaves
    et0 = compute_et0_hargreaves(temps_raw, spec.lat).rename("et0_mm")

    # Rename for final dataset
    temps = temps_raw.rename(columns={
    "temp_max_c": "tmax_c",
    "temp_min_c": "tmin_c"
    })[["tmax_c", "tmin_c"]]

    # 4) Inner-join everything — lose only days where ANY input is missing
    df = pd.concat([precip, temps, et0, runoff], axis=1, join="inner")
    df.index.name = "date"

    # 5) Optional user-specified clip
    if start_date:
        df = df.loc[df.index >= pd.Timestamp(start_date)]
    if end_date:
        df = df.loc[df.index <= pd.Timestamp(end_date)]

    # 6) Sanity checks (fail loud if data is broken)
    if df.empty:
        raise RuntimeError("Joined dataset is empty — check date ranges and file contents.")
    if df.isna().any().any():
        bad = df.isna().sum()
        raise RuntimeError(f"NaNs found after inner-join — should not happen:\n{bad[bad > 0]}")
    if (df["runoff_mm"] < 0).any() or (df["precip_mm"] < 0).any():
        raise RuntimeError("Negative depth values detected — data corruption.")

    # 7) Persist
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path)
    logger.info(
        "✓ Saved %s: %d rows × %d cols, %s → %s, runoff event-day rate %.2f%%",
        out_path.name, *df.shape,
        df.index.min().date(), df.index.max().date(),
        100 * (df["runoff_mm"] > 0).mean(),
    )
    return df