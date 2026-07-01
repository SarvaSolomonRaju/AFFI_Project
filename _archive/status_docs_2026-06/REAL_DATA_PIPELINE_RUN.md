# AFFI Flood Forecasting — Real-Data Pipeline (Plan B)

This document is the complete, end-to-end run instructions for the
**real data** flood-mapping pipeline. Every flood map in this pipeline is
grounded in publicly-issued, government-authoritative data — no synthetic
terrain, no Gaussian DEM, no fabricated discharges.

## Data sources (all real, all free, all public)

| Layer | Source | Used for |
|---|---|---|
| FEMA NFHL flood zones (Layer 28) | hazards.fema.gov ArcGIS REST, DFIRM 04023C | 100-yr (AE) and 500-yr (X shaded) inundation extents |
| FEMA Base Flood Elevations (Layer 16) | hazards.fema.gov ArcGIS REST | 100-yr WSE (feet NAVD88) along Sonoita Creek |
| FEMA Cross-Sections (Layer 14) | hazards.fema.gov ArcGIS REST | XS locations |
| USGS NWIS Peak Streamflow | nwis.waterdata.usgs.gov, site 09481500 | 45 yrs of annual peaks → LP-III (Bulletin 17C) → Q for 2/5/10/25/50/100/200/500-yr |
| USGS 3DEP DEM | py3dep, USGS National Map | Real 10-m terrain for HUC-12 150503010204 (UTM 12N, 1778×1903 cells, 143.6 km²) |
| NOAA Atlas 14 | hdsc.nws.noaa.gov | 24-hr rainfall return periods (already in `src/benchmarking/return_periods.py`) |

## Pilot watershed (per white paper)
* HUC-12 **150503010204** — Sonoita Creek-Patagonia (55.4 mi² / 143.6 km²)
* Reference gauge USGS **09481500** — Sonoita Creek near Patagonia, AZ
* DFIRM panel **04023C** — Santa Cruz County, Arizona

## End-to-end run (from a clean checkout)

```bash
# Install deps
pip install requests geopandas rasterio shapely scipy pandas \
            py3dep pynhd pygeohydro

# Step 1: acquire FEMA NFHL flood zones (county + HUC-12 clip)
python scripts/09_acquire_fema_nfhl.py
# → data/fema_nfhl/{nfhl_zones_county.geojson, nfhl_zones_huc12.geojson, manifest.json}

# Step 2: fit LP-III to USGS annual peaks (no online StreamStats needed)
python scripts/10_acquire_usgs_streamstats.py
# → data/usgs/{peaks_09481500.csv, streamstats_09481500.json}

# Step 3: download 10-m DEM for HUC-12, reproject to UTM 12N
python scripts/11_acquire_3dep_dem.py
# → data/terrain/{dem_huc12_wgs84.tif, dem_huc12_utm12n_10m.tif}

# Step 4: pull FEMA FIS layers (BFE, XS, water lines)
python scripts/12_acquire_fis_profiles.py
# → data/fema_fis/{BFE_huc12.geojson, XS_huc12.geojson, WaterLn_huc12.geojson}

# Step 5: build the real flood-map library indexed by Q
python scripts/13_build_real_flood_library.py
# → data/flood_library_real/{manifest.json, depth_T{T}yr_Q{Q}cms.tif × 8}

# Step 6: run Task 1 (alert packet) — uses NOAA / NWS / USGS / OpenMeteo (real)
python scripts/run_task1.py
# → outputs/task1_alert_packet.json

# Step 7: Task 4 probabilistic mapping — REAL library lookup
python scripts/07_task4_probabilistic.py --library real
# → outputs/task4/{today_*.png, day*_*.png, summary.json}

# Step 8: Task 5 benchmarking — REAL library validation
python scripts/08_task5_benchmarking.py --library real
# → outputs/task5/{benchmark_report.json, return_period_table.csv}

# Step 9: build user/developer dashboard with provenance
python scripts/build_dashboard.py
# → outputs/dashboard.html
```

## How "which flood map matches today" works

1. NOAA / OpenMeteo gives **today's 24-hr rainfall** (P10 / P50 / P90 percentiles).
2. SCS Curve-Number (CN=75) converts rainfall → runoff volume → peak Q.
3. The Real flood library has 8 depth rasters indexed by Q at the 8 return periods.
4. `FloodMapLibrary.lookup(Q)` linearly interpolates between the two nearest stored Q values and returns the matching depth map.
5. The 3 scenarios (best / likely / worst) correspond to (P10, P50, P90) rainfall → 3 different Qs → 3 different depth maps drawn from the same library.
6. Cells with depth > 0.05 m are "wet"; severity is classified by max depth and wet-area km².

## What is REAL vs MODELED

* **Real (verbatim from authoritative source):** FEMA NFHL polygons, FEMA BFE elevations, USGS DEM, USGS annual peak streamflow time series.
* **Modeled (computed using standard hydrologic / hydraulic methods):**
  * Bulletin 17C Log-Pearson III peak-flow frequency (industry standard).
  * Leopold hydraulic geometry (depth ∝ Q^0.4) used to interpolate between return periods when FEMA only publishes the 100-yr WSE.
  * SCS Curve-Number runoff (NRCS TR-55).
* **Pre-existing FEMA HEC-RAS results:** Already encoded in FEMA AE polygons + BFE elevations (Layer 16). Our library reuses these directly.

## Outputs you get

```
outputs/
  task1_alert_packet.json          # NOAA/USGS/forecast packet
  task4/
    today_best.png                 # best-case (P10 rainfall) depth map
    today_likely.png               # likely (P50) — also shown in dashboard hero
    today_worst.png                # worst-case (P90)
    today_poi.png                  # probability-of-inundation
    day0_likely_thumb.png ... day6_likely_thumb.png   # 7-day strip
    summary.json                   # full ensemble summary
  task5/
    benchmark_report.json          # 7-check validation + 4-event replay
    return_period_table.csv        # rainfall × Q × scenario × severity
  dashboard.html                   # 3.7 MB final UI (User + Developer tabs)
data/
  fema_nfhl/        ← real FEMA flood zones
  fema_fis/         ← real FEMA BFE/XS/water lines
  usgs/             ← real LP-III peak Q
  terrain/          ← real 10-m DEM
  flood_library_real/   ← real indexed flood-depth library (8 maps)
```

## Verifying it is real

* `data/fema_nfhl/nfhl_zones_huc12.geojson` — open in QGIS; should match the published FEMA Flood Map Service Center map for Patagonia, AZ.
* `data/terrain/dem_huc12_utm12n_10m.tif` — elevation range 1148–1970 m matches reality (Sonoita 1245 m, ridges ~1900 m).
* `data/usgs/streamstats_09481500.json` — Q₁₀₀ ≈ 16 053 cfs (455 cms) matches published USGS flood-frequency report for site 09481500.
* `outputs/dashboard.html` — User tab has explicit "DATA PROVENANCE" banner listing every government source.

## Tests
```bash
pytest tests/ -q
# 102 passed
```

## Known limitations (honest)

1. **Extent for sub-100-yr events:** FEMA only publishes the 100-yr polygon. We use Leopold (Q^0.4) to scale depth, but the **extent** is kept at the 100-yr AE polygon and depth is set to zero only when scaled depth < 0.05 m. For very small events (< 5 cms), this may over-estimate inundation. The proper fix is HAND-FIM stage-extent curves (Plan C) or running a real HEC-RAS sweep (Plan A).
2. **No SAR validation yet:** Historical-event MAE against Sentinel-1 inundation is not in this build. Replace `predicted_median_wet_depth_m` comparison with SAR IoU/CSI when ready.
3. **45 yrs of peaks ends 1983:** The USGS gauge 09481500 was discontinued in 1983. For post-1983 flood-frequency estimates, supplement with regional regression or active gauges (e.g., 09480500 Santa Cruz River at Lochiel).
