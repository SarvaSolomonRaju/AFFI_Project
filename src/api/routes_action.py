"""Action Panel — turns flood status data into named, actionable lists
for a flood manager, instead of just probabilities on a chart.

Scoped to TODAY's actual live forecast when available
(outputs/task4/today_feature_status.json, written fresh on every forecast
run by scripts/07_task4_probabilistic.py -- see
src/probabilistic/today_feature_status.py). Falls back to the static FEMA
100-yr reference tagging baked into data/local_assets/roads_huc12.geojson /
buildings_huc12.geojson (scripts/14_build_local_assets.py) only if that
file doesn't exist yet -- and says so plainly in reference_scenario rather
than presenting the fallback as if it were live data.
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
from common.building_categories import categorize_building

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


TODAY_STATUS_PATH = ROOT / "outputs" / "task4" / "today_feature_status.json"


def _load_geojson(name: str, today_key: str | None = None) -> dict:
    path = DATA_DIR / "local_assets" / name
    data = json.loads(path.read_text()) if path.exists() else {"features": []}
    if today_key is not None and TODAY_STATUS_PATH.exists():
        today_status = json.loads(TODAY_STATUS_PATH.read_text()).get(today_key, [])
        for feature, status in zip(data.get("features", []), today_status):
            props = feature["properties"]
            props["max_depth_m"] = status["max_depth_m"]
            props["status"] = status["status"]
    return data


def _clean_name(raw, fallback: str) -> str:
    # scripts/14_build_local_assets.py writes missing OSM tags as the
    # literal string "nan" (a pandas str(NaN) artifact) rather than
    # null — most buildings have no OSM name tag at all, so this hits
    # ~95% of flooded buildings. Falling back to street address when
    # available beats showing "nan" on an emergency manager's screen.
    if isinstance(raw, str) and raw and raw.lower() != "nan":
        return raw
    return fallback


def build_action_plan() -> dict:
    """Shared by GET /action-plan and the bulletin generator (routes_bulletin.py)
    so both read the same road/building lists — one source of truth."""
    roads = _load_geojson("roads_huc12.geojson", today_key="roads")
    buildings = _load_geojson("buildings_huc12.geojson", today_key="buildings")

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
                "category": categorize_building(f["properties"].get("building")),
            }
            for f in buildings.get("features", [])
            if f["properties"].get("status") == "FLOODED"
        ),
        key=lambda b: b["max_depth_m"],
        reverse=True,
    )

    # Schools called out separately, not just left buried wherever they
    # land in the depth-sorted list — a school with any water at all is
    # a higher evacuation priority than a deeper-flooded shed, but this
    # doesn't silently re-sort the main list (which stays depth-ranked,
    # already tested that way) — it adds a dedicated, always-complete
    # (not capped to 20) callout instead.
    schools_in_flood_zone = [b for b in flooded_buildings if b["category"] == "School"]

    reference_scenario = (
        "Today's live forecast" if TODAY_STATUS_PATH.exists()
        else "FEMA 1% annual chance (100-yr) flood (today's forecast unavailable)"
    )

    return {
        "reference_scenario": reference_scenario,
        "roads_to_barricade": {
            "total_count": len(flooded_roads),
            "top": flooded_roads[:20],
        },
        "buildings_to_evacuate": {
            "total_count": len(flooded_buildings),
            "top": flooded_buildings[:20],
        },
        "schools_in_flood_zone": schools_in_flood_zone,
        "legal_note": LEGAL_NOTE,
    }


@router.get("/action-plan")
async def get_action_plan(user: dict = Depends(validate_api_key)):
    return build_action_plan()
