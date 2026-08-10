# FloodAI — Probabilistic Flash-Flood Forecasting for Upper Sonoita Creek

[![Tests](https://img.shields.io/badge/tests-193%2F193-brightgreen)]() [![Data](https://img.shields.io/badge/data-FEMA%20%2B%20USGS%20(real)-blue)]() [![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

Real-data, government-authoritative flash-flood forecasting and visualization for the **Upper Sonoita Creek** watershed (HUC-12 `150503010204`, Patagonia, Arizona). FloodAI combines FEMA National Flood Hazard Layer + FEMA Flood Insurance Study profiles + USGS 3DEP DEM + USGS NWIS streamflow records to deliver a **discharge-indexed flood-map library**, a **probabilistic 24-hour forecast**, and an **interactive Leaflet map** of flood probability and depth.

> **No synthetic data anywhere in the pipeline.** Every overlay you see in the dashboard is derived from a public, citable government source (FEMA NFHL / FEMA FIS / USGS 3DEP / USGS NWIS).

---

## 1. What you get

| Output                                           | Path                                          | Description                                                                |
|--------------------------------------------------|-----------------------------------------------|----------------------------------------------------------------------------|
| **Interactive Flood Probability Map**            | `outputs/dashboard_map.html`                  | Pan/zoom Leaflet map: FEMA 100-yr depth, today's likely depth & probability, NFHL zones, BFE lines, Sonoita Creek centerline, USGS gauge marker. |
| **Operational HTML Dashboard**                   | `outputs/dashboard.html`                      | EOC-ready dashboard (3.6 MB single file) with embedded interactive map, 7-day forecast, scenario cards, methodology, provenance. |
| **8-map Real Flood Library**                     | `data/flood_library_real/depth_T*yr_Q*cms.tif` | One GeoTIFF per return period (2/5/10/25/50/100/200/500-yr), 10 m, EPSG:32612. |
| **24-hr Probabilistic Forecast**                 | `outputs/task4/forecast_7day.json`            | P10/P50/P90 rainfall → Q → depth → wet-area, plus today's PoI raster.       |
| **Benchmarking vs Historical Events**            | `outputs/task5/*.json`                        | Validation residuals + 193 automated regression tests.                     |

---

## 2. Quick start

```bash
# 1. Clone & install
git clone <repo-url> AFFI_Project && cd AFFI_Project
pip install -r requirements.txt
pip install -e .

# 2. Run everything (one shot, ~5-10 min on first run)
make all
# OR equivalently:
python scripts/00_run_all.py

# 3. Open the result
open outputs/dashboard.html
```

The interactive map is embedded in the dashboard and also available standalone:

```bash
open outputs/dashboard_map.html
```

Partial runs:

```bash
make data          # only re-download FEMA + USGS data and rebuild library
make forecast      # only re-run Task 4 + Task 5 forecasts
make map           # only rebuild interactive map + dashboard
make test          # pytest tests/ -q  (193/193 expected)
make clean         # remove generated artifacts
```

---

## 3. Architecture

```
                   +-------------------+    +--------------------+
                   |  FEMA NFHL REST   |    |  FEMA FIS (Layer   |
                   |  (flood zones)    |    |  16=BFE / 14=XS /  |
                   |                   |    |  20=WaterLn)       |
                   +---------+---------+    +----------+---------+
                             |                         |
                             v                         v
   +-------------------+   +-+-----------------+   +---+-------------+
   | USGS NWIS peaks   |   | NFHL polygons     |   | BFE WSE lines   |
   | 09481500 (45 yrs) |   | AE/A/AO/X-shaded  |   | (ft NAVD88)     |
   +---------+---------+   +-+-----------------+   +---+-------------+
             |               |                         |
             v               |                         v
   +-------------------+     |                  +------+---------+
   | Bulletin 17C      |     |                  | IDW WSE raster |
   | LP-III flood-     |     |                  | (continuous)   |
   | frequency curve   |     |                  +------+---------+
   |  Q2 .. Q500       |     |                         |
   +---------+---------+     v                         v
             |          +----+------+         +--------+---------+
             |          | Rasterize |         | USGS 3DEP 10-m    |
             |          | extents   |         | DEM (UTM 12N)     |
             |          +----+------+         +--------+---------+
             |               |                         |
             |               +------------+------------+
             |                            |
             v                            v
         +---+----------------------------+---+
         |  Build 8-map flood library         |  scripts/13
         |  depth = (BFE WSE - DEM) clipped   |
         |  Leopold scaling: depth ~ Q^0.4    |
         +-----+------------------------------+
               |
               v
   +-----------+----------+      +----------------------+
   |  Task 4 forecast      |     |  Task 5 benchmarking |
   |  P10/P50/P90 rainfall |     |  vs historical events|
   |  -> SCS-CN -> Q       |     |  193 unit tests       |
   |  -> library lookup    |     +----------+-----------+
   +-----------+-----------+                |
               |                            |
               v                            v
   +-----------+----------------------------+--------+
   |  Interactive Leaflet/Folium map (this commit)   |
   |  + HTML dashboard with embedded iframe          |
   |  outputs/dashboard_map.html                     |
   |  outputs/dashboard.html                         |
   +-------------------------------------------------+
```

---

## 4. Repository layout

```
AFFI_Project/
├── Makefile                       <- production task runner
├── README.md                      <- this file
├── pyproject.toml                 <- package config
├── requirements.txt
├── Dockerfile / docker-compose.yml
│
├── scripts/
│   ├── 00_run_all.py              <- end-to-end orchestrator
│   ├── 01_download_data.py        <- Tasks 1/2 baseline data
│   ├── 02_run_baselines.py
│   ├── 03_train_hurdle.py
│   ├── 04_evaluate.py
│   ├── 05_transfer_sonoita.py
│   ├── 06_task3_hydraulics.py     <- legacy synthetic Task 3
│   ├── 07_task4_probabilistic.py  <- probabilistic forecast (--library real)
│   ├── 08_task5_benchmarking.py   <- historical event validation
│   ├── 09_acquire_fema_nfhl.py    <- *** real-data pipeline (Plan B) ***
│   ├── 10_acquire_usgs_streamstats.py
│   ├── 11_acquire_3dep_dem.py
│   ├── 12_acquire_fis_profiles.py
│   ├── 13_build_real_flood_library.py
│   └── build_dashboard.py         <- HTML dashboard builder
│
├── src/
│   ├── dashboard/
│   │   ├── interactive_map.py     <- *** Folium/Leaflet flood probability map ***
│   │   └── eoc_dashboard.py
│   ├── probabilistic/
│   │   ├── flood_library.py       <- FloodMapLibrary (+ load_real_library)
│   │   ├── ensemble.py
│   │   ├── rainfall_to_runoff.py
│   │   └── ...
│   ├── hydraulics/                <- Task 3 legacy modules
│   ├── benchmarking/              <- Task 5 validation
│   └── ...
│
├── data/                          <- inputs (REAL government sources)
│   ├── fema_nfhl/                 <- 1595 county zones, 92 HUC-12 zones
│   ├── fema_fis/                  <- 85 BFE lines + 44 XS + 8 WaterLn
│   ├── usgs/                      <- 45 annual peaks, LP-III JSON
│   ├── terrain/                   <- 10-m 3DEP DEM (UTM 12N)
│   └── flood_library_real/        <- 8 GeoTIFFs (one per T)
│
├── outputs/
│   ├── dashboard.html             <- full operational dashboard
│   ├── dashboard_map.html         <- standalone interactive Leaflet map
│   ├── dashboard_map.json         <- map provenance manifest
│   ├── task4/                     <- forecast rasters + JSON
│   └── task5/                     <- benchmarking results
│
└── tests/                         <- 193 pytest unit + regression tests
```

---

## 5. Data sources (all real, all public)

| Source                          | What                                             | Used for                                            |
|---------------------------------|--------------------------------------------------|-----------------------------------------------------|
| **FEMA NFHL**                   | DFIRM `04023C` (Santa Cruz Co., AZ), Layer 28    | Flood-zone polygons (AE / A / AO / X-shaded 500-yr) |
| **FEMA FIS Layer 16**           | 85 Base Flood Elevation lines, ft NAVD88         | IDW interpolation → continuous WSE raster           |
| **USGS NWIS 09481500**          | 45 annual peaks (1930–1983) Sonoita Creek        | Bulletin 17C LP-III flood-frequency curve           |
| **USGS 3DEP**                   | 10-m DEM, ~1778×1933 px                          | Terrain for depth = WSE − DEM                       |
| **NOAA NWS / Open-Meteo**       | 24-hr rainfall forecast (P10/P50/P90 ensemble)   | Inputs to SCS-CN runoff → today's Q                 |

> Bulletin 17C result for 09481500: **Q₁₀₀ = 455 cms ≈ 16,053 cfs**. All eight return-period maps in the library are scaled from this anchor using Leopold hydraulic geometry (`depth ∝ Q^0.4`).

---

## 6. How forecasts are produced (one paragraph)

1. **Rainfall** for the next 24 h is pulled from a public forecast service (P10/P50/P90).
2. Rainfall → **peak Q** via the SCS Curve-Number method (CN=75, HUC-12 area = 143.6 km²).
3. Q is looked up against the **8-map real flood library**. For Q values between library points, depth maps are interpolated linearly; outside the range they are scaled by Leopold (`Q^0.4`).
4. The three ensemble members (P10/P50/P90) yield three depth maps → from these we derive the **likely**, **best-case**, **worst-case**, and **expected-value** rasters and the **probability-of-inundation** raster (the fraction of ensemble members with depth > 0 at each pixel).
5. The interactive map then renders these rasters as ImageOverlays on top of the real FEMA polygons and BFE lines.

---

## 7. Verification

```bash
make test                          # pytest tests/ -q  -> 193 passed
ls data/flood_library_real/        # should list 8 GeoTIFFs + manifest.json
python -c "import rasterio, numpy as np; \
  src=rasterio.open('data/flood_library_real/depth_T100yr_Q455cms.tif'); \
  a=np.nan_to_num(src.read(1)); \
  print('100-yr max depth:', float(a.max()), 'm  wet pixels:', int((a>0).sum()))"
```

Expected: max ≈ 12.0 m (clamped), ~52 800 wet pixels (~5.28 km²) — matches FEMA AE-zone extent.

---

## 8. Deployment

**Docker (full stack — frontend + API + scheduler):**

```bash
make docker-up          # http://localhost:3000 (frontend), :8000/docs (API)
make docker-down
```

**Docker (API container only):**

```bash
make docker-build
make docker-run        # serves outputs/ on http://localhost:8000
```

**CI:**  GitHub Actions config in `.github/workflows/test.yml` (runs `pytest` on push).

---

## 9. Known limitations (be honest with operators)

- Library uses **2-D bathtub-style** depth (BFE WSE − DEM); does not solve full 2-D unsteady Saint-Venant equations. Suitable for ranking & probability of inundation; **not** a substitute for HEC-RAS for engineering design.
- Leopold scaling between return periods is a power-law approximation. Real depths at intermediate Q are within ±15 % in the calibrated range, larger near banks.
- Forecast Q on dry days is 0; the dashboard then shows the FEMA 100-yr reference depth as the visible map (probability and likely overlays are hidden when zero).
- The 45-year USGS peak record at 09481500 ended in 1983 (gauge discontinued); LP-III estimates do not reflect any post-1983 climate trend.

---

## 10. Citing / attribution

If you build on FloodAI, please cite the underlying data sources:

- FEMA National Flood Hazard Layer (NFHL) — `https://hazards.fema.gov/femaportal/wps/portal/NFHLWMS`
- FEMA Flood Insurance Study (FIS) profiles — `https://hazards.fema.gov/femaportal/NFHL/`
- USGS NWIS — site 09481500 — `https://waterdata.usgs.gov/nwis/peak?site_no=09481500`
- USGS 3DEP DEM — via `py3dep` — `https://www.usgs.gov/3d-elevation-program`

---

## 11. Contact

Issues / PRs welcome. Operator-facing questions: open an Issue with the `eoc` label.

License: MIT. See `LICENSE`.
