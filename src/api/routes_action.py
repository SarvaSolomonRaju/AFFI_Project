"""Action Panel — turns flood status data into named, actionable lists
for a flood manager, instead of just probabilities on a chart.

Scoped to the FEMA 100-yr reference flood (the extent
data/local_assets/roads_huc12.geojson and buildings_huc12.geojson are
tagged against — see scripts/14_build_local_assets.py). This is NOT
the same as "today's live forecast" — there is no road/building-level
intersection against today's forecast raster yet. Labeled honestly in
the response rather than presented as more precise than it is.
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

router = APIRouter(prefix="/api/v1", tags=["Action Plan"])

# Arizona Revised Statutes 28-910 — driving around a barricade into a
# flooded road shifts rescue-cost liability to the motorist. Once a
# road is barricaded, that's the legal basis; source cited so a
# manager can verify it, not just trust a dashboard's word for it.
LEGAL_NOTE = (
    "Arizona Revised Statutes 28-910 (\"Stupid Motorist Law\"): once a road "
    "is barricaded/signed as flooded, a motorist who drives around the "
    "barricade and requires rescue may be billed for the rescue cost, plus "
    "liability up to $2,000. Barricading a road is what establishes this "
    "legal basis — an un-barricaded flooded road does not."
)


def _load_geojson(name: str) -> dict:
    path = DATA_DIR / "local_assets" / name
    return json.loads(path.read_text()) if path.exists() else {"features": []}


def _clean_name(raw, fallback: str) -> str:
    # scripts/14_build_local_assets.py writes missing OSM tags as the
    # literal string "nan" (a pandas str(NaN) artifact) rather than
    # null — most buildings have no OSM name tag at all, so this hits
    # ~95% of flooded buildings. Falling back to street address when
    # available beats showing "nan" on an emergency manager's screen.
    if isinstance(raw, str) and raw and raw.lower() != "nan":
        return raw
    return fallback


@router.get("/action-plan")
async def get_action_plan(user: dict = Depends(validate_api_key)):
    roads = _load_geojson("roads_huc12.geojson")
    buildings = _load_geojson("buildings_huc12.geojson")

    flooded_roads = sorted(
        (
            {
                "name": _clean_name(f["properties"].get("name"), "Unnamed road"),
                "max_depth_m": round(f["properties"].get("max_depth_m", 0.0), 2),
            }
            for f in roads.get("features", [])
            if f["properties"].get("status") == "FLOODED"
        ),
        key=lambda r: r["max_depth_m"],
        reverse=True,
    )

    def _building_name(props: dict) -> str:
        name = _clean_name(props.get("name"), "")
        if name:
            return name
        street = _clean_name(props.get("addr:street"), "")
        number = _clean_name(props.get("addr:housenumber"), "")
        if street and number:
            return f"{number} {street}"
        if street:
            return street
        return "Unnamed building"

    flooded_buildings = sorted(
        (
            {
                "name": _building_name(f["properties"]),
                "max_depth_m": round(f["properties"].get("max_depth_m", 0.0), 2),
            }
            for f in buildings.get("features", [])
            if f["properties"].get("status") == "FLOODED"
        ),
        key=lambda b: b["max_depth_m"],
        reverse=True,
    )

    return {
        "reference_scenario": "FEMA 1% annual chance (100-yr) flood",
        "roads_to_barricade": {
            "total_count": len(flooded_roads),
            "top": flooded_roads[:20],
        },
        "buildings_to_evacuate": {
            "total_count": len(flooded_buildings),
            "top": flooded_buildings[:20],
        },
        "legal_note": LEGAL_NOTE,
    }
