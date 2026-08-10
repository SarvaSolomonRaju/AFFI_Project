"""Regional live-sensor network — every real-time USGS gauge around the
watershed, not just the single nearest one.

A manager taking direction during a monsoon wants the whole regional picture:
which creeks upstream are already flowing, where rain is falling, how the
Santa Cruz mainstem is responding. All of it is public real-time USGS data;
this pulls every active sensor in a bounding box around Patagonia in one
call, so the dashboard shows the live regional network instead of one point.

Source: USGS NWIS Instantaneous Values (waterservices.usgs.gov) — free, no
key. Never fabricated: an unreachable USGS returns an explicit error.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key

router = APIRouter(prefix="/api/v1", tags=["Sensors"])

NWIS_IV_URL = "https://waterservices.usgs.gov/nwis/iv/"
# Bounding box around Patagonia / upper Santa Cruz basin (west,south,east,north).
BBOX = "-111.1,31.2,-110.4,31.9"
# Patagonia pour point, for distance-from-town sorting.
PATAGONIA = (31.5384, -110.7512)

_PARAM_NAME = {"00060": "discharge_cfs", "00065": "gage_height_ft", "00045": "precip_in"}


def _haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


@router.get("/regional-sensors")
async def get_regional_sensors(user: dict = Depends(validate_api_key)):
    params = {
        "format": "json",
        "bBox": BBOX,
        "parameterCd": "00060,00065,00045",  # discharge, gage height, precip
        "siteStatus": "active",
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(NWIS_IV_URL, params=params, headers={"User-Agent": "AFFI-FloodAI"})
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        return {"available": False, "error": str(e), "source": "USGS NWIS", "sensors": []}

    sensors: dict[str, dict] = {}
    for s in data.get("value", {}).get("timeSeries", []):
        si = s["sourceInfo"]
        sid = si["siteCode"][0]["value"]
        code = s["variable"]["variableCode"][0]["value"]
        key = _PARAM_NAME.get(code)
        if key is None:
            continue
        vals = s["values"][0]["value"]
        if not vals:
            continue
        latest = vals[-1]
        try:
            value = float(latest["value"])
        except (TypeError, ValueError):
            continue
        geo = si["geoLocation"]["geogLocation"]
        lat, lon = float(geo["latitude"]), float(geo["longitude"])
        entry = sensors.setdefault(sid, {
            "id": sid, "name": si["siteName"].title(),
            "lat": lat, "lon": lon,
            "distance_mi": round(_haversine_mi(*PATAGONIA, lat, lon), 1),
            "readings": {}, "datetime": latest.get("dateTime"),
        })
        entry["readings"][key] = value

    result = list(sensors.values())
    # flowing = discharge > 0 or precip > 0 right now; surface those first
    def _active(e: dict) -> bool:
        r = e["readings"]
        return (r.get("discharge_cfs", 0) or 0) > 0 or (r.get("precip_in", 0) or 0) > 0
    for e in result:
        e["is_flowing"] = _active(e)
    result.sort(key=lambda e: (not e["is_flowing"], e["distance_mi"]))

    return {
        "available": True,
        "source": "USGS NWIS Instantaneous Values (waterservices.usgs.gov)",
        "count": len(result),
        "any_flowing": any(e["is_flowing"] for e in result),
        "sensors": result,
    }
