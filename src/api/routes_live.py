"""Live sensor data — real-time USGS stream gauge telemetry.

The pilot watershed's own gauge (USGS 09481500, Sonoita Creek near
Patagonia) is NOT real-time telemetered — confirmed by querying
waterservices.usgs.gov/nwis/iv/ directly: zero instantaneous-value series
returned for any period. This is common for small ephemeral-wash gauges;
not every USGS station has cellular/satellite telemetry equipment.

The nearest REAL-TIME telemetered gauge in the same river system (same
HUC-8, 15050301) is USGS 09480500, Santa Cruz River near Nogales, AZ —
about 13 miles south/downstream of Patagonia. This route proxies that
gauge's live discharge + stage, clearly labeled as "nearest live gauge,"
never presented as if it were the pilot watershed's own reading.
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key

router = APIRouter(prefix="/api/v1", tags=["Live"])

# Pilot gauge (no live telemetry) vs. nearest telemetered gauge, same HUC-8.
PILOT_GAUGE = {"id": "09481500", "name": "Sonoita Creek near Patagonia, AZ", "lat": 31.5407, "lon": -110.7521}
NEAREST_LIVE_GAUGE = {"id": "09480500", "name": "Santa Cruz River near Nogales, AZ", "lat": 31.3446, "lon": -110.8515}

NWIS_IV_URL = "https://waterservices.usgs.gov/nwis/iv/"


@router.get("/live-gauge")
async def get_live_gauge(user: dict = Depends(validate_api_key)):
    """Real-time discharge + gage height from the nearest telemetered USGS
    gauge. No API key required (USGS NWIS is a free public service)."""
    params = {
        "sites": NEAREST_LIVE_GAUGE["id"],
        "parameterCd": "00060,00065",  # discharge (cfs), gage height (ft)
        "format": "json",
        "period": "P1D",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(NWIS_IV_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"USGS NWIS request failed: {e}")

    series = data.get("value", {}).get("timeSeries", [])
    readings = {}
    for s in series:
        var_code = s["variable"]["variableCode"][0]["value"]
        values = s["values"][0]["value"]
        if not values:
            continue
        latest = values[-1]
        key = "discharge_cfs" if var_code == "00060" else "gage_height_ft" if var_code == "00065" else var_code
        readings[key] = {
            "value": float(latest["value"]),
            "datetime": latest["dateTime"],
            "provisional": "P" in latest.get("qualifiers", []),
        }

    if not readings:
        raise HTTPException(status_code=404, detail="No live telemetry available from USGS right now.")

    return {
        "pilot_gauge": PILOT_GAUGE,
        "pilot_gauge_has_telemetry": False,
        "nearest_live_gauge": NEAREST_LIVE_GAUGE,
        "distance_note": "~13 miles downstream, same HUC-8 river system (15050301) — NOT the pilot watershed's own gauge",
        "readings": readings,
    }
