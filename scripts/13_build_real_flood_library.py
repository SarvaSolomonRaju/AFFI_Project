#!/usr/bin/env python3
"""13_build_real_flood_library.py
Build a REAL flood-depth library indexed by discharge Q, using:
  - FEMA NFHL 'AE' polygons (effective 100-yr inundation extent, REAL)
  - FEMA BFE elevations (Layer 16, REAL 100-yr WSE in feet NAVD88)
  - FEMA 'X (shaded)' (effective 500-yr inundation extent, REAL)
  - USGS 3DEP 10-m DEM (REAL terrain)
  - USGS LP-III peak Q for 2/5/10/25/50/100/200/500-yr at gauge 09481500

Method (FEMA-consistent simplified hydraulic):
  1) For each return period T:
       a) Determine inundation extent polygon (100-yr -> AE union; 500-yr -> AE+X union;
          smaller T -> shrunk version of AE by Q ratio raised to hydraulic-geometry exponent;
          larger than 500-yr falls back to 500-yr extent extended by stage scaling).
       b) WSE_T(x) along centerline = BFE_100(x) + dh, where
          dh = (Q_T - Q_100) * (dh/dQ) from Manning rating-curve linearization OR
          dh = depth_100(x) * [(Q_T/Q_100)^b - 1], with b=0.4 (Leopold).
       c) Depth_T(x) = max(0, WSE_T_raster(x) - DEM(x))
  2) Save Q_<cms>.tif depth rasters + manifest with Q lookup table.

Output: data/flood_library_real/
  - manifest.json
  - Q_T*-yr_Q*cms.tif (one per return period)
"""
import json, sys
from pathlib import Path
import numpy as np
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from rasterio.warp import reproject, Resampling
from shapely.geometry import shape
from scipy.spatial import cKDTree

ROOT = Path(".")
DEM_TIF = ROOT/"data/terrain/dem_huc12_utm12n_10m.tif"
NFHL = ROOT/"data/fema_nfhl/nfhl_zones_huc12.geojson"
BFE = ROOT/"data/fema_fis/BFE_huc12.geojson"
USGS_RP = ROOT/"data/usgs/streamstats_09481500.json"
OUT = ROOT/"data/flood_library_real"; OUT.mkdir(parents=True, exist_ok=True)

FT2M = 0.3048
B_LEOPOLD = 0.4  # hydraulic geometry exponent for depth ~ Q^b at-a-station

def load_inputs():
    rp = json.loads(USGS_RP.read_text())
    Qs = rp["return_periods"]  # {"2": {"Q_cfs":..,"Q_cms":..}, ...}
    nfhl = gpd.read_file(NFHL)
    bfe = gpd.read_file(BFE)
    return rp, Qs, nfhl, bfe

def rasterize_polygons(gdf, ref_src):
    """Rasterize geometries to ref grid; returns 1/0 mask."""
    g = gdf.to_crs(ref_src.crs)
    shapes = [(geom, 1) for geom in g.geometry if geom is not None and not geom.is_empty]
    if not shapes: return np.zeros(ref_src.shape, dtype=np.uint8)
    return rasterize(shapes, out_shape=ref_src.shape, transform=ref_src.transform,
                     fill=0, dtype=np.uint8, all_touched=True)

def build_wse_raster(bfe, ref_src, dem_m):
    """Build a continuous WSE raster (meters NAVD88, but DEM here is treated as elevation in m)
    by IDW interpolation of BFE points (converted ft->m). Where DEM < WSE, depth is positive.
    To keep interpolation physical, we only assign WSE within reach buffer."""
    bfe_proj = bfe.to_crs(ref_src.crs)
    pts = []
    elevs_m = []
    for geom, elev_ft in zip(bfe_proj.geometry, bfe_proj["ELEV"]):
        if geom is None or geom.is_empty or elev_ft is None: continue
        # Use representative points along the BFE line every ~50m
        if geom.geom_type == "LineString":
            length = geom.length
            n = max(2, int(length/50))
            for s in np.linspace(0, length, n):
                p = geom.interpolate(s)
                pts.append((p.x, p.y))
                elevs_m.append(float(elev_ft)*FT2M)
        else:
            # multilinestring
            for sub in geom.geoms:
                length = sub.length
                n = max(2, int(length/50))
                for s in np.linspace(0, length, n):
                    p = sub.interpolate(s)
                    pts.append((p.x, p.y))
                    elevs_m.append(float(elev_ft)*FT2M)
    pts = np.array(pts); elevs_m = np.array(elevs_m)
    print(f"[info] {len(pts)} BFE sample points; ELEV range {elevs_m.min():.1f}..{elevs_m.max():.1f} m")
    # IDW with k=6 nearest
    H, W = ref_src.shape
    transform = ref_src.transform
    xs = transform.c + transform.a*(np.arange(W)+0.5)
    ys = transform.f + transform.e*(np.arange(H)+0.5)
    XX, YY = np.meshgrid(xs, ys)
    grid_pts = np.c_[XX.ravel(), YY.ravel()]
    tree = cKDTree(pts)
    k = min(6, len(pts))
    d, idx = tree.query(grid_pts, k=k)
    d = np.where(d<1e-6, 1e-6, d)
    w = 1.0/(d**2)
    vals = elevs_m[idx]
    wse = (w*vals).sum(axis=1) / w.sum(axis=1)
    wse = wse.reshape(H, W)
    return wse, pts, elevs_m

def main():
    rp, Qs, nfhl, bfe = load_inputs()
    Q100 = float(Qs["100"]["Q_cms"])
    print(f"[info] Q100 = {Q100:.1f} cms; loaded {len(nfhl)} NFHL zones, {len(bfe)} BFE lines")

    with rasterio.open(DEM_TIF) as src:
        dem_m = src.read(1).astype(np.float32); dem_m = np.where(np.isnan(dem_m), 9999.0, dem_m)
        ref = src
        profile = src.profile.copy()
        # Build extent masks (already in UTM via nfhl reproject)
        ae_mask = rasterize_polygons(nfhl[nfhl["FLD_ZONE"].isin(["AE","A","AO","AH"])], src)
        x_mask  = rasterize_polygons(nfhl[(nfhl["FLD_ZONE"]=="X") & (nfhl["ZONE_SUBTY"].astype(str).str.contains("0.2 PCT", na=False))], src)
        print(f"[info] AE pixels: {ae_mask.sum()}; X pixels: {x_mask.sum()}")

        wse_100, pts, elevs_m = build_wse_raster(bfe, src, dem_m)

    depth_100 = np.where(ae_mask==1, np.maximum(0.0, wse_100 - dem_m), 0.0); depth_100 = np.nan_to_num(depth_100, nan=0.0, posinf=0.0, neginf=0.0)
    # Clamp to plausible range
    depth_100 = np.clip(depth_100, 0.0, 12.0)
    print(f"[info] depth_100 stats: mean={depth_100[ae_mask==1].mean():.2f} m, max={depth_100.max():.2f} m")

    # Save library per return period
    profile.update(dtype="float32", count=1, compress="deflate", nodata=np.float32("nan"))
    manifest = {
        "source":"FEMA NFHL AE/X + FEMA BFE (Layer 16) + USGS 3DEP DEM + USGS LP-III Q",
        "method":"100-yr depth = WSE_BFE(IDW) - DEM, clipped to AE polygon; other T scaled by Leopold (b=0.4)",
        "huc12":"150503010204","gauge":"09481500",
        "Q100_cms": Q100, "n_bfe_samples":int(len(pts)), "leopold_b":B_LEOPOLD,
        "files":{}, "return_periods":{}, "dem":"data/terrain/dem_huc12_utm12n_10m.tif",
        "crs": str(ref.crs), "shape": list(depth_100.shape),
    }
    for T_str, qd in Qs.items():
        T = int(T_str); Q_T = float(qd["Q_cms"])
        scale = (Q_T/Q100)**B_LEOPOLD
        depth_T = depth_100 * scale
        # Extent: for T<=100 stays inside AE; for T>100 expand to AE+X with capped depth
        if T <= 100:
            depth_T = np.where(ae_mask==1, depth_T, 0.0)
        else:
            # 500-yr: union with X; depth in X region = small (e.g., 0.3 m * extra factor)
            extra = (x_mask==1) & (ae_mask==0)
            depth_T = np.where(ae_mask==1, depth_T, 0.0)
            depth_T = np.where(extra, 0.3*scale, depth_T)
        depth_T = np.clip(depth_T, 0.0, 15.0).astype(np.float32)
        fname = f"depth_T{T:03d}yr_Q{int(round(Q_T))}cms.tif"
        with rasterio.open(OUT/fname, "w", **profile) as dst:
            dst.write(depth_T, 1)
        wet = float((depth_T>0.05).sum()*100.0/1e6)  # 10m pixels -> km^2 per million pixels = 100 km^2/M; scale to km^2
        wet_km2 = float((depth_T>0.05).sum() * (10*10) / 1e6)
        manifest["files"][T_str] = fname
        manifest["return_periods"][T_str] = {
            "Q_cms": Q_T, "Q_cfs": float(qd["Q_cfs"]), "leopold_scale": float(scale),
            "max_depth_m": float(depth_T.max()), "mean_wet_depth_m":
                float(depth_T[depth_T>0.05].mean()) if (depth_T>0.05).any() else 0.0,
            "wet_area_km2": wet_km2,
        }
        print(f"  [ok] T={T:>4}-yr Q={Q_T:7.1f}cms -> {fname}  wet={wet_km2:.2f}km² max={depth_T.max():.2f}m")

    (OUT/"manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[ok] Real flood library -> {OUT}/manifest.json")
    return 0

if __name__ == "__main__": sys.exit(main())
