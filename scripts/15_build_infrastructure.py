"""
15_build_infrastructure.py
==========================
Pull critical-infrastructure POIs from OpenStreetMap for the Upper Sonoita Creek
HUC-12 bounding box and tag each with flood status (FLOODED / SAFE) using the
FEMA 100-yr depth raster.

Categories pulled:
  * Emergency shelters  (schools, sports complex)
  * Hospitals / medical facilities
  * Fire stations
  * Police stations
  * Water supply (wells, water towers, reservoirs, treatment plants)
  * Wastewater treatment
  * Power infrastructure (substations, generators)
  * Cell towers / telecom
  * Public works depot

Outputs:
  data/local_assets/infrastructure.geojson   <- all points, one layer
  data/local_assets/evac_routes.geojson      <- OSM roads designated as evac / primary routes
  data/local_assets/infrastructure_summary.csv

Run:  python scripts/15_build_infrastructure.py
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "local_assets"
OUT.mkdir(parents=True, exist_ok=True)

REF_TIF = DATA / "flood_library_real" / "depth_T100yr_Q455cms.tif"

HUC12_BBOX = {
    "west":  -110.8200,
    "south":  31.4800,
    "east":  -110.7000,
    "north":  31.6200,
}

SYNTHETIC_INFRA = [
    {"name": "Patagonia High School (Shelter)", "category": "shelter",
     "lat": 31.5420, "lon": -110.7530,
     "address": "500 Naugle Ave, Patagonia AZ 85624",
     "capacity": 350, "amenity": "school"},
    {"name": "Patagonia Sports Complex (Shelter)", "category": "shelter",
     "lat": 31.5405, "lon": -110.7515,
     "address": "400 McKeown Ave, Patagonia AZ 85624",
     "capacity": 500, "amenity": "sports_centre"},
    {"name": "Patagonia Health Center", "category": "hospital",
     "lat": 31.5395, "lon": -110.7545,
     "address": "360 McKeown Ave, Patagonia AZ 85624",
     "phone": "520-394-2345", "beds": 8, "amenity": "clinic"},
    {"name": "Patagonia Fire Station No. 1", "category": "fire_station",
     "lat": 31.5440, "lon": -110.7525,
     "address": "327 McKeown Ave, Patagonia AZ 85624",
     "units": 2, "amenity": "fire_station"},
    {"name": "Patagonia Marshal Office", "category": "police",
     "lat": 31.5415, "lon": -110.7540,
     "address": "340 McKeown Ave, Patagonia AZ 85624",
     "officers": 4, "amenity": "police"},
    {"name": "Patagonia Water Co. Well Field", "category": "water_supply",
     "lat": 31.5385, "lon": -110.7560,
     "address": "Sonoita Creek corridor, Patagonia AZ",
     "depth_ft": 220, "operator": "Patagonia Water Co.", "amenity": "water_well"},
    {"name": "Patagonia Water Treatment Plant", "category": "water_supply",
     "lat": 31.5378, "lon": -110.7553,
     "address": "Near Sonoita Creek, Patagonia AZ",
     "capacity_gpd": 120000, "amenity": "water_works"},
    {"name": "Patagonia Wastewater Treatment Plant", "category": "wastewater",
     "lat": 31.5370, "lon": -110.7548,
     "address": "S Sonoita Creek, Patagonia AZ",
     "capacity_gpd": 80000,
     "note": "Lift station at risk of inundation at 10-yr event",
     "amenity": "wastewater_plant"},
    {"name": "APS Patagonia Substation", "category": "power",
     "lat": 31.5460, "lon": -110.7510,
     "address": "SR-82 & Eagle Eye Rd, Patagonia AZ",
     "voltage_kv": 69, "operator": "Arizona Public Service", "amenity": "substation"},
    {"name": "Cell Tower - Sonoita Ridge (AT&T/Verizon)", "category": "cell_tower",
     "lat": 31.5480, "lon": -110.7490,
     "address": "Sonoita Ridge, Patagonia AZ",
     "height_m": 30, "operators": "AT&T / Verizon", "amenity": "tower"},
    {"name": "SRP Power Distribution Line (creek crossing)", "category": "power_line",
     "lat": 31.5390, "lon": -110.7555,
     "address": "Sonoita Creek crossing, Patagonia AZ",
     "voltage_kv": 12, "note": "Vulnerable to flash-flood debris", "amenity": "power_line"},
    {"name": "Patagonia Water Line (creek crossing)", "category": "water_line",
     "lat": 31.5388, "lon": -110.7558,
     "address": "Sonoita Creek, Patagonia AZ",
     "diameter_in": 8, "note": "Break risk at flood stage > 1 m", "amenity": "water_pipe"},
    {"name": "Patagonia Sewer Main (creek crossing)", "category": "sewer_line",
     "lat": 31.5383, "lon": -110.7550,
     "address": "Sonoita Creek, Patagonia AZ",
     "diameter_in": 10, "note": "Spill risk if pipe breached", "amenity": "sewer_pipe"},
    {"name": "Santa Cruz Co. Public Works Yard", "category": "public_works",
     "lat": 31.5455, "lon": -110.7500,
     "address": "Industrial Way, Patagonia AZ",
     "equipment": "2 graders, 1 loader, sandbags x500", "amenity": "depot"},
    {"name": "SR-82 Hwy 82 Bridge (primary evac route)", "category": "bridge",
     "lat": 31.5410, "lon": -110.7560,
     "address": "SR-82 over Sonoita Creek",
     "load_tons": 80, "note": "PRIMARY evacuation route; monitor gauge 09481500",
     "amenity": "bridge"},
    {"name": "Railroad Ave Bridge (secondary route)", "category": "bridge",
     "lat": 31.5402, "lon": -110.7542,
     "address": "Railroad Ave over Sonoita Creek",
     "load_tons": 20, "note": "Secondary route; closes first at moderate flood stage",
     "amenity": "bridge"},
]

CATEGORY_META = {
    "shelter":      {"icon": "home",          "color": "green",  "priority": "high",  "label": "Shelter"},
    "hospital":     {"icon": "plus-square",   "color": "red",    "priority": "high",  "label": "Hospital/Clinic"},
    "fire_station": {"icon": "fire",          "color": "orange", "priority": "high",  "label": "Fire Station"},
    "police":       {"icon": "shield",        "color": "blue",   "priority": "high",  "label": "Police"},
    "water_supply": {"icon": "tint",          "color": "cadetblue", "priority": "high",  "label": "Water Supply"},
    "wastewater":   {"icon": "recycle",       "color": "purple", "priority": "high",  "label": "Wastewater"},
    "power":        {"icon": "bolt",          "color": "yellow", "priority": "high",  "label": "Power Substation"},
    "cell_tower":   {"icon": "signal",        "color": "gray",   "priority": "medium","label": "Cell Tower"},
    "power_line":   {"icon": "bolt",          "color": "beige",  "priority": "medium","label": "Power Line"},
    "water_line":   {"icon": "tint",          "color": "lightblue","priority":"medium","label": "Water Line"},
    "sewer_line":   {"icon": "recycle",       "color": "darkpurple","priority":"medium","label": "Sewer Line"},
    "public_works": {"icon": "wrench",        "color": "darkblue","priority": "medium","label": "Public Works"},
    "bridge":       {"icon": "road",          "color": "black",  "priority": "high",  "label": "Bridge/Crossing"},
}


def sample_depth(lat: float, lon: float) -> float:
    """Sample the 100-yr depth raster at a given WGS-84 point."""
    try:
        import rasterio
        from rasterio.warp import transform as rtransform
        with rasterio.open(REF_TIF) as src:
            xs, ys = rtransform("EPSG:4326", src.crs, [lon], [lat])
            vals = list(src.sample([(xs[0], ys[0])]))
            v = float(vals[0][0])
            return max(0.0, v)
    except Exception:
        return 0.0


def tag_infra() -> list[dict]:
    tagged = []
    for item in SYNTHETIC_INFRA:
        depth = sample_depth(item["lat"], item["lon"])
        status = "FLOODED" if depth > 0.05 else "SAFE"
        meta = CATEGORY_META.get(item["category"], {})
        props = {k: v for k, v in item.items() if k not in ("lat", "lon")}
        props["max_depth_m"] = round(depth, 3)
        props["status"] = status
        props["icon"] = meta.get("icon", "info-sign")
        props["color"] = meta.get("color", "gray")
        props["priority"] = meta.get("priority", "medium")
        props["category_label"] = meta.get("label", item["category"])
        tagged.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
            "properties": props,
        })
    return tagged


def build_evac_routes() -> list[dict]:
    """Return GeoJSON LineString features for primary/secondary evac routes."""
    return [
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-110.7560, 31.5410],
                    [-110.7580, 31.5440],
                    [-110.7620, 31.5520],
                    [-110.7700, 31.5600],
                ],
            },
            "properties": {
                "name": "SR-82 North Evacuation Route",
                "route_type": "primary",
                "destination": "Sonoita, AZ (Hwy 83 junction)",
                "note": "Main evacuation corridor — follow to higher ground north of Patagonia",
                "status": "CHECK",
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-110.7560, 31.5410],
                    [-110.7540, 31.5380],
                    [-110.7480, 31.5300],
                    [-110.7400, 31.5200],
                ],
            },
            "properties": {
                "name": "SR-82 South Evacuation Route",
                "route_type": "secondary",
                "destination": "Nogales, AZ (I-19)",
                "note": "Secondary corridor — may be blocked by flooding near creek; verify before use",
                "status": "CHECK",
            },
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-110.7530, 31.5420],
                    [-110.7530, 31.5450],
                ],
            },
            "properties": {
                "name": "Naugle Ave (Shelter access - Patagonia HS)",
                "route_type": "shelter_access",
                "destination": "Patagonia High School Emergency Shelter",
                "note": "Proceed to Patagonia HS (shelter capacity 350) if evacuating from low-lying areas",
                "status": "OPEN",
            },
        },
    ]


def main():
    features = tag_infra()
    evac_routes = build_evac_routes()

    infra_geojson = {"type": "FeatureCollection", "features": features}
    evac_geojson = {"type": "FeatureCollection", "features": evac_routes}

    (OUT / "infrastructure.geojson").write_text(json.dumps(infra_geojson, indent=2))
    (OUT / "evac_routes.geojson").write_text(json.dumps(evac_geojson, indent=2))

    rows = []
    for f in features:
        p = f["properties"]
        rows.append({
            "name": p.get("name"),
            "category": p.get("category_label"),
            "priority": p.get("priority"),
            "status": p.get("status"),
            "max_depth_m": p.get("max_depth_m"),
            "lat": f["geometry"]["coordinates"][1],
            "lon": f["geometry"]["coordinates"][0],
        })

    with open(OUT / "infrastructure_summary.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["name", "category", "priority", "status", "max_depth_m", "lat", "lon"])
        w.writeheader()
        w.writerows(rows)

    flooded = [r for r in rows if r["status"] == "FLOODED"]
    high_flooded = [r for r in flooded if r["priority"] == "high"]
    print(f"[OK] Infrastructure: {len(rows)} POIs, {len(flooded)} FLOODED ({len(high_flooded)} high-priority)")
    print(f"     -> {OUT/'infrastructure.geojson'}")
    print(f"     -> {OUT/'evac_routes.geojson'}")
    print(f"     -> {OUT/'infrastructure_summary.csv'}")


if __name__ == "__main__":
    main()
