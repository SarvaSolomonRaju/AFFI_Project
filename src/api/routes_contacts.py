"""On-call contact roster — who to actually call during an event.

Reads data/local_assets/infrastructure.geojson (scripts/15_build_infrastructure.py),
filtered to organizations a manager would call (shelters, hospital, fire,
police, water/wastewater utilities, public works) rather than passive
physical assets (power lines, bridges, cell towers) that aren't
call-able.

Real addresses throughout; phone is real where documented (currently just
the health center) and explicitly null otherwise -- never a fabricated
number. A phone number is the one piece of information where guessing
wrong has real consequences during an actual event, so "not on file" is
the honest answer until someone enters the real one from the frontend
roster panel (which persists it in the browser's own localStorage only --
this endpoint never receives or stores it).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, Depends

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key

DATA_DIR = ROOT / "data"

router = APIRouter(prefix="/api/v1", tags=["Contacts"])

# Categories worth calling during an event. Excludes power_line/water_line/
# sewer_line/bridge/cell_tower — real facilities on the map, but physical
# assets rather than organizations with a number to dial.
_CALLABLE_CATEGORIES = {
    "shelter", "hospital", "fire_station", "police",
    "water_supply", "wastewater", "power", "public_works",
    "government", "post_office", "mine",
}


@router.get("/contacts")
async def get_contact_roster(user: dict = Depends(validate_api_key)):
    path = DATA_DIR / "local_assets" / "infrastructure.geojson"
    if not path.exists():
        return {"contacts": []}

    data = json.loads(path.read_text())
    contacts = [
        {
            "name": p.get("name"),
            "category": p.get("category"),
            "category_label": p.get("category_label") or p.get("category"),
            "address": p.get("address"),
            "phone": p.get("phone"),
        }
        for p in (f["properties"] for f in data.get("features", []))
        if p.get("category") in _CALLABLE_CATEGORIES
    ]
    return {"contacts": contacts}
