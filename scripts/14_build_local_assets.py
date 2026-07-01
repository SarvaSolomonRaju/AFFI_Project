#!/usr/bin/env python3
"""
scripts/14_build_local_assets.py
================================

Build LOCAL resident-useful overlays for the Upper Sonoita Creek map:
  - OSM road network (with street names) tagged "FLOODED" / "OPEN" against the
    FEMA 1% (100-yr) flood depth raster.
  - OSM building footprints tagged the same way.
  - CSV summary of every flooded named road segment.

Outputs:
  data/local_assets/roads_huc12.geojson
  data/local_assets/buildings_huc12.geojson
  data/local_assets/flooded_roads_summary.csv
  data/local_assets/manifest.json
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import geopandas as gpd
import rasterio
import osmnx as ox

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "local_assets"
OUT.mkdir(parents=True, exist_ok=True)

BBOX_FILE = DATA / "fema_nfhl" / "huc12_bbox.geojson"
DEPTH_TIF = DATA / "flood_library_real" / "depth_T100yr_Q455cms.tif"
DEPTH_THRESHOLD_M = 0.05  # > 5 cm => flooded


def load_bbox():
    g = json.loads(BBOX_FILE.read_text())
    coords = g["features"][0]["geometry"]["coordinates"][0]
    xs = [c[0] for c in coords]; ys = [c[1] for c in coords]
    return min(ys), min(xs), max(ys), max(xs)  # S, W, N, E


def sample_max_depth(geom_utm, src, n=25):
    try:
        if geom_utm.geom_type in ("LineString", "MultiLineString"):
            if geom_utm.length <= 0: return 0.0
            pts = [geom_utm.interpolate(t/(n-1), normalized=True) for t in range(n)]
            xy = [(p.x, p.y) for p in pts]
        elif geom_utm.geom_type in ("Polygon", "MultiPolygon"):
            c = geom_utm.representative_point(); xy = [(c.x, c.y)]
        else:
            return 0.0
        vals = []
        for v in src.sample(xy, indexes=1):
            x = float(v[0])
            if np.isnan(x): x = 0.0
            vals.append(x)
        return float(max(vals)) if vals else 0.0
    except Exception:
        return 0.0


def main():
    s, w, n, e = load_bbox()
    print(f"[info] bbox W={w} S={s} E={e} N={n}")

    print("[info] downloading OSM road graph ...")
    G = ox.graph_from_bbox(bbox=(w, s, e, n), network_type="drive", simplify=True, retain_all=False)
    _, edges = ox.graph_to_gdfs(G, nodes=True, edges=True)
    edges = edges.reset_index()[["u","v","key","name","highway","length","geometry"]]
    edges["name"] = edges["name"].apply(lambda x: ", ".join(x) if isinstance(x,list) else (x or "(unnamed road)"))
    edges["highway"] = edges["highway"].apply(lambda x: x[0] if isinstance(x,list) else x)
    print(f"[info] {len(edges)} road segments")

    print("[info] downloading OSM buildings ...")
    try:
        bld = ox.features_from_bbox(bbox=(w, s, e, n), tags={"building": True})
        bld = bld[bld.geometry.type.isin(["Polygon","MultiPolygon"])].copy()
        keep = [c for c in ["name","building","addr:full","addr:street","addr:housenumber","geometry"] if c in bld.columns]
        bld = bld[keep].reset_index(drop=True)
    except Exception as ex:
        print(f"[warn] buildings: {ex}")
        bld = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    print(f"[info] {len(bld)} buildings")

    print(f"[info] sampling {DEPTH_TIF.name} ...")
    with rasterio.open(DEPTH_TIF) as src:
        crs = src.crs
        edges_utm = edges.to_crs(crs)
        edges["max_depth_m"] = [sample_max_depth(g, src) for g in edges_utm.geometry]
        edges["flooded_100yr"] = edges["max_depth_m"] > DEPTH_THRESHOLD_M
        edges["status"] = np.where(edges["flooded_100yr"], "FLOODED", "OPEN")

        if len(bld):
            bld_utm = bld.to_crs(crs)
            bld["max_depth_m"] = [sample_max_depth(g, src) for g in bld_utm.geometry]
            bld["flooded_100yr"] = bld["max_depth_m"] > DEPTH_THRESHOLD_M
            bld["status"] = np.where(bld["flooded_100yr"], "FLOODED", "OPEN")
            if "addr:full" not in bld.columns: bld["addr:full"] = None

    edges_out = edges[["name","highway","length","max_depth_m","flooded_100yr","status","geometry"]]
    edges_out.to_file(OUT/"roads_huc12.geojson", driver="GeoJSON")
    if len(bld):
        for c in bld.columns:
            if bld[c].dtype == object:
                bld[c] = bld[c].astype(str)
        bld.to_file(OUT/"buildings_huc12.geojson", driver="GeoJSON")
    else:
        (OUT/"buildings_huc12.geojson").write_text(json.dumps({"type":"FeatureCollection","features":[]}))

    flooded = edges_out[edges_out["flooded_100yr"]].copy()
    flooded = flooded[flooded["name"] != "(unnamed road)"]
    summary = (flooded.groupby("name")
               .agg(flooded_length_m=("length","sum"),
                    max_depth_m=("max_depth_m","max"),
                    n_segments=("name","size"))
               .reset_index()
               .sort_values("max_depth_m", ascending=False))
    summary.to_csv(OUT/"flooded_roads_summary.csv", index=False)

    n_road_fl = int(edges_out["flooded_100yr"].sum())
    n_bld_fl = int(bld["flooded_100yr"].sum()) if len(bld) else 0
    manifest = {
        "source": "OpenStreetMap (osmnx) intersected with FEMA 100-yr depth raster",
        "depth_raster": str(DEPTH_TIF.relative_to(ROOT)),
        "depth_threshold_m": DEPTH_THRESHOLD_M,
        "n_road_segments_total": len(edges_out),
        "n_road_segments_flooded": n_road_fl,
        "n_named_flooded_roads": int(summary.shape[0]),
        "n_buildings_total": int(len(bld)),
        "n_buildings_flooded": n_bld_fl,
    }
    (OUT/"manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\n[OK] Roads:     {len(edges_out)} total, {n_road_fl} flooded ({summary.shape[0]} named)")
    print(f"[OK] Buildings: {len(bld)} total, {n_bld_fl} flooded")
    print(f"[OK] -> {OUT}")
    if summary.shape[0]:
        print("\nTop flooded named roads:")
        print(summary.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
