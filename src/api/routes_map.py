"""Map layer and simulation-mode routes.

Serves the same GeoJSON/raster/scenario data that
src/dashboard/interactive_map.py and scripts/build_dashboard.py already
produce as files on disk — this module adds no new data generation
(scenarios excepted, see build_scenario_library), just HTTP access to
what's already there, behind the existing API-key auth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key
from common.building_categories import categorize_building

DATA_DIR = ROOT / "data"
OUTPUTS_DIR = ROOT / "outputs"

router = APIRouter(prefix="/api/v1", tags=["Map"])

# Reference markers — mirrors src/dashboard/interactive_map.py (USGS_GAUGE,
# PATAGONIA, HWY82). Duplicated as plain constants here rather than
# importing that module, which pulls in folium/matplotlib as a side effect
# of module import — unnecessary weight for a JSON config endpoint.
_REFERENCE_MARKERS = [
    {"lat": 31.5407, "lon": -110.7521, "label": "USGS 09481500 Sonoita Creek nr Patagonia"},
    {"lat": 31.5393, "lon": -110.7548, "label": "Patagonia, AZ"},
    {"lat": 31.5410, "lon": -110.7560, "label": "Hwy 82 Bridge over Sonoita Creek"},
]

_GEOJSON_LAYERS: dict[str, Path] = {
    "nfhl-zones": DATA_DIR / "fema_nfhl" / "nfhl_zones_huc12.geojson",
    "bfe-lines": DATA_DIR / "fema_fis" / "BFE_huc12.geojson",
    "creek-centerline": DATA_DIR / "fema_fis" / "WaterLn_huc12.geojson",
    "roads": DATA_DIR / "local_assets" / "roads_huc12.geojson",
    "buildings": DATA_DIR / "local_assets" / "buildings_huc12.geojson",
    "infrastructure": DATA_DIR / "local_assets" / "infrastructure.geojson",
}

_RASTER_LAYERS: dict[str, Path] = {
    "fema-100yr": OUTPUTS_DIR / "_map_layer_100yr_depth.png",
    "today-likely": OUTPUTS_DIR / "_map_layer_today_likely.png",
    "today-poi": OUTPUTS_DIR / "_map_layer_today_poi.png",
}


@router.get("/map/config")
async def get_map_config(user: dict = Depends(validate_api_key)):
    from config.settings import load_settings
    import json as _json

    s = load_settings()

    bounds_path = OUTPUTS_DIR / "_map_layer_bounds.json"
    raster_bounds = _json.loads(bounds_path.read_text()) if bounds_path.exists() else {}

    return {
        "bbox": {
            "north": s.watershed.bbox.north,
            "south": s.watershed.bbox.south,
            "east": s.watershed.bbox.east,
            "west": s.watershed.bbox.west,
        },
        "center": {"lat": s.watershed.pour_point.lat, "lon": s.watershed.pour_point.lon},
        "reference_markers": _REFERENCE_MARKERS,
        "base_tiles": [
            {"name": "OpenStreetMap", "url": None},
            {"name": "CartoDB Light", "url": None},
            {
                "name": "Esri Satellite",
                "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            },
            {
                "name": "Esri Topographic",
                "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
            },
        ],
        "available_layers": list(_GEOJSON_LAYERS.keys()),
        "available_rasters": list(_RASTER_LAYERS.keys()),
        "raster_bounds": raster_bounds,
    }


@router.get("/map/layers/{layer}")
async def get_map_layer(layer: str, user: dict = Depends(validate_api_key)):
    path = _GEOJSON_LAYERS.get(layer)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Unknown map layer: {layer}")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Layer file not found on disk: {path.name}")

    if layer == "buildings":
        # Only this layer gets a transform — everything else is a raw
        # passthrough (see module docstring). The raw OSM `building` tag
        # (school, house, industrial, ...) is already on disk but was
        # never grouped into anything a manager would scan at a glance;
        # inject a `category` property rather than have the frontend
        # duplicate this lookup in JS.
        data = json.loads(path.read_text())
        for feature in data.get("features", []):
            feature["properties"]["category"] = categorize_building(
                feature["properties"].get("building")
            )
        return JSONResponse(content=data, media_type="application/geo+json")

    return FileResponse(path, media_type="application/geo+json")


@router.get("/map/raster/{layer}")
async def get_map_raster(layer: str, user: dict = Depends(validate_api_key)):
    path = _RASTER_LAYERS.get(layer)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Unknown raster layer: {layer}")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Raster not yet generated: {path.name}")
    return FileResponse(path, media_type="image/png")


@router.get("/simulation/scenarios")
async def get_simulation_scenarios(user: dict = Depends(validate_api_key)):
    from probabilistic.scenarios import build_scenario_library

    library = build_scenario_library()
    if not library:
        raise HTTPException(status_code=404, detail="Flood map library not built yet.")
    return {
        "return_periods_yr": sorted(library.keys()),
        "scenarios": {
            str(T): {
                "Q_cms": entry["Q_cms"],
                "max_depth_m": entry["max_depth_m"],
                "wet_area_km2": entry["wet_area_km2"],
                "roads_at_risk": entry.get("roads_at_risk"),
                "infra_at_risk": entry.get("infra_at_risk"),
                "alert_level": entry.get("alert_level"),
                "severity": entry.get("severity"),
                "probability": entry.get("probability"),
                "raster_url": f"/api/v1/simulation/raster/{T}",
            }
            for T, entry in library.items()
        },
    }


@router.get("/simulation/raster/{return_period}")
async def get_simulation_raster(return_period: int, user: dict = Depends(validate_api_key)):
    path = OUTPUTS_DIR / "sim" / f"depth_T{return_period:03d}yr.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No simulation raster for T={return_period}yr")
    return FileResponse(path, media_type="image/png")
