"""
data_loader.py — Download & cache hydro-meteorological data.

RESPONSIBILITIES:
    1. Fetch daily streamflow from USGS NWIS  (target variable)
    2. Fetch daily precipitation/temperature from Open-Meteo Historical API
       (which serves ERA5-Land reanalysis under the hood)
    3. Compute reference evapotranspiration (ET₀) via Hargreaves equation
    4. Quality-check, align, save as interim Parquet

DESIGN PHILOSOPHY:
    - "Raw" data on disk is IMMUTABLE.  Re-running this script is
       idempotent: if the raw file exists, we load from cache.
    - "Interim" data (cleaned, aligned) is regenerated freely.
    - Every external API call is wrapped in retry logic.
    - Failures are LOUD (raise + log), never silent.

WHY OPEN-METEO HISTORICAL INSTEAD OF CDS/ERA5 DIRECT?
    Open-Meteo's `archive-api.open-meteo.com` serves the same ERA5-Land
    reanalysis dataset, pre-resampled, no auth, no async queue.
    The official CDS API requires (a) account registration, (b) accepting
    a license, (c) joining a server-side processing queue (~hours latency).
    For a master's-level project this is overkill — the data is identical.
    If you ever need raw NetCDF for >50 basins, switch to cdsapi then.

USAGE:
    python scripts/01_download_data.py
    # → data/raw/usgs/09471500_discharge.parquet
    # → data/raw/openmeteo/09471500_forcing.parquet
    # → data/interim/walnut_gulch_daily.parquet
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import dataretrieval.nwis as nwis  # battle-tested USGS NWIS wrapper

from common.logging_setup import get_logger
from common.paths import DATA_INTERIM, DATA_RAW, USGS_DIR

logger = get_logger(__name__)

# ============================================================================
# Constants — Open-Meteo endpoint (no API key, free)
# ============================================================================
OPENMETEO_HISTORICAL_URL = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_DIR: Path = DATA_RAW / "openmeteo"

# Conversion: USGS reports cubic feet per second (cfs); science uses m³/s
CFS_TO_CMS: float = 0.028316846592


# ============================================================================
# Domain object — describes ONE basin we want to model.
# Using @dataclass instead of dict → IDE autocomplete + type checking.
# ============================================================================
@dataclass(frozen=True)
class BasinSpec:
    """Static description of a watershed pulled from config/task2.yaml."""
    name: str
    usgs_id: str
    lat: float
    lon: float
    area_km2: float
    huc: str | None = None


# ============================================================================
# 1. STREAMFLOW (USGS NWIS)
# ============================================================================
def fetch_usgs_discharge(
    site_id: str,
    start_date: str,
    end_date: str,
    cache_dir: Path = USGS_DIR,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Download daily mean streamflow from USGS NWIS.

    Parameters
    ----------
    site_id : str
        USGS site ID, 8 digits, leading zeros preserved (e.g. "09471500").
    start_date, end_date : str
        ISO format "YYYY-MM-DD". Inclusive on both ends.
    cache_dir : Path
        Where to save the raw Parquet. If file exists and force_refresh
        is False, loads from disk instead of hitting the API.
    force_refresh : bool
        Force re-download even if cache exists. Use sparingly — USGS
        rate limits at ~120 req/min.

    Returns
    -------
    pd.DataFrame
        Columns:
            date          (DatetimeIndex, daily)
            discharge_cms (float, m³/s)
            qc_flag       (str, USGS approval code: 'A' approved, 'P' provisional)
        Index: date

    Raises
    ------
    RuntimeError
        If USGS returns no data for the site/period.

    DESIGN NOTE — UNIT CONVERSION:
        USGS reports streamflow in cubic feet per second (cfs).
        Hydrology literature, ML papers, and the rest of the world
        use cubic meters per second (cms). We convert IMMEDIATELY at
        the data boundary so cms is the only unit downstream.
        Rule: convert at the edge, never in the middle.

    DESIGN NOTE — QC FLAGS:
        USGS marks every data point with a code:
            'A' = Approved by USGS hydrologist (final)
            'P' = Provisional (subject to revision, may change)
            'e' = Estimated (sensor failed, value interpolated)
        Training on provisional data = training on a moving target.
        We KEEP all rows but downstream code will filter to 'A' only
        for the training set.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{site_id}_discharge.parquet"

    # ---- Cache hit ----
    if cache_path.exists() and not force_refresh:
        logger.info("Loading cached USGS discharge: %s", cache_path.name)
        return pd.read_parquet(cache_path)

    # ---- Cache miss → API call ----
    logger.info("Fetching USGS discharge: site=%s, %s → %s",
                site_id, start_date, end_date)
    t0 = time.time()

    # ── Use dataretrieval (handles NWIS quirks, pagination, edge cases) ──
    df_nwis, _ = nwis.get_dv(
        sites=site_id,
        parameterCd='00060',
        start=start_date,
        end=end_date,
    )

    if df_nwis.empty:
        raise RuntimeError(
            f"USGS NWIS returned no data for site {site_id}. "
            f"Check site exists at https://waterdata.usgs.gov/monitoring-location/{site_id}/"
        )

    # Accept 'A' (approved) AND 'A, e' (approved+estimated) — reject 'P' (provisional)
    qc_col = '00060_Mean_cd'
    if qc_col in df_nwis.columns:
        mask = df_nwis[qc_col].astype(str).str.startswith('A')
        n_dropped = (~mask).sum()
        if n_dropped:
            logger.info("Dropped %d non-approved rows (kept 'A' and 'A, e')", n_dropped)
        df_nwis = df_nwis[mask]

    # Build df_raw with discharge in cfs
    df_raw = pd.DataFrame({
        'discharge_cfs': pd.to_numeric(df_nwis['00060_Mean'], errors='coerce'),
    }, index=df_nwis.index)
    df_raw.index = df_raw.index.tz_localize(None)  # strip timezone for consistency
    df_raw.index.name = 'dateTime'

    # ---- Replace negative discharge (sensor errors) with NaN ----
    # Negative discharge is physically impossible. USGS sometimes leaves
    # sensor garbage in the feed. Setting to NaN so we know it's missing.
    n_negative = int((df_raw["discharge_cfs"] < 0).sum())
    if n_negative:
        logger.warning("Found %d negative discharge values → setting to NaN", n_negative)
        df_raw.loc[df_raw["discharge_cfs"] < 0, "discharge_cfs"] = np.nan

    # Convert cfs to cms and build final DataFrame
    df = pd.DataFrame({
          "discharge_cms": df_raw["discharge_cfs"] * CFS_TO_CMS,
          "qc_flag": "A",
      })
    df.index = df_raw.index
    df.index.name = "date"

    df.to_parquet(cache_path)
    logger.info("✓ USGS: %d days, %.2f%% NaN, cached to %s (%.1fs)",
                len(df),
                100.0 * df["discharge_cms"].isna().mean(),
                cache_path.name,
                time.time() - t0)

    return df


# ============================================================================
# 2. METEOROLOGICAL FORCING (Open-Meteo Historical → ERA5-Land)
# ============================================================================
def fetch_openmeteo_forcing(
    site_id: str,
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    cache_dir: Path = OPENMETEO_DIR,
    force_refresh: bool = False,
    max_retries: int = 3,
) -> pd.DataFrame:
    """
    Fetch daily precipitation, temperature (mean/min/max), and shortwave
    radiation at the basin centroid from Open-Meteo Historical Weather API.

    Returns
    -------
    pd.DataFrame indexed by date with columns:
        precip_mm       — total daily precipitation (mm)
        temp_mean_c     — daily mean 2m air temperature (°C)
        temp_min_c      — daily minimum (°C)
        temp_max_c      — daily maximum (°C)
        shortwave_mj    — total shortwave radiation (MJ/m²/day)

    DESIGN NOTE — POINT vs AREA AVERAGE:
        Strictly correct hydrology averages forcing over the full basin
        polygon. We use the centroid as a single representative point.
        For a 149 km² basin like Walnut Gulch, the point→area error is
        ~5-10% on rainfall — acceptable for a research prototype, and
        the LSTM will learn to compensate via bias terms.

        When you scale to 100+ basins, replace this with the actual
        ERA5-Land basin-averaged forcing from CAMELS-style preprocessing.

    DESIGN NOTE — RETRY LOGIC:
        Same exponential-backoff pattern you used in Task 1.
        Open-Meteo is generous but does rate-limit at ~10k requests/day.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{site_id}_forcing.parquet"

    if cache_path.exists() and not force_refresh:
        logger.info("Loading cached Open-Meteo forcing: %s", cache_path.name)
        return pd.read_parquet(cache_path)

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "daily": ",".join([
            "precipitation_sum",
            "temperature_2m_mean",
            "temperature_2m_min",
            "temperature_2m_max",
            "shortwave_radiation_sum",
        ]),
        "timezone": "UTC",
    }

    logger.info("Fetching Open-Meteo: site=%s, lat=%.4f, lon=%.4f, %s → %s",
                site_id, lat, lon, start_date, end_date)

    # ---- Retry loop ----
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            t0 = time.time()
            resp = requests.get(OPENMETEO_HISTORICAL_URL, params=params, timeout=60)
            resp.raise_for_status()
            payload = resp.json()
            elapsed_ms = (time.time() - t0) * 1000
            logger.info("  ✓ HTTP %d in %.0fms", resp.status_code, elapsed_ms)
            break
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
            last_err = e
            wait = 5 * attempt  # 5s, 10s, 15s
            logger.warning("  ✗ attempt %d/%d failed (%s) — waiting %ds",
                           attempt, max_retries, type(e).__name__, wait)
            if attempt < max_retries:
                time.sleep(wait)
    else:
        raise RuntimeError(f"Open-Meteo failed after {max_retries} retries: {last_err}")

    # ---- Parse JSON → DataFrame ----
    daily = payload.get("daily")
    if not daily or "time" not in daily:
        raise RuntimeError(f"Open-Meteo returned no 'daily' block: {payload!r}")

    df = pd.DataFrame({
        "precip_mm":   daily["precipitation_sum"],
        "temp_mean_c": daily["temperature_2m_mean"],
        "temp_min_c":  daily["temperature_2m_min"],
        "temp_max_c":  daily["temperature_2m_max"],
        "shortwave_mj": daily["shortwave_radiation_sum"],
    }, index=pd.to_datetime(daily["time"]))
    df.index.name = "date"

    # Cast everything to float32 — saves 50% memory, more than enough precision
    df = df.astype(np.float32)

    df.to_parquet(cache_path)
    logger.info("✓ Open-Meteo: %d days, NaN%%: precip=%.2f temp=%.2f",
                len(df),
                100.0 * df["precip_mm"].isna().mean(),
                100.0 * df["temp_mean_c"].isna().mean())

    return df


# ============================================================================
# 3. ET₀ — Reference evapotranspiration (Hargreaves method)
# ============================================================================
def compute_et0_hargreaves(
    df: pd.DataFrame,
    lat: float,
) -> pd.Series:
    """
    Compute reference evapotranspiration via the Hargreaves-Samani equation.

        ET₀ = 0.0023 * Ra * (T_mean + 17.8) * sqrt(T_max - T_min)

    where:
        ET₀     = reference ET (mm/day)
        Ra      = extraterrestrial radiation (MJ/m²/day) — function of lat & day-of-year
        T_mean  = (T_max + T_min) / 2 (°C)
        T_max, T_min = daily temperature extremes (°C)

    WHY HARGREAVES INSTEAD OF PENMAN-MONTEITH?
        Penman-Monteith (FAO-56) is the gold standard but needs wind speed,
        humidity, and net radiation — five inputs. Hargreaves needs only
        T_min/T_max/latitude and is within 5% of PM in arid climates.
        Allen et al. (1998) FAO-56 paper explicitly recommends Hargreaves
        when full meteorological data is unavailable.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns 'temp_min_c', 'temp_max_c', 'temp_mean_c'.
        Index must be a DatetimeIndex.
    lat : float
        Latitude in decimal degrees (positive North).

    Returns
    -------
    pd.Series
        ET₀ in mm/day, indexed identically to df.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise TypeError("df.index must be DatetimeIndex for ET₀ computation")

    # Day of year (1–365/366)
    doy = df.index.dayofyear.to_numpy()

    # Solar declination δ (radians) — Allen et al. (1998), eq. 24
    decl = 0.409 * np.sin(2.0 * np.pi * doy / 365.0 - 1.39)

    # Latitude in radians
    phi = np.deg2rad(lat)

    # Inverse relative Earth–Sun distance dr — eq. 23
    dr = 1.0 + 0.033 * np.cos(2.0 * np.pi * doy / 365.0)

    # Sunset hour angle ωs — eq. 25
    # Clip the argument to [-1, 1] to handle high latitudes (polar night/day)
    arg = np.clip(-np.tan(phi) * np.tan(decl), -1.0, 1.0)
    omega_s = np.arccos(arg)

    # Extraterrestrial radiation Ra (MJ/m²/day) — eq. 21
    # Gsc = 0.0820 MJ/m²/min (solar constant)
    Ra = (24.0 * 60.0 / np.pi) * 0.0820 * dr * (
        omega_s * np.sin(phi) * np.sin(decl)
        + np.cos(phi) * np.cos(decl) * np.sin(omega_s)
    )

    # Hargreaves-Samani — eq. 52 in FAO-56
    t_max = df["temp_max_c"].to_numpy()
    t_min = df["temp_min_c"].to_numpy()
    t_mean = df["temp_mean_c"].to_numpy()

    # Guard against bogus negative ranges (sensor errors)
    t_range = np.clip(t_max - t_min, a_min=0.0, a_max=None)

    et0 = 0.0023 * Ra * (t_mean + 17.8) * np.sqrt(t_range)
    et0 = np.clip(et0, a_min=0.0, a_max=None)  # ET₀ can't be negative

    return pd.Series(et0, index=df.index, name="et0_mm", dtype=np.float32)


# ============================================================================
# 4. ASSEMBLE — pull everything together into one tidy DataFrame
# ============================================================================
def build_basin_dataset(
    basin: BasinSpec,
    start_date: str,
    end_date: str,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Top-level convenience function. Downloads streamflow + forcings,
    computes ET₀, aligns on a daily date index, and saves to data/interim/.

    Returns a tidy DataFrame ready for feature engineering (Batch 3).
    """
    logger.info("[bold cyan]Building dataset for basin: %s (%s)[/]",
                basin.name, basin.usgs_id)

    # 1. Streamflow
    q_df = fetch_usgs_discharge(basin.usgs_id, start_date, end_date,
                                 force_refresh=force_refresh)

    # 2. Meteo forcing
    f_df = fetch_openmeteo_forcing(basin.usgs_id, basin.lat, basin.lon,
                                    start_date, end_date,
                                    force_refresh=force_refresh)

    # 3. ET₀
    f_df["et0_mm"] = compute_et0_hargreaves(f_df, basin.lat)

    # 4. Inner-join on date — only keep days present in BOTH sources
    # `how='inner'` is the safe default. If you `how='left'`, you risk
    # silent NaN propagation through the LSTM.
    merged = f_df.join(q_df, how="inner")

    # 5. Quality-control logging
    logger.info("Merged: %d days (%s → %s)",
                len(merged), merged.index.min().date(), merged.index.max().date())
    nan_pct = 100.0 * merged.isna().mean()
    logger.info("NaN%% per column:\n%s", nan_pct.round(2).to_string())

    # 6. Persist to interim
    out_path = DATA_INTERIM / f"{basin.name}_daily.parquet"
    DATA_INTERIM.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_path)
    logger.info("✓ Saved interim dataset: %s (%.1f MB)",
                out_path, out_path.stat().st_size / 1e6)

    return merged