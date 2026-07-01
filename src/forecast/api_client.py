"""
api_client.py — Weather API Client with Retry Logic
=====================================================
WHAT THIS DOES:
    Fetches ensemble rainfall forecasts from Open-Meteo's GFS API.
    If the API fails, it retries up to 3 times with increasing delays.
    If all retries fail, it falls back to synthetic data.

WHY RETRY LOGIC?
    APIs fail. The internet is unreliable. Servers go down.
    Without retry logic, ONE failed API call crashes your entire
    forecast pipeline. With retry logic:

    Attempt 1: Failed (server busy)     → wait 5 seconds
    Attempt 2: Failed (timeout)         → wait 10 seconds  
    Attempt 3: Success!                 → continue normally

    This is called "exponential backoff" — each retry waits
    longer than the last. It's how Google, Netflix, and every
    professional system handles API failures.

WHAT IS AN "ENSEMBLE"?
    Weather models are run multiple times with slightly different
    starting conditions. Each run is called a "member."
    GFS has 31 members. Each member predicts different rainfall.

    Why? Because weather is chaotic. Tiny differences in initial
    temperature/pressure → very different forecasts 5 days later.

    31 members gives you a PROBABILITY DISTRIBUTION:
    - "20 out of 31 members predict >1 inch" = 65% probability
    - Much more useful than a single "it will rain 1.2 inches"
"""

import time
import numpy as np
import pandas as pd
import requests
from datetime import datetime
from typing import Optional, Dict, Any

from common.logging_setup import get_logger

logger = get_logger(__name__)


class EnsembleForecastClient:
    """
    Fetches ensemble precipitation forecasts from Open-Meteo API.

    HOW TO USE:
        client = EnsembleForecastClient()
        df = client.fetch(lat=31.66, lon=-110.70)
        # df has 168 rows (7 days × 24 hours) and 31 columns (members)
    """

    def __init__(self, 
                 base_url: str = "https://ensemble-api.open-meteo.com/v1/ensemble",
                 model: str = "gfs_seamless",
                 forecast_days: int = 7,
                 timeout: int = 30,
                 max_retries: int = 3,
                 retry_delay: int = 5,
                 timezone: str = "America/Phoenix"):
        """
        Initialize the API client.

        All these values come from config/settings.py.
        You never hardcode them here — they're passed in.
        """
        self.base_url = base_url
        self.model = model
        self.forecast_days = forecast_days
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timezone = timezone

        # Track API call statistics
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.synthetic_fallbacks = 0

    def fetch(self, lat: float, lon: float, 
              point_id: str = "unknown") -> tuple:
        """
        Fetch ensemble forecast for one grid point.

        Parameters
        ----------
        lat : float
            Latitude of the grid point
        lon : float
            Longitude of the grid point
        point_id : str
            ID like "P1", "P2" — for logging

        Returns
        -------
        tuple of (pd.DataFrame, str)
            - DataFrame: rows=hours, columns=ensemble members
              Values are precipitation in mm/hour
            - str: "api" if real data, "synthetic" if fallback

        THE RETRY LOOP EXPLAINED:
            for attempt in range(1, max_retries + 1):
                try:
                    call API
                    if success: return data
                except:
                    if last attempt: give up, use synthetic
                    else: wait and try again
        """
        self.total_calls += 1

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "precipitation",
            "models": self.model,
            "forecast_days": self.forecast_days,
            "timezone": self.timezone
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("API call %s (%.4f, %.4f) — attempt %d/%d",
                           point_id, lat, lon, attempt, self.max_retries)

                start_time = time.time()
                response = requests.get(
                    self.base_url, 
                    params=params, 
                    timeout=self.timeout
                )
                elapsed_ms = (time.time() - start_time) * 1000

                # HTTP status check
                # 200 = OK, 429 = rate limited, 500 = server error
                response.raise_for_status()

                data = response.json()

                # Parse the response into a DataFrame
                df = self._parse_response(data)

                if df is not None and not df.empty:
                    self.successful_calls += 1
                    logger.info("  ✓ %s: %d members, %d hours (%.0fms)",
                               point_id, df.shape[1], df.shape[0], elapsed_ms)
                    return df, "api"
                else:
                    logger.warning("  ✗ %s: API returned empty data", point_id)

            except requests.exceptions.Timeout:
                logger.warning("  ✗ %s: Timeout after %ds (attempt %d)",
                              point_id, self.timeout, attempt)
            except requests.exceptions.HTTPError as e:
                logger.warning("  ✗ %s: HTTP error %s (attempt %d)",
                              point_id, e, attempt)
            except requests.exceptions.ConnectionError:
                logger.warning("  ✗ %s: Connection failed (attempt %d)",
                              point_id, attempt)
            except Exception as e:
                logger.error("  ✗ %s: Unexpected error: %s (attempt %d)",
                            point_id, e, attempt)

            # Wait before retrying (exponential backoff)
            if attempt < self.max_retries:
                wait = self.retry_delay * attempt  # 5s, 10s, 15s
                logger.info("  Waiting %ds before retry...", wait)
                time.sleep(wait)

        # All retries failed — fall back to synthetic data
        self.failed_calls += 1
        self.synthetic_fallbacks += 1
        logger.warning("  ⚠ %s: All %d attempts failed — using synthetic data",
                       point_id, self.max_retries)
        return self._make_synthetic(), "synthetic"

    def _parse_response(self, data: Dict[str, Any]) -> Optional[pd.DataFrame]:
        """
        Parse Open-Meteo JSON response into a DataFrame.

        THE API RETURNS:
        {
            "hourly": {
                "time": ["2026-04-07T00:00", "2026-04-07T01:00", ...],
                "precipitation_member01": [0.0, 0.1, ...],
                "precipitation_member02": [0.0, 0.3, ...],
                ...
            }
        }

        WE CONVERT TO:
            DataFrame with:
            - Index = datetime (2026-04-07 00:00, 01:00, ...)
            - Columns = member_00, member_01, ..., member_30
            - Values = precipitation in mm/hour
        """
        if "hourly" not in data:
            return None

        hourly = data["hourly"]
        times = pd.to_datetime(hourly.get("time", []))

        if len(times) == 0:
            return None

        # Find all precipitation member columns
        members = {}
        for key, values in hourly.items():
            if key.startswith("precipitation_member"):
                members[key] = values

        if not members:
            # Some API responses use different naming
            for key, values in hourly.items():
                if key.startswith("precipitation") and key != "time":
                    members[key] = values

        if not members:
            return None

        df = pd.DataFrame(members, index=times)
        # Standardize column names
        df.columns = [f"member_{i:02d}" for i in range(len(df.columns))]

        return df

    def _make_synthetic(self, n_hours: int = 168, 
                        n_members: int = 31) -> pd.DataFrame:
        """
        Generate synthetic monsoon-like ensemble data.

        WHEN IS THIS USED?
            Only when the API fails completely (all retries exhausted).
            The synthetic data mimics Arizona monsoon patterns:
            - Mostly dry hours
            - Occasional intense convective bursts (2-8 hours)
            - Random intensity (exponential distribution)

        WHY EXPONENTIAL DISTRIBUTION?
            Real rainfall intensity follows an exponential-like
            distribution: many light events, few heavy events.
            This is well-documented in hydrology literature.

        WARNING:
            Synthetic data is for TESTING ONLY.
            The alert packet will be flagged as data_source="synthetic"
            so you know not to trust it for real decisions.
        """
        logger.warning("Generating synthetic ensemble data "
                       "(%d hours, %d members)", n_hours, n_members)

        # Use current time as seed for reproducibility within a run
        # but different between runs
        rng = np.random.RandomState(int(datetime.now().timestamp()) % 2**31)

        times = pd.date_range(
            datetime.now().replace(minute=0, second=0, microsecond=0),
            periods=n_hours, freq="h"
        )

        data = {}
        for m in range(n_members):
            rain = np.zeros(n_hours)
            # Each member gets 2-6 random convective bursts
            n_bursts = rng.randint(2, 7)
            for _ in range(n_bursts):
                start = rng.randint(0, max(1, n_hours - 8))
                duration = rng.randint(1, 9)
                intensity = rng.exponential(0.3)
                end = min(start + duration, n_hours)
                rain[start:end] += intensity * rng.exponential(1.0, end - start)
            data[f"member_{m:02d}"] = rain

        return pd.DataFrame(data, index=times)

    def get_stats(self) -> Dict[str, int]:
        """Return API call statistics."""
        return {
            "total_calls": self.total_calls,
            "successful": self.successful_calls,
            "failed": self.failed_calls,
            "synthetic_fallbacks": self.synthetic_fallbacks,
            "success_rate_pct": round(
                self.successful_calls / max(1, self.total_calls) * 100, 1
            )
        }
