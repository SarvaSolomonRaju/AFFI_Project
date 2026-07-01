#!/usr/bin/env python3
"""12_acquire_fis_profiles.py
Acquire FEMA Flood Insurance Study profile data for Sonoita Creek:
  - Base Flood Elevation lines (NFHL Layer 16) — 100-yr WSE at cross-sections
  - Cross-Sections (NFHL Layer 14) — XS locations
  - Water Lines (NFHL Layer 20) — channel centerlines
This gives us REAL FEMA-effective 1% AEP water-surface elevations along Sonoita Creek."""
import json, sys
from pathlib import Path
import requests
import geopandas as gpd
from shapely.geometry import shape, box

OUT = Path("data/fema_fis"); OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer"
DFIRM = "04023C"
HUC12_BBOX = (-110.85, 31.46, -110.65, 31.62)

LAYERS = {16: "BFE", 14: "XS", 20: "WaterLn"}

def page(layer, where, offset, n=500):
    p = {"f":"geojson","where":where,"outFields":"*","returnGeometry":"true","outSR":4326,
         "resultOffset":offset,"resultRecordCount":n}
    r = requests.get(f"{BASE}/{layer}/query", params=p, timeout=180); r.raise_for_status()
    return r.json().get("features", [])

def fetch_all(layer):
    feats = []; off = 0
    while True:
        b = page(layer, f"DFIRM_ID='{DFIRM}'", off)
        if not b: break
        feats.extend(b)
        if len(b) < 500: break
        off += 500
        if off > 20000: break
    return feats

def to_gdf(feats):
    if not feats: return gpd.GeoDataFrame()
    geoms = [shape(f["geometry"]) for f in feats if f.get("geometry")]
    props = [f.get("properties",{}) for f in feats if f.get("geometry")]
    return gpd.GeoDataFrame(props, geometry=geoms, crs="EPSG:4326")

def main():
    huc_bbox = gpd.GeoDataFrame({"id":[1]}, geometry=[box(*HUC12_BBOX)], crs="EPSG:4326")
    manifest = {"source":"FEMA NFHL FIS layers","dfirm_id":DFIRM,"huc12_bbox":list(HUC12_BBOX),"layers":{}}
    for lid, name in LAYERS.items():
        print(f"[info] Fetching layer {lid} ({name})...")
        try:
            feats = fetch_all(lid)
            gdf = to_gdf(feats)
            if gdf.empty:
                print(f"  [warn] layer {lid}: empty")
                manifest["layers"][name] = {"layer_id":lid,"n_county":0,"n_huc12":0}
                continue
            clipped = gpd.clip(gdf, huc_bbox)
            gdf.to_file(OUT/f"{name}_county.geojson", driver="GeoJSON")
            if not clipped.empty:
                clipped.to_file(OUT/f"{name}_huc12.geojson", driver="GeoJSON")
            print(f"  [ok] {name}: county={len(gdf)}, huc12={len(clipped)}")
            manifest["layers"][name] = {"layer_id":lid,"n_county":int(len(gdf)),"n_huc12":int(len(clipped))}
            if name=="BFE" and not clipped.empty and "ELEV" in clipped.columns:
                elevs = clipped["ELEV"].dropna().astype(float).tolist()
                if elevs:
                    manifest["layers"][name]["bfe_elev_ft_min"] = float(min(elevs))
                    manifest["layers"][name]["bfe_elev_ft_max"] = float(max(elevs))
                    manifest["layers"][name]["bfe_elev_ft_mean"] = float(sum(elevs)/len(elevs))
        except Exception as e:
            print(f"  [err] layer {lid}: {e}")
            manifest["layers"][name] = {"layer_id":lid,"error":str(e)}
    (OUT/"manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[ok] manifest -> {OUT/'manifest.json'}")
    return 0

if __name__ == "__main__": sys.exit(main())
