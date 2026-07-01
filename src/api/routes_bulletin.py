"""NWS-style bulletin generator.

Real flood warnings use a WHAT/WHERE/WHEN/IMPACTS bulleted format
(NOAA's 2021 move to "impact-based" flash flood warnings) — flood
managers already know how to read and relay this format over radio/PA.
Composes one from data this project already produces: the alert
packet (src/api/server.py) and the Action Panel (routes_action.py).
No new data, just a different rendering of what's already computed.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key
from src.api.routes_action import build_action_plan

router = APIRouter(prefix="/api/v1", tags=["Bulletin"])

# NWS action language per category — mirrors the real definitions:
# minor = "minimal/no property damage, possible public threat";
# moderate = "some inundation, some evacuation... necessary";
# major = "extensive inundation... significant evacuations necessary".
# (https://forecast.weather.gov/glossary.php?word=flood+categories)
_ACTION_BY_LEVEL = {
    "GREEN": "Monitor conditions. No public action required.",
    "ADVISORY": "Pre-stage sandbags and pumps at known trouble spots. Monitor forecast for escalation.",
    "WATCH": "Barricade the low-water crossings listed below. Notify nearby schools and residents in the affected area.",
    "WARNING": "Evacuate the buildings listed below. Activate EOC. Barricade all listed roads. Issue public warning via all available channels.",
}


def _compose_text(packet: dict, plan: dict) -> str:
    level = packet.get("current_alert", "GREEN")
    watershed = packet.get("watershed", {}) or {}
    watershed_name = watershed.get("name", "Upper Sonoita Creek")
    # Not labeled "HUC-12" — this field (from config/settings.py, via
    # the Task 1/2 alert packet) is documented to sometimes hold the
    # HUC-8 code (510 km^2) rather than the HUC-12 pilot watershed code
    # (150503010204, 143.6 km^2) that Task 3-5's real flood library
    # actually uses. See _archive/status_docs_2026-06/
    # HONEST_ASSESSMENT_AND_REAL_DATA_PLAN.md for the known divergence.
    # Printing whatever's actually there rather than asserting a tier.
    huc = watershed.get("huc", "unknown")

    road_names = [r["name"] for r in plan["roads_to_barricade"]["top"][:10]]
    building_names = [b["name"] for b in plan["buildings_to_evacuate"]["top"][:10]]

    lines = [
        f"FLOOD {level} — {watershed_name.upper()} WATERSHED (HUC {huc})",
        f"Issued: {packet.get('generated_utc', 'unknown')}",
        f"Source: FloodAI / USGS 09481500 / FEMA NFHL",
        "",
        f"* WHAT: {level.title()}-level flood conditions per FEMA/USGS-derived forecast.",
        f"* WHERE: {watershed_name}, HUC {huc}.",
        f"* WHEN: Next 24 hours, per current forecast (see 7-day outlook for trend).",
        f"* IMPACTS: {plan['roads_to_barricade']['total_count']} roads and "
        f"{plan['buildings_to_evacuate']['total_count']} buildings at risk at the "
        f"{plan['reference_scenario']} — see road/building list below.",
        f"* ACTION: {_ACTION_BY_LEVEL.get(level, _ACTION_BY_LEVEL['GREEN'])}",
    ]

    if level in ("WATCH", "WARNING") and road_names:
        lines.append("")
        lines.append("ROADS TO BARRICADE (top 10 by depth):")
        lines += [f"  - {name}" for name in road_names]

    if level == "WARNING" and building_names:
        lines.append("")
        lines.append("BUILDINGS TO EVACUATE (top 10 by depth):")
        lines += [f"  - {name}" for name in building_names]

    lines.append("")
    lines.append(plan["legal_note"])

    return "\n".join(lines)


@router.get("/bulletin")
async def get_bulletin(user: dict = Depends(validate_api_key)):
    from src.api.server import _load_latest_alert_packet

    packet = _load_latest_alert_packet()
    if packet is None:
        raise HTTPException(status_code=404, detail="No forecast data available.")

    plan = build_action_plan()
    text = _compose_text(packet, plan)
    return {"alert_level": packet.get("current_alert", "GREEN"), "text": text}
