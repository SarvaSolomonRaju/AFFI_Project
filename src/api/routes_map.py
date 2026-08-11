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

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key
from common.building_categories import categorize_building
from src.probabilistic.today_feature_status import severity_tier

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
    # Built by scripts/15_build_infrastructure.py alongside infrastructure.geojson
    # but never registered here, so the map never had a way to serve it.
    "evac-routes": DATA_DIR / "local_assets" / "evac_routes.geojson",
}

_RASTER_LAYERS: dict[str, Path] = {
    "fema-100yr": OUTPUTS_DIR / "_map_layer_100yr_depth.png",
    "today-likely": OUTPUTS_DIR / "_map_layer_today_likely.png",
    "today-poi": OUTPUTS_DIR / "_map_layer_today_poi.png",
    # WorldPop 2020 1km population density, clipped to the HUC-12 bbox by
    # scripts/17_build_population_layer.py — real gridded population counts,
    # free/no-key source (data.worldpop.org).
    "population": OUTPUTS_DIR / "_map_layer_population.png",
    # Inundation-frequency ("how often does this flood") — smallest return
    # period at which each pixel floods, colored by annual chance. Static,
    # built by scripts/19_build_recurrence_layer.py from the flood library.
    "recurrence": OUTPUTS_DIR / "_map_layer_recurrence.png",
}

_TASK4_IMAGES: dict[str, Path] = {
    "ensemble-hydrograph": OUTPUTS_DIR / "task4" / "today_ensemble_hydrograph.png",
    "prob-gt-05m":          OUTPUTS_DIR / "task4" / "today_prob_gt_05m.png",
    "uncertainty":          OUTPUTS_DIR / "task4" / "today_uncertainty.png",
    "today-best":           OUTPUTS_DIR / "task4" / "today_best.png",
    "today-likely":         OUTPUTS_DIR / "task4" / "today_likely.png",
    "today-worst":          OUTPUTS_DIR / "task4" / "today_worst.png",
    "today-poi":            OUTPUTS_DIR / "task4" / "today_poi.png",
    "today-expected":       OUTPUTS_DIR / "task4" / "today_expected.png",
    **{f"day{i}": OUTPUTS_DIR / "task4" / f"day{i}_likely.png" for i in range(7)},
}


@router.get("/forecast/image/{name}")
async def get_forecast_image(name: str, user: dict = Depends(validate_api_key)):
    path = _TASK4_IMAGES.get(name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Unknown forecast image: {name}")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Image not yet generated: {name}")
    return FileResponse(path, media_type="image/png")


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


# Same 5cm threshold used when scripts/14_build_local_assets.py first
# tagged the 100-yr reference flood — kept identical so a return_period=100
# request reproduces the exact same FLOODED/OPEN split as the untagged default.
_DEPTH_THRESHOLD_M = 0.05


@router.get("/map/layers/{layer}")
async def get_map_layer(
    layer: str,
    return_period: Optional[int] = Query(
        None, description="Return period in years (5/10/25/50/100/200). "
        "Recomputes flood status/depth for that scenario instead of the FEMA 100-yr default."
    ),
    user: dict = Depends(validate_api_key),
):
    path = _GEOJSON_LAYERS.get(layer)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Unknown map layer: {layer}")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Layer file not found on disk: {path.name}")

    today_status_path = OUTPUTS_DIR / "task4" / "today_feature_status.json"
    apply_today_status = (
        return_period is None
        and layer in ("roads", "buildings", "infrastructure", "evac-routes")
        and today_status_path.exists()
    )

    # infrastructure is always materialized (not a raw FileResponse) so its
    # hand-placed pins can be snapped onto real building footprints below.
    data = json.loads(path.read_text()) if (layer in ("buildings", "infrastructure") or return_period is not None or apply_today_status) else None

    if layer == "buildings":
        # Only this layer gets a transform — everything else is a raw
        # passthrough (see module docstring). The raw OSM `building` tag
        # (school, house, industrial, ...) is already on disk but was
        # never grouped into anything a manager would scan at a glance;
        # inject a `category` property rather than have the frontend
        # duplicate this lookup in JS.
        for feature in data.get("features", []):
            feature["properties"]["category"] = categorize_building(
                feature["properties"].get("building")
            )

    if return_period is not None:
        # depth_by_rp was added by scripts/16_tag_return_periods.py for
        # roads/buildings/infrastructure — reruns the same 100-yr-only
        # flood tag against whichever scenario the map/simulation slider
        # currently has selected, instead of always showing the 100-yr view.
        # infrastructure.geojson labels its non-flooded state "SAFE" (built by
        # scripts/15_build_infrastructure.py); roads/buildings use "OPEN"
        # (scripts/14_build_local_assets.py) — preserve each layer's own word.
        not_flooded_label = "SAFE" if layer == "infrastructure" else "OPEN"
        data = data if data is not None else json.loads(path.read_text())
        rp_key = str(return_period)
        for feature in data.get("features", []):
            props = feature["properties"]
            depth_by_rp = props.get("depth_by_rp")
            if depth_by_rp and rp_key in depth_by_rp:
                depth = depth_by_rp[rp_key]
                props["max_depth_m"] = depth
                props["status"] = "FLOODED" if depth > _DEPTH_THRESHOLD_M else not_flooded_label
                props["severity"] = severity_tier(depth)
                props["selected_return_period_yr"] = return_period

    elif apply_today_status:
        # LIVE mode, no return-period explorer active: answer "is this
        # flooding TODAY" (src/probabilistic/today_feature_status.py,
        # written fresh on every forecast run) instead of silently falling
        # back to the static FEMA 100-yr reference tagging baked into the
        # file on disk -- that fallback is what made every building read
        # "FLOODED" on a dry day with nothing actually forecast to flood.
        today_status = json.loads(today_status_path.read_text()).get(layer, [])
        features = data.get("features", [])
        for feature, status in zip(features, today_status):
            props = feature["properties"]
            props["max_depth_m"] = status["max_depth_m"]
            props["max_depth_worst_m"] = status["max_depth_worst_m"]
            props["status"] = status["status"]
            props["severity"] = status.get("severity")
            props["poi_pct"] = status.get("poi_pct")
            props["data_source"] = "today_forecast"

    if layer == "infrastructure" and data is not None:
        # Snap the hand-placed facility pins onto the nearest real building
        # footprint (src/common/snap_to_buildings.py) so each tag sits on an
        # actual building instead of floating near it.
        from common.snap_to_buildings import snap_infrastructure
        data = snap_infrastructure(data)

    if data is not None:
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
                "population_exposed": entry.get("population_exposed"),
                "population_life_safety": entry.get("population_life_safety"),
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


@router.get("/download/flood-map/{return_period}")
async def download_flood_map(return_period: int, user: dict = Depends(validate_api_key)):
    """Download the real georeferenced depth GeoTIFF for a return period —
    the actual map a GIS analyst can open in QGIS/ArcGIS, not just a picture.
    These are the pre-built flood library maps (FEMA BFE + USGS 3DEP DEM,
    EPSG:32612) the forecast pulls the closest one from."""
    manifest_path = DATA_DIR / "flood_library_real" / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Flood library manifest not found.")
    manifest = json.loads(manifest_path.read_text())
    tif_name = manifest.get("files", {}).get(str(return_period))
    if not tif_name:
        raise HTTPException(status_code=404, detail=f"No library map for T={return_period}yr. Available: {sorted(manifest.get('files', {}).keys())}")
    tif_path = DATA_DIR / "flood_library_real" / tif_name
    if not tif_path.exists():
        raise HTTPException(status_code=404, detail=f"Map file missing on disk: {tif_name}")
    return FileResponse(
        tif_path, media_type="image/tiff",
        filename=f"UpperSonoitaCreek_flood_{return_period}yr.tif",
    )


@router.get("/simulation/raster/{return_period}/thumb")
async def get_simulation_raster_thumb(return_period: int, user: dict = Depends(validate_api_key)):
    # Cropped tight to the wet-pixel bounding box (src/probabilistic/scenarios.py
    # _reproject_depth_to_png) — the full raster's flood ribbon is only ~1-2% of
    # the frame, invisible at scenario-card thumbnail size without this crop.
    path = OUTPUTS_DIR / "sim" / f"depth_T{return_period:03d}yr_thumb.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No simulation thumbnail for T={return_period}yr")
    return FileResponse(path, media_type="image/png")


DEM_PATH = DATA_DIR / "terrain" / "dem_huc12_wgs84.tif"


@router.get("/map/elevation")
async def get_elevation_at_point(
    lat: float = Query(..., description="Latitude, WGS84"),
    lon: float = Query(..., description="Longitude, WGS84"),
    return_period: Optional[int] = Query(None, description="If given, also reports flood depth at this point for that scenario"),
    user: dict = Depends(validate_api_key),
):
    """Real point query against the same USGS 3DEP DEM the flood library is
    built from (data/terrain/dem_huc12_wgs84.tif) — not an estimate. When
    return_period is given, also samples that scenario's depth grid at the
    same point so a manager can ask "how high is this spot, and how deep
    would it flood at a 100-yr event" in one click."""
    import rasterio

    if not DEM_PATH.exists():
        raise HTTPException(status_code=404, detail="DEM not available on this deployment.")

    with rasterio.open(DEM_PATH) as src:
        if not (src.bounds.left <= lon <= src.bounds.right and src.bounds.bottom <= lat <= src.bounds.top):
            raise HTTPException(status_code=400, detail="Point is outside the watershed DEM extent.")
        elevation_m = next(src.sample([(lon, lat)], indexes=1))[0]
        elevation_m = float(elevation_m) if elevation_m == elevation_m else None  # NaN check

    flood_depth_m = None
    if return_period is not None:
        # Depth values live in the flood-library manifest's source GeoTIFFs,
        # not the pre-rendered PNG overlay (which is display-only RGBA).
        manifest_path = DATA_DIR / "flood_library_real" / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
            tif_name = manifest.get("files", {}).get(str(return_period))
            if tif_name:
                depth_tif = DATA_DIR / "flood_library_real" / tif_name
                if depth_tif.exists():
                    with rasterio.open(depth_tif) as dsrc:
                        import pyproj
                        transformer = pyproj.Transformer.from_crs("EPSG:4326", dsrc.crs, always_xy=True)
                        dx, dy = transformer.transform(lon, lat)
                        if dsrc.bounds.left <= dx <= dsrc.bounds.right and dsrc.bounds.bottom <= dy <= dsrc.bounds.top:
                            val = next(dsrc.sample([(dx, dy)], indexes=1))[0]
                            flood_depth_m = round(float(val), 3) if val == val and val > 0 else 0.0

    return {
        "lat": lat,
        "lon": lon,
        "elevation_m": round(elevation_m, 2) if elevation_m is not None else None,
        "flood_depth_m": flood_depth_m,
        "return_period_yr": return_period,
        "source": "USGS 3DEP 10m DEM (data/terrain/dem_huc12_wgs84.tif)",
    }
