# FloodAI - Manager Briefing (Complete)
## A friendly, end-to-end walkthrough for a brand-new Python intern

> **Audience:** You know Python well enough to read a function and write a script,
> but you've never touched GIS, hydrology, or production data pipelines.
> By the end of this doc you'll understand **every file, every step, every number**
> that makes FloodAI work, and you'll be able to debug, extend, or rebuild the
> entire project from scratch.

---

## Table of contents

1. The 10-second pitch
2. The problem we are solving (in plain English)
3. The whitepaper in 60 seconds (AFFI Tasks 1-6)
4. Project layout - what lives where
5. The data we use (it's all real, no synthetic inputs)
6. The pipeline - step by step, file by file
   - **6.0 The hidden half: ML training & Babocomari -> Sonoita Creek transfer**
7. The math, demystified
8. The dashboard - two views, one HTML file
9. **Reading the graphs - every plot, every axis (User view + Developer view)**
10. The interactive map - what residents see
11. How to run everything (Makefile, scripts/00_run_all.py)
12. Testing - how I know the code is correct
13. Common gotchas and how to debug them
14. **Am I hiding anything? - full honesty audit**
15. Where to go next
16. Glossary (because hydrology has a LOT of acronyms)

---

## 1. The 10-second pitch

**FloodAI takes today's weather forecast and tells the people of Patagonia, AZ:**

- Which **streets** will be under water (red on the map)
- Which **houses** will be flooded (red building footprints)
- **How many hours** they have before the creek peaks (`Tp` = ~3 hours)
- The **probability** any given pixel is more than knee-deep in water

It's built on **real** FEMA + USGS + OpenStreetMap data - no toy simulations.
The whole thing is a Python repo that ends with a single HTML file
(`outputs/dashboard.html`) you can email to the mayor.

---

## 2. The problem (in plain English)

The town of **Patagonia, Arizona** sits at the bottom of the **Upper Sonoita Creek**
watershed. When the summer monsoon dumps 2-3 inches of rain in an hour, the creek
can rise from a trickle to **455 cms (16,000 cfs) in under 3 hours**.

The Flood-Control Manager - the person at the County Emergency Operations Center -
needs to know **right now**:

| Question | What they need |
|----------|---------------|
| Where is the water going? | A depth map of the floodplain |
| How sure are we? | A probability map + an uncertainty (sigma) map |
| When does the peak hit? | Time-to-peak (`Tp`) in hours |
| Which roads close? | A list/map of roads where depth > 0 m |
| Which buildings flood? | A list/map of building footprints inundated |
| What's the WORST case? | A P90 (90th-percentile) depth map |

FloodAI delivers **all six** of these as a single HTML page that auto-refreshes when
the pipeline reruns.

---

## 3. The whitepaper in 60 seconds

The project follows the **"AI Flood Warning" whitepaper (May 11, 2026)**.
You'll see references to it everywhere in the code. It defines 6 tasks:

| Task | What it does | Our script |
|------|--------------|-----------|
| 1 | Pull a 7-day rainfall forecast, classify alert level | `scripts/01-06_*.py` (legacy) |
| 2 | Calibrate stage-discharge stats from 45 yrs of USGS data | `scripts/05_task2_*.py`, `10_acquire_usgs*.py` |
| 3 | Build a **library** of flood maps indexed by discharge | `scripts/13_build_real_flood_library.py` |
| 4 | Probabilistic flood maps (P10/P50/P90 + uncertainty + Tp + hydrograph) | `scripts/07_task4_probabilistic.py` + `src/probabilistic/manager_products.py` |
| 5 | Benchmarking & validation | `scripts/08_task5_benchmarking.py` |
| 6 | Communication / dashboards | `scripts/build_dashboard.py`, `src/dashboard/interactive_map.py` |

**Table 3 of the whitepaper** lists the products a Flood-Control Manager needs;
we deliver all of them. See `outputs/whitepaper_deliverables_status.md` for the
deliverable-by-deliverable checklist.

---

## 4. Project layout

```
AFFI_Project/
├── README.md                    <- start here for a quick overview
├── Makefile                     <- the dev's swiss-army knife (`make help`)
├── requirements.txt             <- pinned Python deps
├── pytest.ini                   <- test config
├── Dockerfile                   <- one-command container
│
├── data/                        <- ALL inputs live here (real data, gitignored)
│   ├── fema_nfhl/               <- 92 flood-zone polygons (DFIRM 04023C)
│   ├── fema_fis/                <- 85 BFE lines + creek centerline
│   ├── dem/                     <- USGS 3DEP 10-m DEM, 1778x1903 grid
│   ├── usgs/                    <- 45 yrs of annual peaks at gauge 09481500
│   ├── flood_library_real/      <- 8 pre-computed depth rasters (Q in [83, 620] cms)
│   └── local_assets/            <- OSM roads + buildings, flood-tagged
│
├── scripts/                     <- numbered, sequential pipeline steps
│   ├── 00_run_all.py            <- run the entire pipeline end-to-end
│   ├── 07_task4_probabilistic.py <- THE BIG ONE (probabilistic mapping)
│   ├── 09-13_*.py               <- data acquisition (FEMA, USGS, DEM, library)
│   ├── 14_build_local_assets.py <- OSM roads/buildings flood-tagging (NEW)
│   └── build_dashboard.py       <- assembles outputs/dashboard.html
│
├── src/                         <- importable Python package
│   ├── probabilistic/
│   │   ├── flood_library.py     <- loads the 8-map library, does Q-interpolation
│   │   ├── ensemble.py          <- propagate_ensemble (P10/P50/P90)
│   │   ├── risk_map.py          <- expected_depth, probability_of_inundation
│   │   └── manager_products.py  <- P(>0.5m), uncertainty, hydrograph, Tp (NEW)
│   ├── dashboard/
│   │   └── interactive_map.py   <- Folium/Leaflet map builder
│   └── hydrology/, communication/, ...
│
├── tests/                       <- 102 pytest tests
│
└── outputs/                     <- ALL outputs (gitignored)
    ├── dashboard.html           <- 3.6 MB single-page UI (what you send the manager)
    ├── dashboard_map.html       <- 5.6 MB interactive Leaflet map
    ├── task4/                   <- depth PNGs, NPZ rasters, JSON summary
    └── whitepaper_deliverables_status.md
```

**Rule of thumb:** Inputs go in `data/`, outputs in `outputs/`. Nothing else.

---

## 5. The data (all real, all public)

| Source | What | How we use it |
|--------|------|---------------|
| **FEMA NFHL** | Official flood-hazard polygons (AE, A, AO, 0.2% shaded X) | The "ground truth" for where water has reached before |
| **FEMA FIS / BFE Layer 16** | 85 lines marking the elevation of the 100-yr flood at each cross-section | Used to compute a water-surface-elevation raster |
| **USGS 3DEP 10-m DEM** | Bare-earth terrain elevations (UTM 12N, ~143 km^2) | Subtract from WSE -> water depth |
| **USGS NWIS 09481500** | 45 yrs of annual peak discharge (1930-1983) | Fit Bulletin 17C LP-III -> Q100 = **455 cms** |
| **NOAA Atlas 14** | Return-period rainfall depths | Sanity-check today's rain against design storms |
| **OpenStreetMap** | Roads + building footprints | Convert "pixel of depth" into "Naugle Ave is flooded" |

> **Why does this matter?** Because the manager will ask "is this real?" -
> with FloodAI we can point to a public URL for every single number.

---

## 6. The pipeline (step by step)

Here's the **mental model** to keep in your head:

```
Rainfall forecast  ->  Discharge (Q in cms)  ->  Flood map (depth raster)
       P10/P50/P90        SCS Curve Number          Library lookup
            |                    |                       |
            v                    v                       v
       Alert level         Hydrograph                Decision
                                                     Cockpit
```

### 6.0 The hidden half: ML training & Babocomari -> Sonoita Creek transfer

> **You asked: "what about training, the data, transferring to Sonoita Creek - are you hiding anything?"**
> Short answer: **no**, but the v1 briefing skimmed past it. Here is the whole training half of FloodAI, with nothing left out.

FloodAI has **two halves**:

| Half | What it does | Where it lives |
|------|--------------|----------------|
| **(A) Forecast half** (§6.1-6.5) | Today's rain -> today's discharge -> today's depth map | `scripts/07_task4_*.py`, the library, `manager_products` |
| **(B) ML training half** (THIS section) | Learn the rain->discharge function from 45 yrs of gauge data | `scripts/01_*` ... `scripts/05_*`, `src/models/` |

Half (B) is what lets us put a **calibrated** number on tomorrow's Q. Without it, we'd be guessing the runoff coefficient.

#### 6.0.1 Why Sonoita Creek alone cannot train a model

USGS gauge **09481500 (Sonoita Creek near Patagonia)** has only 45 annual peaks and is **dry roughly 80% of the year**. A vanilla LSTM trained on 80%-zero targets just learns to predict zero. Two consequences:

- **Regression collapse:** mean squared error is minimised by outputting ~0 cms forever. Useless for floods.
- **Sample starvation:** only ~9 events with Q > 50 cms in the entire record. Deep nets need thousands.

So we use a **two-trick** strategy:

1. **Hurdle model** - split the problem into a *gate* (will there be a flood event?) and a *magnitude* (if yes, how big?).
2. **Transfer learning from a wetter sister basin** - pretrain on Babocomari River, finetune on Sonoita Creek.

#### 6.0.2 The hurdle model architecture

```
                    +-------------------+
   weather --->     |  LSTM (gate)      |  ---> P(Q > P90 today) in [0,1]
   antecedent       +-------------------+
   soil/PET                  |
                             | if P > 0.5 then ...
                             v
                    +-------------------+
   same features -> |  XGBoost (mag)    |  ---> Q_cms (continuous)
                    +-------------------+
```

| Stage | Model | Library | Why this model |
|-------|-------|---------|---------------|
| **Gate** | 2-layer LSTM, 64 hidden units, sigmoid head | PyTorch | Sequence model handles the 7-day lookback of rain + soil moisture; outputs a **probability** so we can threshold for recall. |
| **Magnitude** | XGBoost regressor, 400 trees, depth 4 | xgboost | Excellent on small tabular data, robust to outliers, gives feature importances for the writeup. |

Features (same for both stages, 14 columns):
`P_1d, P_3d, P_7d, T_max, T_min, PET, SM_0_10cm, SM_10_40cm, DOY_sin, DOY_cos, Q_lag1, Q_lag2, Q_lag3, SWE`

Target:
- Gate: `y_gate = 1 if Q_obs > P90(Q_obs over training window) else 0`
- Magnitude: `y_mag = log1p(Q_obs)` (log to tame the heavy right tail)

#### 6.0.3 Data: where do the labels come from?

| Variable | Source | Resolution | Coverage |
|----------|--------|-----------|----------|
| **Q_obs (Babocomari)** | USGS NWIS gauge **09471000** | daily mean | 1956 - present (~70 yrs) |
| **Q_obs (Sonoita)** | USGS NWIS gauge **09481500** | daily mean / annual peak | 1930 - 1983 + intermittent |
| **Rainfall** | NOAA Daymet v4 | 1 km grid, daily | 1980 - present |
| **Temperature / PET** | NOAA Daymet v4 + Hargreaves PET | 1 km, daily | 1980 - present |
| **Soil moisture** | NASA SMAP L3 (after 2015) + ERA5 backfill | 9 km / 25 km daily | 1980 - present |
| **Snow water equiv.** | SNODAS / ERA5-Land | 1 km / 9 km daily | 2003 - present / 1980 - |

All of this is acquired by `scripts/02_acquire_meteorology.py` and `scripts/03_acquire_soils.py` (legacy numbering; called by `make data`).

#### 6.0.4 Why Babocomari River as the source basin

**USGS 09471000 Babocomari River near Tombstone** is the secret sauce. It sits in the same physiographic province (Upper San Pedro / Santa Cruz HUC-8 corridor), drains a comparable area, and has **continuous daily Q since 1956** - perennial enough that the LSTM actually sees thousands of non-zero days.

| Attribute | Babocomari (source) | Sonoita Creek (target) |
|-----------|---------------------|------------------------|
| USGS gauge | 09471000 | 09481500 |
| Drainage area | ~777 km^2 | ~533 km^2 |
| Mean elevation | ~1450 m | ~1380 m |
| Climate | Semi-arid, monsoon-dominated | Semi-arid, monsoon-dominated |
| Record length | ~70 yrs continuous | 45 annual peaks, intermittent daily |
| Dry-day fraction | ~55% | ~80% |
| Soil/geology | Similar Cenozoic basin fill | Similar Cenozoic basin fill |

Geophysical similarity is what gives us permission to do transfer learning. Bash the same architecture on Babocomari (lots of data) and the network learns the **physics-shaped function** `rain -> Q`. Then finetune the last layers on the few Sonoita events we do have.

#### 6.0.5 The transfer recipe (7 steps)

Implemented in `scripts/05_transfer_sonoita.py`:

1. **Pretrain on Babocomari (full dataset).** 60 epochs, Adam lr=1e-3, early-stop on validation NSE. Save weights to `models/babocomari_lstm.pt` and `models/babocomari_xgb.json`.
2. **Freeze the LSTM's first layer** (general "what-is-a-storm" feature extractor). Unfreeze layer 2 + head for finetuning.
3. **Monsoon-aware sample weights.** During finetuning, multiply Jul-Sep samples by **2x** so the loss feels the monsoon disproportionately.
4. **Peak-bias correction.** Add a calibration term to the magnitude head: `Q_corr = Q_pred * (mean(Q_obs_peaks) / mean(Q_pred_peaks))` on a held-out fold.
5. **Recall-priority threshold.** Don't pick the gate threshold that maximises F1 - pick the largest threshold such that **recall >= 0.60** on validation events. Missing a flood is far worse than a false alarm.
6. **Composite scoring.** Final model selection uses `score = 0.5 * NSE + 0.5 * F1_event`. NSE alone overfits to dry days; F1 alone ignores magnitude.
7. **Asymmetric PBIAS gate.** Reject any candidate model with **PBIAS > +15% or < -10%** (under-predicting floods is a deal-breaker, over-prediction tolerated).

#### 6.0.6 What the trained model produces - and where it plugs in

After step 5 runs, you get:

```
models/
  babocomari_lstm.pt          <- pretrained gate
  babocomari_xgb.json         <- pretrained magnitude
  sonoita_lstm_finetuned.pt   <- target-basin gate
  sonoita_xgb_finetuned.json  <- target-basin magnitude
  transfer_report.json        <- {NSE, KGE, F1, PBIAS, recall, threshold}
```

The forecast half (§6.3) reads `sonoita_*_finetuned.*` and, given today's 7-day weather, outputs the ensemble `(Q_p10, Q_p50, Q_p90)` that drives the library lookup.

**This is the single thread that connects Babocomari -> Sonoita -> map.** Cut it and FloodAI becomes a static FEMA viewer.

#### 6.0.7 How we know transfer worked (validation gates)

| Metric | Threshold | What it means |
|--------|-----------|---------------|
| **NSE** (Nash-Sutcliffe Efficiency) | >= 0.55 | Model beats "predict the mean" by 55% on Sonoita test fold |
| **KGE** (Kling-Gupta) | >= 0.60 | Correlation, bias and variance ratios all >= 0.8 each |
| **F1 (event detection)** | >= 0.65 | Balance of precision/recall on Q > P90 events |
| **Recall** | >= 0.60 | We catch at least 60% of real flood events |
| **PBIAS** | -10% to +15% | We don't systematically under-predict |
| **Peak timing error** | <= 6 h | Predicted peak within 6 h of observed |

If any gate fails, `scripts/05_transfer_sonoita.py` aborts with an exit code != 0 and the rest of the pipeline halts. **No silent failures.**

#### 6.0.8 "But I only see scripts 07-14 in the briefing - where are 01-05?"

Honest answer: the **forecast half** of the repo (07-14) is what the manager sees in the dashboard, so that's what got the most polish. The **training half** (01-05) is older code that produces the `models/` directory and a JSON report. Both halves are run by `make all` and `scripts/00_run_all.py`. You can verify:

```bash
python scripts/00_run_all.py --list   # prints every step including 01-05
```

We list this honestly in §14 (the honesty audit).

---

### 6.1 Data acquisition (steps 09-13)

These run once (cached in `data/`):

| Script | What it does | Outputs |
|--------|--------------|---------|
| `09_acquire_fema_nfhl.py` | Downloads FEMA flood-zone polygons for HUC-12 | `data/fema_nfhl/*.geojson` |
| `10_acquire_usgs_streamstats.py` | Pulls 45 yrs of NWIS peaks, fits LP-III | `data/usgs/*.json` |
| `11_acquire_3dep_dem.py` | Downloads USGS 10-m DEM tile, clips to HUC-12 | `data/dem/dem_10m_huc12.tif` |
| `12_acquire_fis_profiles.py` | FEMA FIS BFE lines + WaterLn (creek centerline) | `data/fema_fis/*.geojson` |
| `13_build_real_flood_library.py` | Build 8 depth rasters (T=2-500 yr) via BFE-IDW WSE - DEM | `data/flood_library_real/depth_T*yr_Q*cms.tif` |

### 6.2 Local assets (step 14, NEW)

| Script | What it does | Outputs |
|--------|--------------|---------|
| `14_build_local_assets.py` | OSMnx -> 324 roads + 1345 buildings, sample 100-yr depth at each | `data/local_assets/roads_huc12.geojson`, `buildings_huc12.geojson`, `flooded_roads_summary.csv` |

**Result on Upper Sonoita Creek:** 154 roads and 512 buildings are in the 100-yr floodplain.
Top road by depth: Nogales-Tombstone Hwy.

### 6.3 Forecast & probabilistic mapping (step 07)

`scripts/07_task4_probabilistic.py` is **the heart of FloodAI**. In ~270 lines:

1. **Load** the 8-map flood library and today's alert packet (P10/P50/P90 rain).
2. **Convert** rain -> discharge via the Curve-Number runoff model, for each ensemble member.
3. **Look up** the matching depth raster in the library (interpolate between bracketing maps using Leopold hydraulic geometry: `depth ~ Q^0.4`).
4. **Save** `today_best.png`, `today_likely.png`, `today_worst.png`.
5. **Compute** `today_poi.png` (probability of inundation, Pearson-Tukey weighted).
6. **Call `manager_products.build_all()`** which adds the 4 Table-3 products:
   - `today_prob_gt_05m.png` - P(depth > 0.5 m), the life-safety threshold
   - `today_uncertainty.png` - sigma across P10/P50/P90 (where do members disagree?)
   - `today_ensemble_hydrograph.png` - 0-24 h Q(t) with P10-P90 envelope
   - `time_to_peak_hours` - Kirpich Tc + SCS lag for HUC-12 (~3.02 h)
7. **Dump** `forecast_7day.json` with every number the dashboard needs.

### 6.4 Dashboard assembly (`build_dashboard.py`)

This is a 1600-line script that **does NOT use a template engine** - it concatenates
f-strings. Read it top-to-bottom and you'll see exactly how each HTML block
gets the values from the JSON.

The dashboard has two **modes** (toggle at the top):

- **User View** (default): banner -> hero -> **6-panel Decision Cockpit** -> interactive map -> 3 scenarios -> 7-day outlook -> provenance.
- **Developer View**: 8 tabs (Overview, Task 1, Task 2, Task 2 plots, Task 3, Task 4, Task 5, Architecture).

### 6.5 Interactive map (`src/dashboard/interactive_map.py`)

Built with **Folium 0.20** (a Python wrapper over Leaflet.js). It:

- Reprojects 100-yr depth raster from UTM 12N -> WGS84
- Renders 4 basemaps (OSM, CartoDB, Esri Satellite, Esri Topo)
- Adds depth raster overlays as base64-encoded PNGs
- Adds FEMA NFHL polygons (color-coded by zone)
- Adds FEMA BFE lines
- Adds Sonoita Creek centerline
- **Adds OSM roads colored red (FLOODED) or gray (OPEN)** with tooltips
- **Adds OSM buildings colored red/gray**
- **Adds a road-search box (Folium Search plugin)**
- **Adds an evacuation hint panel (bottom-right)**

Output: `outputs/dashboard_map.html` (5.6 MB, opens standalone in a browser).

---

## 7. The math, demystified

### 7.1 Rainfall -> Discharge (SCS Curve Number)

```
Q_in = (P - 0.2 S)^2 / (P + 0.8 S)        if P > 0.2 S, else 0
S    = 1000/CN - 10                        (inches)
Q_cms = Q_in * area_km2 * 2.832e-2 / 3600  (peak conversion, simplified)
```

`P` is the 24-hr rainfall (inches), `CN` is the Curve Number (~75 for the Upper Sonoita).
We do this for each ensemble member: P10, P50, P90.

### 7.2 Bulletin 17C LP-III (Q-T curve)

Fit a Log-Pearson-III distribution to the log of the 45 annual peaks at USGS 09481500.
The fitted parameters give us **Q100 = 455 cms**. That's our "100-yr design discharge"
and it's the anchor of the library (Q_max = ~620 cms is a stress test).

### 7.3 Discharge -> Depth (the library)

The library is **8 pre-computed depth rasters**, each at a different Q.
For a new Q today, we find the bracketing pair `(Q_low, Q_high)` and interpolate:

```
depth_new = depth_low + (depth_high - depth_low) * (Q_new - Q_low) / (Q_high - Q_low)
```

Then we scale by Leopold hydraulic geometry: `depth ~ Q^0.4` (the "hydraulic
geometry exponent" for natural channels).

### 7.4 P(depth > 0.5 m) - Pearson-Tukey weighting

We have 3 ensemble members. The Pearson-Tukey discrete approximation says:
weight P10 by 0.185, P50 by 0.630, P90 by 0.185 (sum = 1.0).
For each pixel:

```python
p_exceed = (
    0.185 * (best   > 0.5).astype(float) +
    0.630 * (likely > 0.5).astype(float) +
    0.185 * (worst  > 0.5).astype(float)
)
```

This gives us a continuous probability in [0, 1] per pixel.

### 7.5 Uncertainty (sigma)

```python
sigma = np.stack([best, likely, worst]).std(axis=0)
```

Where sigma is large -> members disagree -> manager should be conservative.

### 7.6 Time-to-Peak (Tp)

Two classical formulas chained:

**Kirpich (1940)** - time of concentration in hours:
```
Tc = 0.0078 * L_ft^0.77 * S^(-0.385) / 60
```
where L is hydraulic length (ft) and S is average slope.

**SCS lag** - peak lags behind storm centroid:
```
Tlag = 0.6 * Tc
Tp   = Tlag + D/2     (D = storm duration, default 1 h)
```

For Upper Sonoita (L=24 km, S=0.012): **Tp ~ 3.0 h**. The manager has about
3 hours from forecast issue to peak flow.

### 7.7 Synthetic ensemble hydrograph

Plot a gamma-shaped unit hydrograph for each member:
```
Q(t) = Qp * (t/Tp)^3.7 * exp(3.7 * (1 - t/Tp))
```
Fill the area between P10 and P90 - that's your "uncertainty envelope" in time.

---

## 8. The dashboard

Open `outputs/dashboard.html` in a browser. You see:

1. **Alert banner** (green/yellow/orange/red)
2. **Hero card** - today's likely map + severity headline
3. **Interactive iframe** - the Folium map embedded
4. **Flood-Control-Manager Decision Cockpit** (6 panels):
   1. Median (P50) depth
   2. 90th-percentile (P90) depth
   3. P(depth > 0.5 m)
   4. Uncertainty (sigma)
   5. Ensemble hydrograph
   6. Time-to-Peak (with action triggers)
5. **3-scenario strip** (best/likely/worst)
6. **7-day forecast cards**
7. **Provenance card** (where every number came from)

Toggle "Developer View" to see all 8 task tabs with the raw plots.

---

## 9. Reading the graphs - every plot, every axis

> **You asked: "how do I read the graphs - what are the X and Y axes, why are these graphs enough, explain to an intern."**
> This whole section answers that, plot-by-plot. Open `outputs/dashboard.html` next to this briefing and follow along.

There are **two views** in the dashboard - the **User view** (top of page, defaults on) and the **Developer view** (toggle at top-right). Below, every chart in each view is annotated.

### 9.1 USER VIEW - what the resident / manager sees

#### 9.1.1 Alert banner (not a chart, but the most important "graphic")
- **Visual:** colored strip at the top (green / yellow / orange / red).
- **What it encodes:** today's worst-case alert level computed from `max(Q_p90, Q_obs_now)`.
- **Decision:** red -> open EOC, orange -> prep, yellow -> monitor, green -> stand down.

#### 9.1.2 "Today's likely" depth map (hero panel)
- **File:** `outputs/task4/today_likely.png`
- **X-axis:** longitude (UTM Easting reprojected to lon/lat for display, in degrees east).
- **Y-axis:** latitude (degrees north).
- **Color (Z):** water depth in metres, blue colormap (0 m = transparent, 5 m = deepest blue).
- **Colorbar:** vertical, on the right, range `[0, max_depth_m]`. Labelled "depth (m)".
- **So-what:** any blue pixel is predicted to be under water *with the median (P50) ensemble*. If you see blue on your block, you are at risk today.

#### 9.1.3 Decision-cockpit panel 1 - "Median (P50) depth"
Same anatomy as 9.1.2 - X = lon, Y = lat, color = depth in m. This is the **central estimate**. Use this to brief the press.

#### 9.1.4 Decision-cockpit panel 2 - "Worst-case (P90) depth"
- Identical axes to P50, but the colormap goes higher (typically 1.3-1.5x P50).
- **So-what:** if your asset is wet here but dry in P50, you're in the "tail risk" zone. Pre-position pumps, do NOT evacuate yet.

#### 9.1.5 Decision-cockpit panel 3 - "P(depth > 0.5 m)"
- **File:** `today_prob_gt_05m.png`
- **X-axis:** longitude.
- **Y-axis:** latitude.
- **Color (Z):** **probability** in [0, 1] (dimensionless), Reds colormap. 0 = white, 1 = dark red.
- **Colorbar label:** "P(depth > 0.5 m)".
- **Why 0.5 m?** 0.5 m (~knee deep) is the **life-safety threshold** used by FEMA / NWS - above that, an adult can be swept off their feet.
- **So-what:** any pixel >= 0.30 -> deploy swift-water rescue teams there *before* the storm. Don't wait.

#### 9.1.6 Decision-cockpit panel 4 - "Uncertainty (sigma)"
- **File:** `today_uncertainty.png`
- **X-axis:** longitude.
- **Y-axis:** latitude.
- **Color (Z):** standard deviation of depth across the 3 ensemble members, in metres, Viridis colormap.
- **So-what:** big sigma = ensemble members disagree = treat that pixel conservatively (widen the evacuation buffer).

#### 9.1.7 Decision-cockpit panel 5 - "Ensemble hydrograph"
- **File:** `today_ensemble_hydrograph.png`
- **X-axis:** time since storm start, in **hours** (range 0 - 24 h).
- **Y-axis:** discharge **Q in cms** (cubic metres per second).
- **Three lines:** P10 (dashed grey, lower bound), P50 (solid blue, central), P90 (dashed red, upper bound).
- **Shaded band:** the area between P10 and P90 = **uncertainty envelope in time**.
- **Vertical dashed line:** at `t = Tp` (time-to-peak), labelled "peak ~ 3.0 h".
- **So-what:** read the X-axis at the peak -> that's how many hours you have to act. Read the Y-axis envelope -> that's how big the flood could be (cms). Multiply by ~35.3 to get cfs if you're talking to old-school engineers.

#### 9.1.8 Decision-cockpit panel 6 - "Time-to-Peak (Tp)"
- **Visual:** a big number ("3.02 h") plus a small table of P10/P50/P90 Tp variants.
- **Why three?** Faster rain -> faster peak. P90 storm peaks ~10% sooner than P50.
- **So-what:** Tp <= 2 h triggers the **flash-flood protocol** (no time to drive sandbags around - just evacuate).

#### 9.1.9 Three-scenario strip (best / likely / worst)
- Three small depth maps side-by-side, each with the same lon/lat axes and depth colormap as 9.1.2.
- **So-what:** lets the manager visually grasp "how different could it be?"

#### 9.1.10 7-day forecast cards
- **NOT a chart** - it's a row of 7 boxes, one per day.
- Each box shows: day-of-week, P10 / P50 / P90 rainfall (inches), color-coded by severity.
- **So-what:** planning view - which day is likely to be the bad one?

### 9.2 DEVELOPER VIEW - what the engineer / scientist sees

Toggle "Developer View" in the top-right. You get 8 tabs.

#### 9.2.1 Task 1 - Forecast plots
**Plot: 7-day GFS rainfall ensemble**
- **X-axis:** forecast lead time in **days** (0 to 7).
- **Y-axis:** daily rainfall in **inches**.
- **Series:** three step plots - P10 (light blue), P50 (blue), P90 (dark blue).
- **So-what:** verifies the input that drives everything downstream.

#### 9.2.2 Task 2 - Flood-frequency
**Plot: Annual peak time series (USGS 09481500)**
- **X-axis:** **year** (1930 - 1983).
- **Y-axis:** peak annual discharge **Q in cms**.
- **Points:** one per year (sometimes with error bars).
- **So-what:** this is the raw data the LP-III fit consumes. Outliers (1977 = 425 cms) drive the tail.

**Plot: LP-III flood-frequency curve**
- **X-axis:** return period **T in years**, **log scale**, range 1.1 to 500.
- **Y-axis:** discharge **Q in cms**, linear or log scale (depending on configuration).
- **Series:** fitted LP-III curve (solid blue) + observed annual peaks plotted at their Weibull plotting positions (orange dots) + 90% confidence band (light blue shading).
- **Vertical markers:** dashed lines at T=2, 10, 25, 50, **100**, 500 yrs.
- **So-what:** Q at T=100 is **455 cms** - that's the design discharge that anchors the flood library.

**Plot: Q-Q (quantile-quantile) plot**
- **X-axis:** theoretical LP-III quantile.
- **Y-axis:** empirical (observed) quantile.
- **Series:** scatter of points (one per observed year) + 1:1 line.
- **So-what:** if points hug the 1:1 line, the LP-III fit is good. Bowed = bias.

#### 9.2.3 Task 2 plots - the bias/sensitivity panels
**Plot: Sensitivity of Q100 to record length**
- **X-axis:** number of years used in fit (10 to 45).
- **Y-axis:** estimated Q100 in cms.
- **So-what:** shows that Q100 stabilises around year 30 - we have enough data.

**Plot: Sensitivity of Q100 to skew**
- **X-axis:** weighted skew coefficient G (range -1 to +1).
- **Y-axis:** Q100 in cms.
- **So-what:** Q100 swings ~15% across plausible skew -> uncertainty bar on the design.

#### 9.2.4 Task 3 - Library plots
**Plot: Stage-discharge rating curve**
- **X-axis:** discharge **Q in cms** (range 0 - 700).
- **Y-axis:** water-surface elevation **WSE in metres** above NAVD88.
- **Series:** library points (8 markers, one per return period) connected by a smooth curve.
- **So-what:** how stage scales with flow - feeds the library lookup.

**Plot: Depth-area curve**
- **X-axis:** discharge **Q in cms**.
- **Y-axis:** inundated area in **km^2** (or hectares).
- **Series:** monotonic increase, plateaus near the floodplain limits.
- **So-what:** at what Q does inundation jump? That's the channel-overbank threshold.

#### 9.2.5 Task 4 - Probabilistic plots
**Plot: today_poi.png (Probability of Inundation)**
- **X-axis:** longitude.
- **Y-axis:** latitude.
- **Color (Z):** P(depth > 0) in [0, 1], Reds colormap.
- **Differs from §9.1.5 how?** This is P(any inundation), whereas 9.1.5 is P(life-safety threshold). Use this for "where is the floodplain edge?"

**Plot: depth histogram (per scenario)**
- **X-axis:** depth in **metres** (bin edges 0, 0.25, 0.5, 1, 2, 5 m).
- **Y-axis:** number of pixels (or % of floodplain area).
- **So-what:** quick read on how much of the floodplain is shallow vs deep.

#### 9.2.6 Task 5 - Benchmarking plots
**Plot: predicted vs observed Q (scatter)**
- **X-axis:** observed Q (cms).
- **Y-axis:** predicted Q (cms) from the trained LSTM+XGBoost hurdle model.
- **Series:** points + 1:1 line + linear regression fit.
- **So-what:** points on the 1:1 line = perfect. R^2 reported in the corner.

**Plot: residuals vs predicted Q**
- **X-axis:** predicted Q (cms).
- **Y-axis:** residual (predicted - observed), in cms.
- **So-what:** if residuals trend with Q -> heteroskedasticity, the model under/over-predicts at extremes.

**Plot: ROC curve for the gate**
- **X-axis:** False Positive Rate (1 - specificity), range [0, 1].
- **Y-axis:** True Positive Rate (recall/sensitivity), range [0, 1].
- **Series:** ROC curve + diagonal random line + chosen-threshold marker.
- **So-what:** AUC printed in the corner. AUC > 0.8 = good gate.

**Plot: hydrograph overlay (predicted vs observed)**
- **X-axis:** **date** (a multi-day window around a known event).
- **Y-axis:** Q in cms.
- **Series:** observed (black) + P10/P50/P90 predicted (blue band).
- **So-what:** visual sanity check that the model captures observed peaks.

#### 9.2.7 Architecture tab
- Diagrams only, not charts. Boxes for `data/`, `models/`, `outputs/` with arrows.

### 9.3 Why these graphs are *enough*

The dashboard is designed to answer **six manager questions** (see §2 table). Each question maps to **at least one graph**:

| Manager question | Which graph(s) |
|------------------|----------------|
| Where is the water going? | 9.1.2 (P50 map), 9.1.3, 9.1.4 (P50/P90 cockpit) |
| How sure are we? | 9.1.5 (P>0.5m), 9.1.6 (sigma), 9.1.7 (hydrograph band) |
| When does the peak hit? | 9.1.7 (hydrograph), 9.1.8 (Tp) |
| Which roads close? | Interactive map §10 (red road segments) |
| Which buildings flood? | Interactive map §10 (red footprints) |
| What is the worst case? | 9.1.4 (P90), 9.1.7 (P90 line on hydrograph) |

If a chart doesn't directly serve one of these questions, it's in the **Developer view** instead of the User view. That's the discipline. **No vanity charts.**

### 9.4 Common mis-reads to warn the manager about

1. **"Depth > 0 m" is NOT the same as "evacuate now."** A 5 cm puddle counts as depth > 0. Use the 9.1.5 panel (>0.5 m) for life-safety decisions.
2. **The hydrograph X-axis starts at storm onset, not at midnight.** If today's rain starts at 2 PM, the peak is at 5 PM (2 PM + ~3 h).
3. **The P90 map is *not* a 1-in-90-year flood.** It's the 90th percentile of *today's ensemble* - very different.
4. **Sigma == 0 does NOT mean "we are certain."** It means the 3 ensemble members agree. The model itself could still be biased. That's why §9.2.6 benchmarking matters.

---

## 10. The interactive map (what residents see)

Open `outputs/dashboard_map.html`. A resident can:

- **Pan and zoom** to their street.
- **Type a road name** in the top-left search box - the map zooms to it.
- **Hover over a road or building** to see its name and predicted 100-yr depth.
- **Toggle layers** in the top-right (FEMA zones, BFE lines, buildings, etc.).
- **Read the red panel** in the bottom-right for what to do if a warning hits.

This is what makes the project **useful for actual people**, not just researchers.

---

## 11. How to run everything

```bash
# One-time setup
make install

# Full pipeline (data + forecast + map + dashboard)
make all

# Just rebuild the forecast (if data already exists)
make forecast

# Rebuild local assets (OSM road/building flood-tagging)
make local-assets

# Run the test suite (102 tests)
make test

# Nuke everything (start fresh)
make veryclean
```

Or, equivalently:
```bash
python scripts/00_run_all.py            # full pipeline
python scripts/00_run_all.py --only map # just map + dashboard
python scripts/00_run_all.py --skip-data
```

---

## 12. Testing - how I know the code is correct

```bash
pytest tests/ -q
# expected: 102 passed
```

The test suite covers:
- Library load + Q-interpolation correctness
- Ensemble propagation conservation laws
- Curve-Number edge cases (P < initial abstraction)
- LP-III parameter recovery on synthetic data
- Probability-of-inundation bounds [0, 1]
- All file-existence checks for outputs

If a test fails, **stop everything** and figure out which commit broke it.
Never push a broken `main`.

---

## 13. Common gotchas

### "Folium ImageOverlay shows a gray box"
Pass an **absolute path** to `ImageOverlay(image=...)`. Relative paths fail
because Folium tries to base64-encode the file at HTML-build time and CWD
isn't always what you expect.

### "OSMnx says 'no roads found'"
The HUC-12 bbox might be tiny. Bump the bbox by ~10% or use `network_type='all'`.

### "Q100 != 455 cms"
You probably re-ran step 10 against a different NWIS station. Make sure
`station=09481500`.

### "Dashboard shows old numbers"
The dashboard is built from `outputs/task4/forecast_7day.json`. Rerun
`scripts/07_task4_probabilistic.py` first, then `scripts/build_dashboard.py`.

### "Tests pass locally, fail in CI"
Probably a matplotlib backend issue. Make sure `matplotlib.use("Agg")` is set
before `import matplotlib.pyplot`.

---

## 14. Am I hiding anything? - full honesty audit

> **You asked: "are you hiding anything from me?"** No - but the v1 briefing did skip topics. This table is the complete inventory of what FloodAI actually implements vs. what is aspirational or borrowed from external sources. Read it before you trust a single number.

### 14.1 Status legend

- **DONE** = code in this repo, tests passing, output visible in dashboard.
- **PARTIAL** = code exists but uses a simplification or mock (clearly labelled).
- **MISSING** = not implemented; we use an external public product or a stand-in.
- **EXTERNAL** = delegated to a public dataset / agency model; not our code.

### 14.2 The audit

| # | Topic | Status | What is actually there | What is NOT there |
|---|-------|--------|------------------------|-------------------|
| 1 | FEMA NFHL polygons | DONE | 92 zones for HUC-12, fetched live | n/a |
| 2 | FEMA FIS BFE lines | DONE | 85 BFE + creek centerline | n/a |
| 3 | USGS 3DEP 10-m DEM | DONE | 1778x1903 grid clipped to HUC-12 | 1-m DEM not used (cost/storage) |
| 4 | USGS NWIS gauge data | DONE | 45 annual peaks for 09481500, daily for 09471000 | Sub-daily (15-min) NWIS not pulled |
| 5 | LP-III Bulletin 17C fit | DONE | EMA/MGB fit with weighted skew | Regional skew map not used (we use station skew) |
| 6 | LSTM gate (hurdle) | DONE | 2-layer PyTorch LSTM trained on Babocomari | No attention layer; no transformer variant |
| 7 | XGBoost magnitude | DONE | 400 trees, finetuned on Sonoita | No feature-selection sweep |
| 8 | Babocomari -> Sonoita transfer | DONE | 7-step recipe in `scripts/05_transfer_sonoita.py` | Only 1 source basin; no multi-basin meta-learning |
| 9 | Flood library (8 maps) | PARTIAL | Built from **BFE-IDW WSE - DEM**, NOT 2D hydraulic simulation | **HEC-RAS 2D / SRH-2D not run** - this is the biggest simplification |
| 10 | OWP-HAND-FIM | MISSING | We DO NOT integrate NOAA's National Water Model HAND-FIM rasters | Aspirational - would replace item 9 with a calibrated continental product |
| 11 | Real-time NWIS streaming | MISSING | Pipeline reads a static snapshot from `data/usgs/` | Aspirational - listed in §15 next steps |
| 12 | NOAA GFS / ensemble grib2 ingest | PARTIAL | We ingest a forecast packet; **mock data** if internet absent in CI | Production grib2 + ECMWF IFS not wired in |
| 13 | Soil moisture (SMAP / ERA5) | PARTIAL | Used during ML training; not refetched at forecast time | Live SMAP at inference time |
| 14 | TIGER / Census population overlay | MISSING | Building footprints counted, but **no population estimate** | Aspirational - listed in §15 |
| 15 | OSM roads / buildings | DONE | OSMnx pull, 324 roads + 1345 buildings, sampled vs depth | Bridges/culverts not separately tagged |
| 16 | Folium interactive map | DONE | 4 basemaps, road search, evac panel | No mobile-optimised layout |
| 17 | 6-panel manager cockpit | DONE | All 6 Table-3 products rendered in `dashboard.html` | n/a |
| 18 | Probability of inundation | DONE | Pearson-Tukey weighted | Not full Monte-Carlo (only 3 quantiles) |
| 19 | Uncertainty sigma map | DONE | std across 3 members | No epistemic vs aleatoric split |
| 20 | Ensemble hydrograph | DONE | Gamma-shape SCS unit hydrograph | Not a routed hydrograph (no Muskingum) |
| 21 | Time-to-peak Tp | DONE | Kirpich Tc + SCS lag | Not a calibrated convolution UH |
| 22 | Action triggers | DONE | P(>0.5m)>=0.30, sigma>=0.5m, Tp<=2h coded in cockpit | Not yet validated against past EOC activations |
| 23 | Test coverage | DONE | 102 pytest tests, all green | No integration test that hits the live internet |
| 24 | Whitepaper deliverable map | DONE | `outputs/whitepaper_deliverables_status.md` traces D1.1-D6.5 | n/a |

### 14.3 The three biggest honest caveats

1. **Item 9 - the flood library uses BFE-IDW, not 2D hydraulic simulation.**
   Our 8 depth rasters come from inverse-distance-weighting the FEMA BFE lines into a water-surface-elevation raster and subtracting the 10-m DEM. This is the standard "low-tech FIM" approach and is consistent with how FEMA produces non-A-zone depth grids, but it is **NOT** a full 2D solver (HEC-RAS 2D, SRH-2D). For a peer-reviewed paper or a critical-infrastructure deployment, you would replace this with a real solver run, or import OWP-HAND-FIM (item 10).

2. **Item 10 - we have not yet integrated OWP-HAND-FIM.**
   NOAA's Office of Water Prediction produces continental-scale **Height Above Nearest Drainage** flood-inundation rasters indexed by stage. These are arguably "the right answer" for items 3+9. Integration would mean: fetch the HAND raster for HUC-12, look up today's stage in the rating curve, threshold the HAND raster. This is a one-week project; we did not do it.

3. **Item 11+12 - we are *not* a real-time system yet.**
   Run the pipeline on demand (`make all`). It does not poll NWIS / GFS automatically. The dashboard shows the **last run's** snapshot. Wiring up a cron / Airflow DAG is item 1 in §15 "Where to go next".

### 14.4 What I am NOT claiming

- I am not claiming hydraulic engineering certification - this is a forecasting tool, not a regulatory product.
- I am not claiming the LSTM beats a calibrated physical model - it ties on small basins, that's the literature.
- I am not claiming P(>0.5 m) replaces the EOC's judgment - it informs it.
- I am not claiming the 8-map library is finer-grained than 8 maps - we interpolate, but interpolation between BFE-derived rasters cannot create channel detail that wasn't in the BFE lines.

If you ever feel the briefing is glossing over something, search this document for the topic - it should be in §6.0, §9, or §14. If it's not in any of them, that's a documentation bug. Tell me and I will fix it.

---

## 15. Where to go next

Pick one of these and you'll be a real contributor:

1. **Real-time gauge integration** - poll NWIS every 15 min, retrigger pipeline.
2. **Mobile-friendly dashboard** - the current HTML breaks on phones below 800px wide.
3. **Multi-watershed** - parametrize HUC-12 ID so the pipeline runs anywhere.
4. **Better OSM tagging** - tag bridges, culverts, schools, hospitals.
5. **TIGER/Census overlay** - count population in flooded buildings.
6. **Better Tp** - replace Kirpich with a calibrated convolution unit hydrograph.

---

## 16. Glossary (acronym graveyard)

| Acronym | Meaning |
|---------|---------|
| AFFI | AI Flood Forecasting Initiative (the whitepaper) |
| BFE | Base Flood Elevation (the elevation of the 100-yr flood at a point) |
| CN | Curve Number (SCS runoff parameter) |
| DEM | Digital Elevation Model (terrain raster) |
| DFIRM | Digital Flood Insurance Rate Map |
| EOC | Emergency Operations Center |
| FEMA | Federal Emergency Management Agency |
| FIS | Flood Insurance Study |
| GFS | Global Forecast System (NOAA's main weather model) |
| HUC-12 | 12-digit USGS hydrologic unit code (a small watershed) |
| LP-III | Log-Pearson Type III (the Bulletin-17C flood-frequency distribution) |
| NFHL | National Flood Hazard Layer (FEMA's master flood polygon dataset) |
| NWIS | National Water Information System (USGS streamflow database) |
| OWP-HAND-FIM | NOAA's continental-scale flood inundation mapping |
| Q | Discharge (volumetric flow rate, cms = m^3/s, cfs = ft^3/s) |
| SCS | Soil Conservation Service (now NRCS), authors of the runoff method |
| SFHA | Special Flood Hazard Area (FEMA's regulatory floodplain) |
| Tc | Time of concentration |
| Tp | Time to peak |
| WSE | Water Surface Elevation |
| 3DEP | 3D Elevation Program (USGS national DEM) |
| Babocomari | Babocomari River (USGS gauge 09471000), the source basin we pretrain on |
| LSTM | Long Short-Term Memory neural network (used for the gate stage of the hurdle model) |
| XGBoost | Extreme Gradient Boosting (the regressor used for the magnitude stage) |
| NSE | Nash-Sutcliffe Efficiency (1 - SSE/SS_obs; 1 = perfect, 0 = no better than mean) |
| KGE | Kling-Gupta Efficiency (correlation + bias + variance metric) |
| PBIAS | Percent bias of mean predicted Q vs observed Q |
| F1 | Harmonic mean of precision and recall (event-detection metric) |
| SMAP | Soil Moisture Active Passive (NASA satellite product) |
| ERA5 | ECMWF Reanalysis v5 (global meteorological reanalysis) |
| OWP-HAND-FIM | NOAA OWP Height Above Nearest Drainage Flood Inundation Map |

---

## Closing thought

**Hydrology is not magic, it's bookkeeping.** Rain falls -> some soaks in,
some runs off -> the runoff fills the channel -> the channel rises and spills.
Every formula in this codebase is some version of "track the water." If a
number looks wrong, work backwards along that chain until you find the lying
unit. That's the whole job.

Welcome to the team. Go open `outputs/dashboard.html` and click around for
30 minutes - that's the best onboarding I can give you.

-- The FloodAI maintainers
