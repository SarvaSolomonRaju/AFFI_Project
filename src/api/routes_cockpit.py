"""Decision Cockpit — time-to-peak, life-safety threshold, uncertainty.

These three numbers were part of the original white paper's "Flood-
Control-Manager Decision Cockpit" (Task 4 deliverables D4.2.c/d/f) and
are already computed by the pipeline into
outputs/task4/forecast_7day.json['manager_products'] — but the React
dashboard never surfaced them. Passthrough, not new computation.
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

OUTPUTS_DIR = ROOT / "outputs"

router = APIRouter(prefix="/api/v1", tags=["Decision Cockpit"])


@router.get("/decision-cockpit")
async def get_decision_cockpit(user: dict = Depends(validate_api_key)):
    forecast_path = OUTPUTS_DIR / "task4" / "forecast_7day.json"
    if not forecast_path.exists():
        raise HTTPException(status_code=404, detail="Today's forecast not available.")

    forecast = json.loads(forecast_path.read_text())
    mp = forecast.get("manager_products", {})
    if not mp:
        raise HTTPException(status_code=404, detail="Manager products not available in today's forecast.")

    ttp = mp.get("time_to_peak_hours", {})

    return {
        "time_to_peak_hours": {
            "p10": ttp.get("p10_hours"),
            "p50": ttp.get("p50_hours"),
            "p90": ttp.get("p90_hours"),
            "method": ttp.get("method"),
        },
        "life_safety": {
            "prob_gt_0_5m_max_pct": round((mp.get("prob_gt_05m_max") or 0.0) * 100, 1),
            "wet_pixels_above_0_5m": mp.get("prob_gt_05m_wet_pixels", 0),
        },
        "uncertainty_m": {
            "max": mp.get("uncertainty_max_m"),
            "mean": mp.get("uncertainty_mean_m"),
        },
    }
