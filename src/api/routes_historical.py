"""Historical event comparison — "today looks like [past event]" context.

Flood managers trust a forecast more when it's anchored to something
they remember living through. Compares today's forecast discharge
against data/historical_events/sonoita_events.json (4 documented real
events, USGS-gauge-sourced) and returns the closest match by peak Q.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key

DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT / "outputs"

router = APIRouter(prefix="/api/v1", tags=["Historical"])


@router.get("/historical-comparison")
async def get_historical_comparison(user: dict = Depends(validate_api_key)):
    events_path = DATA_DIR / "historical_events" / "sonoita_events.json"
    forecast_path = OUTPUTS_DIR / "task4" / "forecast_7day.json"

    if not events_path.exists() or not forecast_path.exists():
        raise HTTPException(status_code=404, detail="Historical events or today's forecast not available.")

    events_data = json.loads(events_path.read_text())
    forecast = json.loads(forecast_path.read_text())

    today_q = forecast.get("today", {}).get("discharge_cms", {}).get("p50", 0.0)
    events = events_data.get("events", [])
    if not events:
        raise HTTPException(status_code=404, detail="No historical events in catalog.")

    closest = min(events, key=lambda e: abs(e["peak_q_cms"] - today_q))
    # On a dry/no-flow day (today_q == 0), a "% vs closest event" number
    # is always -100% regardless of which event is closest — technically
    # correct but reads as a meaningless comparison. Omit it and let the
    # frontend show a "no flow forecasted" framing instead.
    delta_pct = (
        None
        if today_q == 0 or closest["peak_q_cms"] == 0
        else round(100 * (today_q - closest["peak_q_cms"]) / closest["peak_q_cms"], 1)
    )

    return {
        "today_discharge_cms": round(today_q, 1),
        "closest_event": closest,
        "delta_pct_vs_closest_event": delta_pct,
        "catalog_size": len(events),
        "catalog_source": events_data.get("notes", ""),
    }
