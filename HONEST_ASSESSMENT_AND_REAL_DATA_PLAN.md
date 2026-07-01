# Honest Assessment and Real-Data Plan
**Date:** June 22, 2026

## 1. The advisor's question
The advisor stated, correctly: **HEC-RAS flood inundation maps for return periods (5, 10, 20, 25, 50, 100, 500-year) already exist for Sonoita Creek (FEMA / USACE).** The task is:

> Given today's rainfall, predict today's discharge, then look up the matching pre-computed flood map.

This is the same pattern NOAA OWP uses operationally (ras2fim and HAND-FIM).

## 2. Brutal honest assessment of what we built

| Task | Status | Real or synthetic? |
|------|--------|---|
| 1. Meteorology (GFS, Atlas-14) | Production | **REAL** — Open-Meteo GFS + NOAA Atlas-14 |
| 2. Hydrology (XGBoost hurdle) | Production | **REAL** — USGS 09471000 (train) → 09481500 (transfer) |
| 3. Hydraulics (ResUNet) | Synthetic | **SYNTHETIC** — Gaussian-mound DEM, idealized HAND+Manning, NOT real Sonoita |
| 4. Probabilistic (today) | Built on Task 3 | **SYNTHETIC** — library is interpolation between synthetic depths |
| 5. Benchmarking (today) | Built on Task 3 | Mixed — real Q, but depth residuals vs synthetic predictions |
| 6. API + Dashboard | Production | **REAL** |

**Task 2 is the strongest link.** Real rain → real Q. That part stays.
**Tasks 3, 4, 5 are physically meaningless until tied to real terrain and real HEC-RAS maps.**

### Divergences from the white paper
- Pilot watershed: paper says HUC **150503010204** (HUC-12, 143.6 km²); our code uses HUC-8 (510 km²).
- Anchor: paper says Walnut Gulch (USDA SWRC); we used Babocomari (acceptable as proxy).
- Task 3: paper says U-Net trained on **250 HEC-RAS simulations** on real terrain; we used 80 Manning scenarios on a synthetic Gaussian DEM.
- Task 4: paper says run all 31 GFS members through the full pipeline; we approximate with SCS-CN on P10/P50/P90.
- Task 5: paper says compare to **pre-computed HEC-RAS 10/25/50/100-yr maps**; we compare Q only.

## 3. Why the current pipeline will not give accurate results
1. Synthetic terrain ≠ real Sonoita Creek geometry. SR-82, real channels, road crossings, building footprints absent.
2. Depth metrics (RMSE 0.034 m, MAE 0.264 m) are internally consistent within a synthetic universe — meaningless externally.
3. Library indexed by Q is methodologically sound; contents are wrong.
4. Deployed as-is would mislead emergency managers.

## 4. Corrected plan — Plan B (executable today, no partner data required)

| Step | Source | Output |
|------|--------|--------|
| R1 | FEMA NFHL, Santa Cruz County (04023) | 1% (100-yr) and 0.2% (500-yr) polygons |
| R2 | FEMA FIS Vol. 1, Santa Cruz County | WSE profiles for 10/50/100/500-yr along Sonoita Creek |
| R3 | USGS StreamStats AZ, gauge 09481500 | Peak Q (cms) for 2/5/10/25/50/100/200/500-yr |
| R4 | USGS 3DEP 1/3 arcsec DEM, HUC 150503010204 | Real 10 m terrain raster |
| R5 | Build RealFloodMapLibrary indexed by Q | manifest.json + Q_*.tif rasters |
| R6 | Replace Task 4 lookup | Real depth/extent rasters for today's Q |
| R7 | Validate against Sentinel-1 SAR (Jul 2014, Aug 2017) | Real IoU/CSI numbers |
| R8 | Stamp every artifact with provenance | "Source: FEMA NFHL eff. YYYY-MM-DD" |

## 5. Plan A (multi-week) — full white-paper conformance
Acquire HEC-RAS model from FEMA Region 9 / Santa Cruz County Flood Control / ADWR → run 250 scenarios → retrain ResUNet. Best fidelity; requires partner data sharing.

## 6. Plan C (fallback) — NOAA OWP HAND-FIM
Download HAND grid for HUC8 15050301 from ESIP S3 (`s3://noaa-nws-owp-fim/hand_fim/outputs/`). Any Q → inundation polygon, nationally consistent. Less channel detail than HEC-RAS but operationally what NWS uses.

## 7. Data acquisition endpoints (verified)

| Asset | URL |
|---|---|
| FEMA NFHL ArcGIS REST | https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer |
| FEMA county shapefile (search) | https://hazards.fema.gov/femaportal/NFHL/searchResult (county 04023) |
| FEMA FIS Vol. 1 Santa Cruz Co | https://www.santacruzcountyaz.gov/DocumentCenter/View/3299/Flood-Insurance-Study-Volume-1 |
| USGS StreamStats | https://streamstats.usgs.gov/streamstatsservices/ |
| USGS 3DEP DEM | py3dep.get_map("DEM", geometry, resolution=10) |
| USGS NWIS peak flows | https://nwis.waterdata.usgs.gov/nwis/peak?site_no=09481500&format=rdb |
| NOAA OWP HAND | s3://noaa-nws-owp-fim/hand_fim/outputs/ |

## 8. Target run instructions (after Plan B)
```bash
pip install requests geopandas rasterio shapely fiona py3dep pynhd

# acquire real data (~5 min, ~80 MB)
python scripts/09_acquire_fema_nfhl.py
python scripts/10_acquire_usgs_streamstats.py
python scripts/11_acquire_3dep_dem.py
python scripts/12_acquire_fis_profiles.py

# build real library
python scripts/13_build_real_flood_library.py

# re-run with REAL data
python scripts/07_task4_probabilistic.py --library real
python scripts/08_task5_benchmarking.py --validate sar
python scripts/build_dashboard.py
```

## 9. Residual risks (honest)
1. FEMA effective FIRMs only cover 1% and 0.2% zones natively; we interpolate WSE along profile stations from FIS for 5/25/200-yr.
2. Effective FIRMs in Santa Cruz County are from 2009-2014; channel morphology may have changed — stamped on every output.
3. Sentinel-1 SAR validation needs ASF/GEE account; fallback is FEMA disaster declarations.

## 10. What the user will see after Plan B
- **User View:** today's flood map = real FEMA polygon (or next-higher RP), clipped to watershed, on real 10 m hillshade; "≈ 25-year storm" labels.
- **Developer View:** Task 4 = real Q→map index; Task 5 = real IoU vs SAR.
- Provenance footer on every artifact.
