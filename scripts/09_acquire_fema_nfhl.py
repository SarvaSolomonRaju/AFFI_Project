#!/usr/bin/env python3
"""09_acquire_fema_nfhl.py — Download FEMA NFHL flood zones for Santa Cruz County, AZ (DFIRM 04023C),
   then clip to HUC-12 150503010204 (Sonoita Creek)."""
import json, sys
from pathlib import Path
import requests
import geopandas as gpd
from shapely.geometry import shape, box

OUT = Path("data/fema_nfhl"); OUT.mkdir(parents=True, exist_ok=True)
NFHL = "https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
DFIRM = "04023C"
HUC12 = "150503010204"
# HUC-12 150503010204 bbox (Sonoita Creek-Patagonia), approx WGS84
HUC12_BBOX = (-110.85, 31.46, -110.65, 31.62)

def page(where, offset, n=500):
    p = {"f":"geojson","where":where,"outFields":"FLD_ZONE,ZONE_SUBTY,STATIC_BFE,DEPTH,SFHA_TF,STUDY_TYP",
         "returnGeometry":"true","outSR":4326,"resultOffset":offset,"resultRecordCount":n}
    r = requests.get(NFHL, params=p, timeout=180); r.raise_for_status()
    return r.json().get("features", [])

def main():
    print(f"[info] FEMA NFHL DFIRM_ID={DFIRM}")
    feats = []
    off = 0
    while True:
        b = page(f"DFIRM_ID='{DFIRM}'", off)
        if not b: break
        feats.extend(b)
        print(f"  fetched {len(feats)} so far")
        if len(b) < 500: break
        off += 500
        if off > 50000: break
    if not feats:
        print("[err] no features"); return 1
    geoms = [shape(f["geometry"]) for f in feats if f.get("geometry")]
    props = [f.get("properties",{}) for f in feats if f.get("geometry")]
    gdf = gpd.GeoDataFrame(props, geometry=geoms, crs="EPSG:4326")
    gdf.to_file(OUT/"nfhl_zones_county.geojson", driver="GeoJSON")
    print(f"[ok] county zones: {len(gdf)}")

    huc_poly = gpd.GeoDataFrame({"huc12":[HUC12]}, geometry=[box(*HUC12_BBOX)], crs="EPSG:4326")
    huc_poly.to_file(OUT/"huc12_bbox.geojson", driver="GeoJSON")
    clipped = gpd.clip(gdf, huc_poly)
    clipped.to_file(OUT/"nfhl_zones_huc12.geojson", driver="GeoJSON")
    by = clipped["FLD_ZONE"].value_counts().to_dict() if "FLD_ZONE" in clipped.columns else {}
    print(f"[ok] HUC-12 clipped: {len(clipped)} zones; types={by}")
    (OUT/"manifest.json").write_text(json.dumps({
        "source":"FEMA NFHL (effective)","endpoint":NFHL,"dfirm_id":DFIRM,
        "huc12":HUC12,"huc12_bbox":list(HUC12_BBOX),
        "n_zones_county":int(len(gdf)),"n_zones_huc12":int(len(clipped)),
        "zones_by_type_huc12":by,"crs":"EPSG:4326",
        "files":["nfhl_zones_county.geojson","nfhl_zones_huc12.geojson","huc12_bbox.geojson"]}, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
