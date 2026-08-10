"""Official NWS alerts — the authoritative real-time source, shown alongside
our own forecast so a manager can see BOTH: what we predict, and what the
National Weather Service is actually warning right now.

This is the honest reality check. Our forecast is a model; NWS Flash Flood
Warnings are the legal, authoritative product people's phones get via
Wireless Emergency Alerts. Surfacing them here means the dashboard never
disagrees silently with the official word — and if NWS has a warning out
that our model missed (or vice-versa), the manager sees the mismatch.

Source: api.weather.gov (free, no key; a descriptive User-Agent is required
by NWS). Point = the pilot watershed pour point (Patagonia, AZ).
"""
from __future__ import annotations

import sys
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key

router = APIRouter(prefix="/api/v1", tags=["Official"])

# Pilot watershed pour point (Hwy 82 bridge, Patagonia AZ) — the same point
# the forecast is anchored to.
POINT = "31.5384,-110.7512"
NWS_ALERTS_URL = f"https://api.weather.gov/alerts/active?point={POINT}"
# NWS requires a descriptive User-Agent identifying the app + a contact.
NWS_HEADERS = {"User-Agent": "AFFI-FloodAI (Upper Sonoita Creek pilot; contact via dashboard operator)"}

# Events that mean water danger — surfaced as flood-relevant even though we
# show every active alert (heat, wind, etc. still display, just not flagged).
_FLOOD_EVENTS = {
    "Flash Flood Warning", "Flash Flood Watch", "Flood Warning",
    "Flood Watch", "Flood Advisory", "Hydrologic Outlook",
}


@router.get("/official-alerts")
async def get_official_alerts(user: dict = Depends(validate_api_key)):
    """Live NWS active alerts for the pilot point. Never fabricated — if NWS
    is unreachable, says so rather than implying 'all clear'."""
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=NWS_HEADERS) as client:
            resp = await client.get(NWS_ALERTS_URL)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as e:
        return {
            "available": False,
            "error": str(e),
            "source": "api.weather.gov",
            "alerts": [],
        }

    alerts = []
    for f in data.get("features", []):
        p = f.get("properties", {})
        event = p.get("event", "")
        alerts.append({
            "event": event,
            "severity": p.get("severity"),        # Extreme / Severe / Moderate / Minor
            "urgency": p.get("urgency"),           # Immediate / Expected / Future
            "certainty": p.get("certainty"),
            "headline": p.get("headline"),
            "area": p.get("areaDesc"),
            "effective": p.get("effective"),
            "expires": p.get("expires"),
            "sender": p.get("senderName"),
            "is_flood": event in _FLOOD_EVENTS,
        })

    # flood-relevant alerts first, then by NWS severity
    sev_rank = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3, "Unknown": 4}
    alerts.sort(key=lambda a: (not a["is_flood"], sev_rank.get(a.get("severity") or "Unknown", 4)))

    return {
        "available": True,
        "source": "National Weather Service (api.weather.gov)",
        "point": POINT,
        "count": len(alerts),
        "flood_alert_active": any(a["is_flood"] for a in alerts),
        "alerts": alerts,
    }
