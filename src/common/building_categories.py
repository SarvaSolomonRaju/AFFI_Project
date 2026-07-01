"""Maps OSM `building` tag values to manager-relevant categories.

data/local_assets/buildings_huc12.geojson already carries the raw OSM
`building` tag (school, house, industrial, church, shed, ...) — it was
downloaded but never grouped into anything a flood manager would scan
at a glance. No new data acquisition needed; this is a pure lookup
over what's already on disk.

Category priorities, roughly evacuation-urgency ordered:
  School                  - children present, highest evacuation priority
  Public/Civic            - assembly points, potential shelters
  Residential             - private homes, standard evacuation
  Commercial/Industrial   - business hours occupancy varies
  Agricultural/Outbuilding - usually unoccupied (sheds, barns, etc.)
  Unclassified            - OSM tag is just "yes"/"roof" or missing;
                            honest label, not a guess
"""
from __future__ import annotations

_SCHOOL = {"school"}
_PUBLIC_CIVIC = {"church", "civic", "public", "government", "fire_station", "hospital", "chapel", "cathedral", "mosque", "synagogue", "temple"}
_RESIDENTIAL = {"house", "residential", "detached", "semidetached_house", "terrace", "apartments", "cabin", "static_caravan", "ger", "bungalow", "dormitory"}
_COMMERCIAL_INDUSTRIAL = {"industrial", "retail", "commercial", "warehouse", "office", "supermarket", "kiosk"}
_AGRICULTURAL_OUTBUILDING = {"shed", "barn", "stable", "greenhouse", "farm_auxiliary", "carport", "roof", "ruins", "garage", "garages", "hut", "farm"}

_LOOKUP: dict[str, str] = {}
for _tag in _SCHOOL:
    _LOOKUP[_tag] = "School"
for _tag in _PUBLIC_CIVIC:
    _LOOKUP[_tag] = "Public/Civic"
for _tag in _RESIDENTIAL:
    _LOOKUP[_tag] = "Residential"
for _tag in _COMMERCIAL_INDUSTRIAL:
    _LOOKUP[_tag] = "Commercial/Industrial"
for _tag in _AGRICULTURAL_OUTBUILDING:
    _LOOKUP[_tag] = "Agricultural/Outbuilding"


def categorize_building(building_tag: str | None) -> str:
    """building_tag is the raw OSM `building=*` value (e.g. "school",
    "yes", "house"). Returns one of the categories above, or
    "Unclassified" for a generic/missing tag rather than guessing."""
    if not building_tag or not isinstance(building_tag, str):
        return "Unclassified"
    return _LOOKUP.get(building_tag.lower(), "Unclassified")
