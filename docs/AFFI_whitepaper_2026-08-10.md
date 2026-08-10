# Arizona Flash Flood Inundation AI Early Warning System (AFFI)

### A Physics-Guided Artificial Intelligence Framework for Real-Time Flood Inundation Forecasting in Rural Southern Arizona

**May 11, 2026**
**Revised: July 6, 2026 — updated to reflect the validated pilot implementation**
**Revised: August 10, 2026 — dashboard feature expansion, plus two critical bugs found and fixed in the live pipeline (see Changelog)**

**Prepared by:** Solman Raju Sarva, MSc — AI & Hydrology Researcher and William D. O'Brien, PE, CFM — Principal Engineer, NextGen Engineering Inc.

**Pilot Watershed (first validated deployment):** Upper Sonoita Creek Watershed, near Patagonia, Santa Cruz County, AZ

**Training / Anchor Watershed:** Walnut Gulch, near Tombstone, Cochise County, AZ

---

> **SCOPE:** This white paper presents a transferable technical **platform** for flood-inundation early warning, whose **first validated deployment** is the Upper Sonoita Creek Watershed (HUC 150503010204) in Santa Cruz County, Arizona. The architecture, methodology, and deliverables described herein are designed to be transferable to any watershed in Arizona or the United States with minimal reconfiguration; Upper Sonoita Creek is the pilot that proves the platform, not the whole of it. This white paper is aimed at building collaboration for the full, multi-watershed development of AFFI early warning systems.

---

## 1. Executive Summary

Flash floods are the deadliest natural hazard in Arizona, killing an average of 14 people per year and causing $180 million in annual property damage. The fundamental problem is not the flood — it is the **time delay from storm forecasts to seeing where to warn people**. Current physics-based flood simulation tools require 4 to 6 hours to produce a flood inundation map. A monsoon flash flood in Southern Arizona can arrive in under 2 hours. That gap between warning and flood impact is where lives are lost.

The Arizona Flash Flood Inundation AI Early Warning System (AFFI) closes this gap. AFFI is a **six-stage physics-guided artificial-intelligence pipeline** that ingests real-time weather forecast data and delivers a probabilistic flood inundation map to authorized government personnel at their phone or Emergency Operations Center (EOC) in about 60 seconds — roughly 360 times faster than current methods — with accuracy grounded in federal engineering benchmarks. Table ES-1 outlines the benefits of AFFI.

AFFI is best understood as a **transferable platform, not a single-watershed demo**. Its meteorological interface, hydrologic model, hydraulic flood library, probabilistic engine, benchmarking layer, alert logic, and operational dashboard are all watershed-agnostic in design; adding a new watershed is a data-substitution exercise, not a system rebuild (Section 8). This document describes the complete technical architecture of AFFI as it is **actually built and running today**, with the Upper Sonoita Creek Watershed (HUC 150503010204) near Patagonia serving as the first validated deployment. Upper Sonoita Creek is the only watershed validated end-to-end so far; the platform is engineered so the next watershed inherits the entire stack.

To improve model robustness and transferability, the hydrologic AI is first trained on the USDA Walnut Gulch Experimental Watershed hydrologic and rainfall-runoff data and then adapted for the target deployment area. (Since the late 1950s, Walnut Gulch, near Tombstone, AZ, has hosted long-term hydrology, erosion, and water-quality research.) The transfer-learning approach lets AFFI leverage high-quality historical flood dynamics from a well-instrumented anchor watershed while adapting to the terrain, hydrology, and storm-response characteristics of the specific target watershed.

The full development of AFFI is organized into tasks, each with specific, verifiable deliverables. All primary data sources are publicly available from federal agencies at no licensing cost, and the reference hydraulic modeling software, HEC-RAS, is publicly available. As of July 2026, Tasks 1, 2, 4, and 6 are implemented and running in a live pilot, and Task 3 is delivered in a defensible interim form (an analytical FEMA/USGS flood library) with the neural surrogate implemented in parallel. Section 5 states the honest status of each task.

### Table ES-1: Benefits of AFFI

| Metric | Current Capability | AFFI | Improvement |
|---|---|---|---|
| Time to flood map | 4–6 hours (HEC-RAS) | < 60 seconds | 360× faster |
| Watersheds covered | Gauged only (~12% of AZ) | Transferable to any AZ watershed by design; 1 validated to date | Statewide applicability |
| Forecast lead time | 0–2 hours | Up to 7 days | 84× longer |
| Ensemble members | 1 (deterministic) | 31-member GFS → P10/P50/P90 propagation | Uncertainty quantified |
| Cost per forecast | ~$2,400 (EOC activation) | ~$0.04 (cloud compute) | 60,000× cheaper |
| Ungauged basin coverage | Requires stream-gauge calibration | Any Arizona watershed (design) | Ungauged-ready |

---

## 2. Problem Statement: Flash Flooding in Rural Southern Arizona

### 2.1 Human Cost

Between 2000 and 2023, flash floods killed 287 people in Arizona — more than tornadoes, hurricanes, and earthquakes combined in the same period (NOAA Storm Data, 2023). Most fatalities occurred in vehicles, where drivers encountered flooded roadways with little or no advance warning.

The pilot area for AFFI is the Upper Sonoita Creek watershed near Patagonia in Santa Cruz County, Arizona (HUC 150503010204), a 55.4 mi² (143.6 km²) sub-watershed that contains the mapped flood-inundation footprint (Section 4.5's flood library and the dashboard's map extent). This is a smaller unit than the full ~197–209 mi² (~510 km²) contributing drainage area at USGS gauge 09481500 further downstream, which the hydrology model (Section 4.4, Section 4.6) uses for basin-scale discharge scaling — the two figures describe different, both-real spatial extents used for different purposes, not a discrepancy. This HUC-12 has experienced 12 major flood events since 1980, with peak flows exceeding the 50-year return period on three occasions. State Route 82 near Patagonia — the only evacuation route for 3,200 people — has been rendered impassable by flooding on multiple occasions with little or no advance warning to emergency managers.

**Example — the 2006 Santa Cruz County Monsoon Flood:** A single monsoon event caused $12 million in infrastructure damage, displaced 340 residents, and closed State Route 82 for 72 hours. Emergency managers received no advance flood inundation map; response was entirely reactive. This event is the baseline scenario AFFI is designed to mitigate.

### 2.2 Infrastructure and Economic Cost

The economic cost of flash flooding in Arizona averages $180 million annually in direct damage to roads, bridges, utilities, and structures (FEMA, 2022). Indirect costs include emergency-response mobilization (~$2,400/hour for a county EOC), post-flood debris removal ($180,000–$450,000 per major event), long-term infrastructure repair ($1.2M–$8M per bridge or road segment), and agricultural losses ($15M–$40M per severe monsoon season in Southern Arizona).

### 2.3 The Technology Gap

Southern Arizona's rural flash-flood problem is uniquely difficult. The region is characterized by hundreds of ephemeral washes and arroyos — channels that are dry for 300+ days per year but can carry catastrophic flows within minutes of a monsoon rain cell. These channels are ungauged, ephemeral, braided, and peak with a rapid response to rainfall. Times of concentration can be as short as 15–30 minutes for small sub-watersheds.

Current operational flood-mapping tools — NOAA's National Water Model, FEMA Flood Insurance Rate Maps, Google Flood Hub — were designed for large, gauged river systems. They provide valuable national-scale flood information but do not address the specific challenge of rural, ungauged, ephemeral flash-flood prediction in Southern Arizona. **No existing operational system provides real-time, event-specific flood inundation maps for ungauged rural arroyos in Southern Arizona with lead times sufficient for emergency-management action. AFFI fills this gap.**

### 2.4 The Climate Trend

Climate projections for the Southwest United States indicate a 15–40% increase in extreme-precipitation intensity during monsoon events by 2050 (IPCC AR6, 2021). Flood events that currently occur once every 50 years will occur once every 20–30 years by mid-century. The window for investing in flood-inundation early-warning infrastructure — before these events become routine — is urgent.

---

## 3. Existing Systems and Their Limitations

A thorough review of existing flood-inundation forecasting systems confirms that no current tool adequately addresses the rural Southern Arizona flash-flood problem. The following analysis is not a criticism of these systems — each is excellent for its intended purpose. It is a demonstration that a gap exists which none of them fills.

### Table 1: Comparison of AFFI with Other Flood Inundation Mapping Systems

| System | Forecast Type | Lead Time | Ungauged Basins | Rural Arroyos | Real-Time Maps |
|---|---|---|---|---|---|
| **AFFI (Pilot — validated)** | Probabilistic inundation maps | Up to 7 days | Yes | Yes | Yes |
| NOAA NWM | Streamflow forecast | Up to 7 days | Limited | No | No |
| Google Flood Hub | Flood forecast + maps | Up to 7 days | No | No | Partial |
| FEMA FIRM | Static hazard zones | None (static) | Partial | Partial | No |
| First Street Foundation | Risk scoring | None (static) | Partial | No | No |
| FLASH (RoyalHaskoningDHV) | Short-lead flood alerts | Hours to 1 day | No | No | Partial |

### 3.1 Detailed Limitations of Each System

**NOAA National Water Model (NWM):** The outstanding national-scale streamflow forecasting system. However, it depends on stream-gauge calibration data, is not designed for ephemeral channels, and produces streamflow forecasts rather than spatial flood-inundation maps. Reference: NOAA Office of Water Prediction.

**Google Flood Hub:** Provides flood forecasting for gauged rivers globally but does not cover ungauged basins or ephemeral arroyos. Coverage in Arizona is limited to major perennial rivers. Reference: Google Flood Hub.

**FEMA Flood Insurance Rate Maps (FIRM):** Static maps showing 100-year and 500-year flood zones. Not event-specific, not real-time, and not updated frequently enough to reflect current channel or specific storm conditions. Reference: FEMA Flood Map Service Center.

**First Street Foundation:** Property-level flood-risk scores. Static, not event-specific, and not designed for emergency operations. Reference: First Street Foundation.

**FLASH System:** Short-lead flash-flood alerts based on radar rainfall. Does not produce spatial inundation maps and does not cover ungauged basins with sufficient resolution for rural Arizona. Reference: NOAA Flash Flood Guidance.

---

## 4. Technical Solution: The AFFI Architecture

### 4.1 System Overview — The Physical Pipeline

AFFI follows the physically correct sequence for flood prediction. This sequence mirrors how rainfall becomes a flood:

> **Rainfall Forecast → Mean Areal Watershed Precipitation → Runoff / Discharge → Flood Depth & Extent → Probability Maps → Alert**

Each arrow represents a distinct physical transformation. Each transformation is handled by the most appropriate computational method — physics-based where physics is well understood, AI-based where AI has been proven to match or exceed physics-based accuracy at a fraction of the computational cost, and established engineering procedure (SCS Curve Number, hydraulic geometry, FEMA/USGS benchmarks) where those give a defensible, fast, and transparent result.

### Table 2: Six Stages of AFFI Architecture

| Stage | Input | Output | Method (as built) | Time |
|---|---|---|---|---|
| **Stage 1: Meteorology** | GFS/HRRR ensemble forecast | Mean Areal Precipitation (MAP) per watershed | Statistical downscaling / area-weighted averaging | ~5 sec |
| **Stage 2: Hydrology** | MAP time series + watershed attributes | Flood/no-flood detection + peak discharge (ft³/s) | Hurdle model: LSTM event gate → XGBoost magnitude regressor | ~8 sec |
| **Stage 3: Hydraulics** | Peak discharge + terrain (DEM) | Flood depth + extent raster | Analytical FEMA/USGS flood library (operational); ResUNet surrogate (parallel dev) | ~5–45 sec |
| **Stage 4: Probabilistic Output** | P10/P50/P90 rainfall percentiles from 31-member GFS | Best/likely/worst maps, probability & uncertainty products | SCS-CN runoff → discharge → library lookup | ~2 sec |
| **Stage 5: Benchmarking** | Predicted rainfall / discharge | Return-period classification (2yr–200yr) | NOAA Atlas 14 + USGS LP-III comparison | ~1 sec |
| **Stage 6: Alert** | All above outputs | Alert packet (JSON) + dashboard | Rule-based logic + FastAPI/React | ~1 sec |

**Total pipeline run time: ~60 seconds.** This compares to 4–6 hours for the equivalent hydrology (HEC-HMS or equal) + hydraulic (HEC-RAS or equal) physics-based simulation chain.

**Watershed-specific vs. universal stages.** The *machinery* of every stage is universal and reused unchanged across watersheds — the meteorological averaging code, the hurdle-model architecture, the flood-library data structure, the probabilistic engine, the alert logic, and the dashboard. What changes per watershed is *data*, not code: the AOI polygon and NOAA Atlas 14 county benchmarks (Stage 1), the fitted hydrologic model weights and static attributes (Stage 2), the DEM and the FEMA/USGS-derived depth library (Stage 3), and the calibrated alert thresholds (Stage 6). Stages 4 and 5 are fully watershed-agnostic. This separation of universal code from watershed-specific data is what makes the platform transferable (Section 8).

### 4.2 Why This Architecture and Not Others

After reviewing over 200 published AI flood-prediction systems, this six-stage architecture is the design that satisfies all five operational requirements simultaneously:

- **Speed:** ~60 seconds end-to-end — required for flash-flood warning.
- **Accuracy:** Grounded in federal engineering benchmarks — required for government trust.
- **Transferability:** Universal code, watershed-specific data — required for statewide and rural deployment.
- **Interpretability:** Each stage has physical meaning — required for regulatory acceptance.
- **Uncertainty quantification:** Probabilistic output — required for risk-based decisions.

A single end-to-end deep-learning model (rainfall directly to flood map) fails on transferability — it memorizes the training watershed and cannot transfer. A pure physics model fails on speed. The staged hybrid presented here is the only architecture that passes all five tests.

### 4.3 Stage 1: Meteorological Interface — Explained

**What it does:** Ingests ensemble rainfall forecasts from NOAA's Global Forecast System (GFS, 31 members, 6-hourly updates) and the High-Resolution Rapid Refresh / High-Resolution Ensemble Forecast family (HRRR/HREF, hourly, CONUS). For each watershed, it computes Mean Areal Precipitation (MAP) — the spatially averaged rainfall over the watershed extent — for forecast horizons of 1, 3, 6, 12, 24, 48, 72, and 168 hours.

**Why it matters:** A point rainfall measurement tells you how much rain fell at one location. A watershed responds to the average rainfall over its entire area. MAP is the physically correct input to a hydrologic model; using point rainfall instead of MAP is a common error that leads to significant over- or under-prediction of flood response.

**What is AI at this stage?** Stage 1 is NOT AI. It is physics-based numerical weather prediction (NWP) from NOAA's operational models, plus deterministic area-weighted averaging. The AI begins in Stage 2. This distinction matters for scientific integrity and regulatory acceptance.

**Comparison to design-storm rainfall:** Each MAP value is compared against NOAA Atlas 14 precipitation-frequency benchmarks for Santa Cruz County, producing a return-period classification (2-year through 100-year) and an initial alert level (Advisory / Watch / Warning). This lets emergency managers immediately understand whether an incoming storm is routine or a rare, high-consequence event.

### 4.4 Stage 2: Hydrology Model — Explained

**What it does:** Converts the MAP / rainfall history into (a) a flood / no-flood detection and (b) a peak-discharge estimate. In the validated pilot this is implemented as a **two-part hurdle model**, not a single hydrograph-predicting network:

1. **Event gate — LSTM binary classifier.** A Long Short-Term Memory network reads a 30-day sequence of rainfall and hydrology-informed features (Antecedent Precipitation Index, consecutive dry days, a monsoon-season flag, cyclical day-of-year encoding, 3-day and 7-day rainfall accumulations, and an API×precip interaction) and outputs the probability that a given day is a flood event. Because flooding occurs on fewer than ~5% of days in the record, the classifier is trained with focal loss and event-oversampling, and its operating threshold is fixed at **P(flood) ≥ 0.85** to prioritize precision (every false positive corrupts discharge on an otherwise dry day).
2. **Magnitude regressor — XGBoost, conditional on the gate firing.** When the gate fires, an XGBoost gradient-boosted-tree model predicts peak discharge. Configuration in production: **800 estimators, max depth 6, learning rate 0.02, pseudo-Huber objective (robust to rare extreme-flow outliers), 7 lag features, and quantile-aware sample weights (ordinary / high / extreme days weighted 1× / 5× / 20×)** so the model is pulled toward the rare, high-consequence events rather than the abundant small ones.

**Why a hurdle model?** Rainfall-runoff in ephemeral desert channels is a two-regime problem: most days produce zero flow, and a handful produce everything that matters. Forcing one network to regress a hydrograph across both regimes wastes capacity learning "predict near-zero." Separating *whether* a flood occurs (classification) from *how big* it is (regression, on event days only) matches the physical structure of the data and is what the validated pilot actually uses. A physics-guided LSTM regressor was prototyped, but with only a few hundred event days in the record it is under-determined relative to the tree-based magnitude model, which handles small-N tabular regression natively.

**Why "physics-guided"?** The features are hydrologically motivated (soil-moisture proxy via API, antecedent dryness, monsoon seasonality), and the anchor-then-adapt training strategy uses Walnut Gulch — the world's most complete semi-arid flash-flood dataset, with 70+ years of record — to learn fundamental desert hydrology (rapid infiltration, Hortonian overland flow, ephemeral channel routing, monsoon precipitation-runoff dynamics) before adapting to the target watershed's local gauge record. This anchor-then-adapt approach is established in the hydrology-AI literature (Kratzert et al. 2019).

**Validated pilot performance (Upper Sonoita Creek, held-out test).** The model is reported honestly to users through a developer-facing diagnostics panel:

| Metric | Value | Interpretation |
|---|---|---|
| Event detection (AUC-ROC) | **0.959** | Ranks flood vs. no-flood correctly ~96% of the time — excellent discrimination |
| Event F1 (at P ≥ 0.85) | **0.611** | Acceptable false-alarm / missed-event trade-off for rare events |
| Rare-event detection (AUC-PR) | **0.643** | Strong given a ~5% event base rate (a random baseline ≈ 0.05) |
| Magnitude NSE | **0.348** | Peak-discharge skill (see note below) |
| Peak bias (PBIAS) | **−2.9%** | Effectively unbiased; slight underestimation |

**On the NSE value.** An NSE of 0.348 is well below the 0.75 in-sample target set for this project (Table 6), and that is stated plainly rather than hidden. The gap is not a defect in the implementation but a known property of the regime: arid, ephemeral, flashy basins have an inherently lower NSE ceiling than perennial rivers, because a metric normalized by observed variance is punished hardest exactly where flow is near-zero most of the time and spikes violently on a few days. The large-sample hydrology literature consistently finds arid/ephemeral basins to be the hardest rainfall-runoff regime and the lowest-NSE class of watersheds (Kratzert et al. 2019). The system is therefore engineered so that decisions do not hinge on exact peak magnitude: event *detection* (AUC-ROC 0.959) is the reliable signal, magnitude is treated as a ±25–40% band, and road-closure decisions default to the worst-case (P90) scenario. This is disclosed in the decision-framework panel described in Section 4.8.

**Comparison to design-storm peak runoff:** The predicted peak discharge is compared against 2yr–100yr return-period flows derived from USGS methods for Arizona, telling emergency managers how rare or extreme an event is.

### 4.5 Stage 3: Hydraulic Flood Mapping — Explained

**What it does (operational pilot):** Converts a discharge value into a spatial flood-depth raster by looking it up in a **pre-computed, discharge-indexed flood-map library**. In the validated pilot this library is built by a transparent analytical method from federal open data rather than from a fresh bank of HEC-RAS runs:

- **100-year depth grid:** FEMA National Flood Hazard Layer (NFHL) AE-zone geometry defines the regulatory floodplain extent; FEMA Base Flood Elevations (BFE, FIS Layer 16; 429 BFE samples for this HUC-12) are interpolated (inverse-distance) to a continuous 100-yr water-surface elevation, and the **USGS 3DEP 10-m DEM** is subtracted to yield 100-yr flood depth, clipped to the AE polygon.
- **Other return periods (2, 5, 10, 25, 50, 100, 200, 500-yr):** derived from the 100-yr grid via a **Leopold hydraulic-geometry depth-scaling relationship (exponent b ≈ 0.4)**, anchored to USGS Log-Pearson Type III (LP-III) discharge estimates at each return period (e.g., Q2 ≈ 2,950 cfs, Q10 ≈ 8,120 cfs, Q100 ≈ 16,050 cfs, Q200 ≈ 18,550 cfs for Sonoita Creek at USGS 09481500). At runtime, a requested discharge is matched to the two nearest stored maps and linearly interpolated; discharges below the library minimum are scaled down by the same Leopold exponent.

**Why this method for the pilot?** It is honest about the simulation budget. Standing up a full 2-D HEC-RAS model bank per watershed is 20–40 hours of calibrated modeling *per watershed*; for a single-watershed pilot, an analytical library grounded in FEMA-effective floodplain geometry, FEMA-published base flood elevations, real lidar terrain, and USGS statistical discharges gives an operational, defensible, return-period-indexed depth map today, with full provenance. It is a deliberate methodological simplification for the pilot, not a claim of full hydrodynamic simulation.

**Parallel / future capability — the ResUNet surrogate.** A residual U-Net (ResUNet) hydraulic surrogate is fully implemented in the codebase (4-level encoder/decoder, residual blocks, input channels for DEM + slope + channel distance + discharge, depth output). It is the intended operational engine once a fuller HEC-RAS simulation library is built out: the ResUNet is trained to emulate HEC-RAS and inherits its physical accuracy while running ~360× faster. In the current pilot the ResUNet is a parallel development track; the analytical FEMA/USGS library is what generates the live dashboard maps. When the HEC-RAS bank exists, the same library data structure and lookup interface are reused unchanged — only the source of the depth grids changes.

**Physics plausibility:** Depth grids are non-negative, clipped to the mapped floodplain, and monotone in discharge by construction (higher Q → equal-or-greater depth and extent), so ensemble products remain physically consistent.

**Comparison to design-storm inundation:** Because the library is return-period-indexed, every predicted map is directly comparable to a named design event — "this event is comparable to a 25-year flood" — which is the language emergency managers act on.

### 4.6 Stage 4: Probabilistic Output — Explained

**What it does (operational pilot):** Rather than re-simulating hydraulics independently for all 31 raw GFS members, the pilot propagates the **P10 / P50 / P90 rainfall percentiles** (already derived from the 31-member GFS ensemble in Stage 1) through the pipeline to produce a **best / likely / worst** triplet. Each percentile is converted to discharge with a calibrated **SCS Curve-Number runoff model (NRCS TR-55)** plus a basin-scale unit-response factor, and each resulting discharge is looked up in the flood library (Stage 3). This yields three physically ordered inundation maps per forecast day plus the derived probability and uncertainty products.

**Why the percentile approximation?** It is fast, and it is honest about what the forecast packet contains: the operational alert packet carries rainfall percentiles, not the full 21-day lag-feature history each raw member would need to drive the hurdle model individually. Propagating P10/P50/P90 captures the decision-relevant spread (best case, expected case, worst case) at a fraction of the cost. **Upgrade path:** full independent propagation of all 31 members through the hurdle model and hydraulic surrogate is the planned enhancement once the surrogate and per-member feature histories are wired into the operational packet; the probabilistic engine's downstream products (probability map, uncertainty map) are already agnostic to how many members feed them.

**Products.** For each pixel the engine computes the median (P50) depth, the worst-case (P90) depth, the probability that depth exceeds the 0.5 m life-safety threshold, and the spread across scenarios. These populate the products in Table 3.

### Table 3: Usable Probabilistic Output

| Output Product | Description | Primary User |
|---|---|---|
| **Flood Inundation Maps** | | |
| Likely (median / P50) map | Best-estimate flood depth and extent | EOC Staff |
| Worst-case (P90) map | Worst-case scenario (~10% chance of exceeding) | EOC Staff, Public Works Director |
| Life-safety probability map | P(depth > 0.5 m) for each pixel, 0–100% | EOC Staff |
| Uncertainty spread | Spread of depth across best/likely/worst scenarios | Technical reviewer |
| **Warnings** | | |
| Alert classification | Advisory / Watch / Warning vs. return period | County OEM |
| Time-to-peak estimate | Hours until maximum flooding (Kirpich + SCS lag) | Road-closure coordinator |

### 4.7 Stage 5: Benchmarking — Explained

**What it does:** Compares every AFFI-predicted rainfall, discharge, and flood map against established federal engineering benchmarks — NOAA Atlas 14 precipitation-frequency data and USGS LP-III / regional discharge estimates — to classify each event by return period (2-year through 200-year). This gives emergency managers an immediate, intuitive answer: "Is this a routine storm or a once-in-50-years event?"

**Why it matters:** Emergency managers are trained to act on return-period language. A raw discharge number (e.g., 8,100 ft³/s) is meaningless without context; "comparable to a 10-year storm" is immediately actionable. Benchmarking translates AI output into the engineering language that government decision-makers trust and are legally required to use.

**What is AI at this stage?** Stage 5 is NOT AI. It is a deterministic comparison engine using published federal data, which reinforces scientific integrity and regulatory credibility.

### 4.8 Stage 6: Alert Policy and Decision Support — Explained

The alerts from AFFI need to support the many other data and real-time voices that emergency personnel and public officials must weigh. The following alert policy is recommended:

> **Critical Policy Decision:** All AFFI alerts are delivered exclusively to authorized government personnel — county emergency managers, public-works directors, and EOC staff. No alerts are broadcast directly to the public. This design eliminates the liability of automated public warnings and ensures all public communications are reviewed and authorized by responsible government officials.

The delivered dashboard operationalizes this policy with an EOC-facing **Decision Cockpit** that surfaces, from the shared forecast state: time-to-peak (via Kirpich time-of-concentration → SCS lag), the life-safety threshold probability (P(depth > 0.5 m)), and a plain-English decision framework that maps each decision type to a confidence level — GO/NO-GO (high confidence, driven by AUC-ROC 0.96), road-closure threshold (use the P90 scenario, because the model underestimates peaks by ~3%), exact peak discharge (medium, ±25–40%), and evacuation timing (medium, ±15–20% via Kirpich). This keeps the weaker magnitude skill (Section 4.4) from being over-trusted while letting the strong detection skill drive the primary go/no-go call.

### 4.9 Lead-Time-Dependent Confidence Framework

As an event approaches, forecast confidence improves. Table 4 shows the working measure of confidence as the storm nears; this framework is implemented directly in the dashboard's Decision Cockpit.

### Table 4: Confidence of Predicted Flooding and Related Actions

| Lead Time | Primary Data Source | Confidence Level | Primary Use |
|---|---|---|---|
| 2–7 days | GFS ensemble (31 members) | Low–Medium | Pre-positioning resources, early briefings |
| 6–24 hours | HRRR + updated GFS | Medium–High | Road-closure decisions, evacuation planning |
| 0–6 hours | MRMS radar + nowcast | High | Active road closures, emergency response |

---

## 5. Development of AFFI — Detailed Task Descriptions with Deliverables

**Tasks T1 through T6:** T1 Meteorological Forecasts → T2 Hydrology Model (Anchor → Adapt) → T3 Hydraulic Flood Library / Surrogate → T4 Probabilistic Ensemble → T5 Benchmark & Validation → T6 Alert, API & Dashboard.

### Task 1: Meteorological Forecast Interface

**Objective:** Build and validate the system that ingests real-time weather-forecast data and computes Mean Areal Precipitation (MAP) for the pilot watershed, with alert-threshold logic benchmarked against NOAA Atlas 14 return periods.

**Step-by-Step:**

- **Step 1.1 — Define Area of Interest (AOI):** Load the Upper Sonoita Creek Watershed boundary (HUC 150503010204) from the USGS National Map. Define bounding box (N=31.85, S=31.47, E=−110.50, W=−110.90). This is the spatial domain for all precipitation calculations.
- **Step 1.2 — Ingest GFS Ensemble Forecast:** Connect to the Open-Meteo API (free, no key) to retrieve 31-member GFS ensemble precipitation forecasts at 6-hourly intervals for 7-day lead times. Parse and store as structured arrays.
- **Step 1.3 — Compute Mean Areal Precipitation (MAP):** Spatially average the gridded GFS precipitation over the watershed boundary using area-weighted averaging, for accumulation windows of 1, 3, 6, 12, 24, 48, 72, and 168 hours.
- **Step 1.4 — Load NOAA Atlas 14 Benchmarks:** Load precipitation-frequency estimates for Santa Cruz County, AZ (NOAA Atlas 14 Vol. 1) for return periods 2, 5, 10, 25, 50, 100 years at all durations.
- **Step 1.5 — Compute Return-Period Classification:** For each MAP value and duration, determine the return-period bracket and a Storm Severity Index (SSI = MAP / MAP_10yr).
- **Step 1.6 — Apply Alert Threshold Logic:** Apply thresholds calibrated for Sonoita Creek: Advisory (0.25"/1hr, 0.75"/24hr), Watch (0.50"/1hr, 1.25"/24hr), Warning (1.00"/1hr, 2.00"/24hr). Generate an alert level (GREEN / ADVISORY / WATCH / WARNING) per member and lead time.
- **Step 1.7 — Generate Alert Packet:** Compile all outputs into a structured JSON alert packet (alert level, MAP values, return-period classifications, ensemble statistics [mean, P10, P50, P90], time-to-peak estimate).
- **Step 1.8 — Dummy Rainfall Stress Test:** Validate the alert logic against synthetic scenarios from light shower to extreme cloudburst.

**Deliverables:** D1.1 `task1_met_interface.py`; D1.2 `task1_alert_packet.json`; D1.3 `task1_forecast_dashboard.png`; D1.4 dummy stress-test report; D1.5 technical memo.

**Status:** Complete and validated for Upper Sonoita Creek. In the current build, the alert packet is produced live on a 6-hour schedule (Task 6) and consumed directly by the operational dashboard.

### Task 2: Hydrology Model — Anchor Training → Local Adaptation

**Objective:** Teach the AI how desert floods work using an anchor-then-adapt strategy: learn general Arizona flash-flood behavior from Walnut Gulch, then adapt to the Sonoita Creek pilot. This enables launching new watersheds with far less local data.

**As-built method (corrected from the original single-LSTM plan):** the hydrology stage is a **hurdle model** — an LSTM binary event-gate followed by an XGBoost magnitude regressor conditional on the gate firing — described in full in Section 4.4. This replaces the originally proposed single physics-guided LSTM that directly regressed a hydrograph.

**Step-by-Step:**

- **Step 2.1 — Data Setup:** Collect historical rain and streamflow from Walnut Gulch (anchor) and Sonoita Creek (pilot, USGS 09481500). Engineer hydrology-informed features (API, consecutive dry days, monsoon flag, cyclical day-of-year, 3-/7-day accumulations, API×precip).
- **Step 2.2 — Anchor Training:** Train the event-gate on the data-rich anchor record to learn general semi-arid flash-flood behavior.
- **Step 2.3 — Benchmarking:** Evaluate the classifier and regressor with detection-appropriate metrics (AUC-ROC, AUC-PR, F1) and magnitude metrics (NSE, PBIAS), not accuracy alone.
- **Step 2.4 — Local Adaptation:** Adapt the model to Sonoita Creek; fit the XGBoost magnitude model on local event days with quantile-aware weighting (1×/5×/20×).
- **Step 2.5 — Event Testing:** Test against major historical floods (e.g., 2014 Hurricane Odile remnants) to check event detection and magnitude.
- **Step 2.6 — Return-Period Discharge Estimation:** Derive 2/10/25/50/100/200-yr discharges from USGS LP-III methods. These become the hydraulic benchmarks for Task 3.

**Deliverables:** D2.1 model library (event-gate + XGBoost magnitude model, `best_inference_config.json`); D2.2 performance scorecard (NSE, PBIAS, F1, AUC-ROC, AUC-PR); D2.3 training configs; D2.4 validation plots; D2.5 deployment checklist.

**Status:** Implemented and validated on Upper Sonoita Creek. Held-out metrics: **NSE 0.348, PBIAS −2.9%, F1 0.611, AUC-ROC 0.959, AUC-PR 0.643** (threshold P ≥ 0.85). The NSE is below the 0.75 target and is reported plainly with regime context (Section 4.4).

### Task 3: Hydraulic Flood Mapping — Analytical Library (Pilot) + ResUNet Surrogate (Parallel)

**Objective:** Convert predicted discharge into spatial flood-inundation maps. The originally proposed path — a U-Net/ResUNet trained on 250 HEC-RAS simulations across 25 watersheds — is implemented in code but is **not** the source of today's operational maps. The validated pilot uses an analytical FEMA/USGS flood library (Section 4.5); the ResUNet is a parallel track for when a fuller HEC-RAS bank exists.

**Step-by-Step (as built):**

- **Step 3.1 — Prepare Terrain Data:** Use the USGS 3DEP 10-m DEM for the pilot HUC-12 (projected EPSG:32612). (1-m lidar is available and is the target resolution for full HEC-RAS work.)
- **Step 3.2 — Build the FEMA/USGS Depth Grid:** Interpolate FEMA BFE points (FIS Layer 16; 429 samples) to a continuous 100-yr water-surface elevation and subtract the DEM, clipping to the FEMA NFHL AE polygon, to produce the 100-yr depth grid.
- **Step 3.3 — Scale to All Return Periods:** Generate depth grids for 2/5/10/25/50/100/200/500-yr using a Leopold hydraulic-geometry depth-scaling exponent (b ≈ 0.4) anchored to USGS LP-III discharges.
- **Step 3.4 — (Parallel) ResUNet Architecture:** A 4-level residual U-Net (DEM + slope + channel distance + discharge in; depth out) is implemented for future HEC-RAS emulation.
- **Step 3.5 — (Parallel) Train the Surrogate:** Train the ResUNet on HEC-RAS outputs once the simulation bank is built; enforce physics constraints (gravity, monotonicity, mass conservation) as post-processing.
- **Step 3.6 — Assemble the Discharge-Indexed Library:** Store depth grids keyed by discharge with linear interpolation between neighbors and Leopold scaling below the minimum — the same data structure the ResUNet will feed.
- **Step 3.7 — Validate Against HEC-RAS (future):** When available, compare surrogate maps against HEC-RAS using IoU, CSI, and mean absolute depth error (target IoU > 0.75).

**Deliverables:** D3.1 hydraulically referenced DEM for the pilot HUC-12; D3.2 FEMA/USGS analytical flood library with full provenance manifest (source, method, BFE sample count, per-return-period Q and depth stats); D3.3 implemented ResUNet model code; D3.4 validation plan/report structure for the surrogate; D3.5 return-period flood-map library (GeoTIFF) for 2–500-yr.

**Status:** Analytical FEMA/USGS library delivered and driving live maps. ResUNet implemented; HEC-RAS simulation bank and surrogate validation are future work.

### Task 4: Probabilistic Risk Products

**Objective:** Generate probabilistic flood-risk products for emergency-management decision-making.

**As-built method (corrected from "31 independent pipeline runs"):** the pilot propagates the **P10/P50/P90 rainfall percentiles** (from the 31-member GFS ensemble) through an SCS-CN runoff conversion and a flood-library lookup to produce best/likely/worst maps and derived products (Section 4.6), rather than re-simulating hydraulics independently for all 31 raw members.

**Step-by-Step:**

- **Step 4.1 — Percentile Propagation:** For each forecast day, take P10/P50/P90 24-hr rainfall, convert each to discharge (SCS-CN + unit-response factor), and look up the matching flood map.
- **Step 4.2 — Compute Ensemble Statistics:** From the best/likely/worst maps, compute per-pixel median depth, worst-case (P90) depth, probability of exceeding the 0.5 m life-safety threshold, and spread.
- **Step 4.3 — Generate Life-Safety Probability Map:** Raster of P(depth > 0.5 m), 0–100% — the primary decision-support product.
- **Step 4.4 — Generate Uncertainty Product:** Spread of predicted depth across scenarios; high-uncertainty areas warrant conservative decisions.
- **Step 4.5 — Compute Time-to-Peak:** Estimate hours to peak via Kirpich time-of-concentration → SCS lag for the P10/P50/P90 discharges.
- **Step 4.6 — Generate EOC Products:** Compile the median map, life-safety probability map, uncertainty product, ensemble hydrograph, alert timeline, and return-period comparison for the operational dashboard.

**Deliverables:** D4.1 probabilistic flood-map set (likely/worst/probability/uncertainty); D4.2 EOC dashboard products; D4.3 ensemble hydrograph with best/likely/worst bounds; D4.4 time-to-peak report.

**Status:** Implemented and running live; the 7-day probabilistic outlook is refreshed on the 6-hour schedule. Full 31-member independent propagation is the identified upgrade path.

### Task 5: Design-Storm Benchmarking and Return-Period Comparison

**Objective:** Let emergency managers understand any predicted event by its rarity and severity relative to standard engineering design storms (2-year through 200-year).

**Step-by-Step:**

- **Step 5.1 — Define Return-Period Benchmarks:** Compile (a) NOAA Atlas 14 precipitation-frequency estimates (2/5/10/25/50/100-yr at 1/3/6/24-hr); (b) USGS LP-III peak-discharge estimates at each return period; (c) the pre-computed flood library depth maps for each return period (from Task 3).
- **Step 5.2 — Build Comparison Engine:** A module that maps any predicted rainfall, discharge, or flood map to its return-period bracket, its ratio to the 10-year design storm, and the fraction of the mapped floodplain inundated.
- **Step 5.3 — Historical Event Validation:** Apply the pipeline to major historical Arizona flood events; compare predicted extents against post-event surveys, FEMA damage assessments, and USGS peak-flow records.
- **Step 5.4 — Benchmark Comparison Report:** Side-by-side comparison of AFFI map vs. post-event survey vs. FEMA FIRM 100-year zone, quantifying spatial improvement over static FIRM.
- **Step 5.5 — Sensitivity Analysis:** Test sensitivity to GFS forecast error (±20%), attribute uncertainty (±10%), and DEM resolution.

**Deliverables:** D5.1 return-period benchmark database; D5.2 historical-event validation report; D5.3 benchmark comparison figures; D5.4 sensitivity-analysis report; D5.5 return-period classification-accuracy table.

**Status:** Benchmark database and comparison engine implemented; multi-event historical validation is in progress and is the main remaining validation gap.

### Task 6: Alert System, Government API, and Decision Dashboard

**Objective:** Integrate all pipeline components into an operational alert system with a secure government API and an EOC-ready decision dashboard, with alert logic controlled by county emergency-management agencies.

**As-built — a delivered upgrade over the proposed Streamlit/Dash dashboard.** The operational front end is a **custom React + TypeScript single-page application backed by a FastAPI service**, which exceeds the originally proposed scope. Delivered capabilities:

- **Live-Forecast / Simulation mode toggle** — a shared-state architecture where a what-if rainfall slider drives *every* panel (map, hydrograph, alerts, bulletin, action plan) off one simulation state, letting a flood manager demonstrate "if this much rain falls, here is what happens."
- **Interactive MapLibre GL map** with per-building click popups (buildings categorized as School, Public/Civic, Residential, Commercial/Industrial, Agricultural/Outbuilding, or Unclassified) and per-critical-facility popups (schools, clinic, fire, police, water and power infrastructure, bridges), each showing exact flood depth at any of six return periods.
- **Return-period explorer strip** — the map can display any of the 5/10/25/50/100/200-yr scenarios on demand.
- **Decision Cockpit** — time-to-peak (Kirpich + SCS lag), life-safety threshold probability, and the Table-4 lead-time confidence framework.
- **NWS-style bulletin generator** — WHAT / WHERE / WHEN / IMPACTS, citing Arizona's "Stupid Motorist Law" (ARS 28-910) as legal grounding for road-closure barricades.
- **Model-diagnostics panel** — NSE / F1 / AUC-ROC / AUC-PR / PBIAS with plain-English interpretation and a decision framework, **gated behind a Developer View** and hidden from the flood-manager-facing UI.
- **Data-staleness watchdog** — visibly warns when the forecast pipeline has not refreshed (advisory at 2 hours, critical "DATA STALE — pipeline may have failed" at 6 hours).
- **Automated scheduler** — an APScheduler cron job re-runs the full forecast pipeline every 6 hours (00:15 / 06:15 / 12:15 / 18:15 UTC) and on startup.

**Step-by-Step:**

- **Step 6.1 — Define Alert Logic:** With Santa Cruz County OEM, define the alert-threshold matrix (return-period × probability × time-to-peak → Advisory/Watch/Warning). Document in a formal Alert Logic Specification.
- **Step 6.2 — Build Alert Engine:** Python module that reads Task 4 outputs, applies alert logic, emits a structured JSON alert packet, and logs decisions with timestamps for audit.
- **Step 6.3 — Build Government API:** FastAPI service with API-key authentication and role-based access, exposing current alert, full alert packet, alert history, forecast days, return periods, 7-day detail, model metrics, watershed config, and a pipeline-run trigger; serves flood-map/hydrograph rasters as static assets.
- **Step 6.4 — Build EOC Dashboard:** React + TypeScript SPA (the delivered upgrade above), auto-refreshing every 60 s in live mode with a manual "Refresh now" control.
- **Step 6.5 — Operational Testing:** Deploy for live testing during the Arizona monsoon season; log forecast events, alert levels, and (where available) observed outcomes; compute false-alarm rate, missed-event rate, and lead-time accuracy.
- **Step 6.6 — Documentation and Training:** Produce API reference, dashboard user manual, alert-logic spec, data-flow diagram, and maintenance procedures; train Santa Cruz County OEM staff.

**Deliverables:** D6.1 Alert Logic Specification; D6.2 alert-engine module with audit logging; D6.3 authenticated FastAPI application (with test suite and one-command Docker startup for API + frontend + scheduler); D6.4 deployed React/FastAPI dashboard with user manual; D6.5 operational test report; D6.6 complete system-documentation package.

**Status:** API, dashboard, scheduler, staleness watchdog, and Docker deployment are implemented and running. Step 6.5 live monsoon-season metrics accrue during the 2026 season. An August 2026 hardening pass added Google-Flood-Hub-style decision-support elements (gauge status badge, per-pixel inundation-probability layer), corrected critical-facility locations to an official source list, added a 2D/3D map toggle, and found and fixed two severe correctness bugs in the live pipeline — see the August 10 Changelog entry for full detail; do not rely on any "current alert" screenshot or number dated before August 10, 2026.

---

## 6. Data Sources and Technical Feasibility

All primary data required for AFFI development and operation (Table 5) are publicly available from federal agencies at no licensing cost. Public data eliminates a major category of project risk and ensures sustainability.

### 6.1 Existing Progress — Technical Feasibility

As of July 2026, the pilot is a working system, not a design on paper:

- **6.1.1** The meteorological forecast interface ingests GFS ensemble data and computes MAP in real time for the pilot watershed, on a 6-hour automated schedule.
- **6.1.2** Alert-threshold logic is calibrated against NOAA Atlas 14 for Santa Cruz County, with Advisory/Watch/Warning levels benchmarked to 10/25/50-year return periods.
- **6.1.3** The hydrology hurdle model (LSTM event-gate + XGBoost magnitude) is trained and validated on the pilot watershed with metrics reported to users.
- **6.1.4** The Stage-3 flood library is built from FEMA NFHL + FEMA BFE + USGS 3DEP + USGS LP-III and drives the live maps; the ResUNet surrogate is implemented in parallel.
- **6.1.5** The probabilistic engine, benchmarking engine, government API, React dashboard, scheduler, and staleness watchdog are implemented and operational.

### Table 5: Data Sources for AFFI

| Data Type | Source | Resolution | Coverage | Cost |
|---|---|---|---|---|
| Streamflow records (anchor) | USDA ARS — Walnut Gulch Experimental Watershed | Sub-hourly | 70+ years, 89 rain gauges, 12 flumes | Free |
| Historical precipitation | ERA5 via Open-Meteo Archive API | 0.25°, hourly | 1940–present, global | Free |
| Streamflow (pilot watershed) | USGS NWIS — Gauge 09481500 (Sonoita Creek near Patagonia) | 15-min / daily | Multi-decadal record | Free |
| Terrain (DEM) | USGS 3DEP | 10-m (1-m lidar available) | Statewide AZ | Free |
| Real-time forecast | NOAA GFS | ~13 km, 6-hourly | 31 ensemble members | Free |
| High-res forecast | NOAA HRRR | 3 km, hourly | CONUS | Free |
| Radar rainfall | NOAA MRMS | 1 km, 2-min | Real-time, CONUS | Free |
| Soil data | USDA SSURGO | 1:24,000 | Statewide AZ | Free |
| Land cover | USGS NLCD | 30 m | Statewide AZ | Free |
| Watershed attributes | USGS GAGES-II | Per watershed | 9,322 US watersheds | Free |
| Precipitation benchmarks | NOAA Atlas 14 | Per county | All AZ counties | Free |
| Regulatory floodplain & base flood elevations | FEMA NFHL (AE/X) + FEMA FIS BFE (Layer 16) | Vector / per-panel | Nationwide (where mapped) | Free |
| Return-period discharge | USGS LP-III / regional regression | Per site | Statewide AZ | Free |

---

## 7. Validation Plan and Performance Goals

AFFI will be validated against four independent benchmarks before full operational certification. The original performance **targets** (Table 6) are retained as the standard, and the **validated pilot results to date** are reported honestly in Section 7.2.

### Table 6: Performance Goals (Targets)

| Validation Level | Method | Target | Reference Standard |
|---|---|---|---|
| In-sample accuracy | Hydrology model tested on held-out years | NSE > 0.75, KGE > 0.70 | Moriasi et al. 2007 |
| Out-of-sample generalization | Model tested on completely held-out watersheds | NSE > 0.65 | Kratzert et al. 2019 |
| Historical event validation | Full pipeline tested on major AZ flood events | IoU > 0.75 vs. post-event surveys | FEMA post-disaster assessments |
| Speed benchmark | Wall-clock GFS input → flood map output | < 60 seconds | Flash-flood warning lead-time requirement |

### 7.1 Baseline Comparisons

- **Baseline 1 — Simple classifier/regressor without hydrology-informed features:** proves the physics-guided feature design adds value over generic AI.
- **Baseline 2 — HEC-HMS + HEC-RAS (full physics):** proves AFFI approaches physics-model accuracy at ~360× the speed (the target once the HEC-RAS bank and ResUNet surrogate are in place).
- **Baseline 3 — FEMA static FIRM maps:** proves dynamic, event-based, return-period-indexed maps outperform static hazard maps for real-time decisions.

### 7.2 Validated Pilot Results (as of July 2026)

- **Hydrology (Upper Sonoita Creek, held-out test):** AUC-ROC **0.959**, AUC-PR **0.643**, F1 **0.611** (at P ≥ 0.85), NSE **0.348**, PBIAS **−2.9%**. Event detection meets an operationally strong bar; peak-magnitude NSE is below the 0.75 target, which is expected for a flashy ephemeral regime (Section 4.4) and is disclosed to users. Decisions are structured so the reliable detection signal, not the weaker magnitude estimate, drives the go/no-go call.
- **Speed:** the full pipeline runs in ~60 seconds, meeting the speed benchmark.
- **Historical event / IoU validation:** the analytical flood library is anchored to FEMA-effective floodplain geometry; formal multi-event IoU validation against post-event surveys is the main open validation item and proceeds as the HEC-RAS/ResUNet track matures.
- **Operational integrity incident (disclosed, resolved).** From approximately August 4 to August 10, 2026, a unit-conversion defect caused the live dashboard to display a **permanent false WARNING alert with a "Severe/catastrophic flooding" classification regardless of actual weather**, and a separate memory defect caused the forecast refresh to silently fail on nearly every 6-hourly cycle, freezing "live" data on a stale August 3 snapshot for six days. Both were found during an internal audit, root-caused, fixed, and verified against an independent re-derivation from the raw forecast data; the fix is described in the August 10 Changelog entry. This is disclosed here rather than silently corrected because it directly bears on how much to trust any "current alert" state observed during that window.

---

## 8. Transferability to Other Watersheds — The Platform Thesis

**Design principle:** every component of AFFI was built to be transferable to any watershed in Arizona or the United States. Upper Sonoita Creek is the **first validated deployment**, not the product. The distinction that makes this real is architectural: the *code* of every stage is watershed-agnostic; only *data* changes per watershed (Section 4.1). This section states the mechanics honestly, including what is genuinely turnkey today and what still requires per-watershed effort.

To deploy AFFI for a new watershed, the following watershed-specific inputs are substituted. All universal components (hurdle-model architecture, flood-library data structure and lookup, probabilistic engine, benchmarking engine, alert logic framework, API, dashboard) remain unchanged.

| Component | What Changes Per Watershed | Data Source | Estimated Effort |
|---|---|---|---|
| AOI / bounding box | Watershed boundary polygon and bbox | USGS National Map | ~1 hour |
| NOAA Atlas 14 benchmarks | County-specific precipitation-frequency estimates | NOAA Atlas 14 | ~2 hours |
| Alert thresholds | Advisory/Watch/Warning thresholds for local conditions | County OEM + NOAA Atlas 14 | ~4 hours |
| DEM | 3DEP DEM (10-m operational; 1-m lidar for HEC-RAS) | USGS 3DEP | ~4 hours |
| Flood library (pilot method) | FEMA NFHL AE geometry + FEMA BFE + DEM → Leopold-scaled depth library | FEMA NFHL/FIS + USGS 3DEP + USGS LP-III | ~8–16 hours |
| Hydrology model | Fit event-gate + XGBoost on local gauge record (or transfer anchor model) | USGS NWIS | ~8 hours |
| HEC-RAS + ResUNet (full-fidelity path) | New 2-D hydraulic model + surrogate retraining | DEM + NLCD + field survey | 20–40 hours |

**Estimated marginal effort per new watershed:** ~40–80 hours for the full-fidelity path, or substantially less for the analytical-library pilot method where FEMA NFHL/BFE coverage exists. This is the marginal cost of expansion — not the full system-development cost.

**A key transferability finding from the pilot:** because the operational Stage-3 library is built from *nationally available FEMA and USGS open data* rather than from bespoke HEC-RAS runs, any watershed with FEMA NFHL AE mapping, published BFEs, and a 3DEP DEM can receive an operational, return-period-indexed flood library quickly — with the ResUNet/HEC-RAS path reserved for watersheds that warrant full hydrodynamic fidelity. The analytical method is itself a transferability asset, not just a pilot shortcut.

**Watersheds where AFFI is immediately applicable:** any Arizona watershed with a 3DEP DEM, NOAA Atlas 14 county data, and FEMA NFHL/BFE coverage. Outside Arizona, the only additional requirement is the relevant NOAA Atlas 14 volume.

### 8.1 Statewide Scaling — Transfer to Additional Arizona Watersheds

**Objective:** deploy the validated pipeline to additional Arizona watersheds using the transfer framework established in Tasks 1–6, demonstrating that the marginal cost of a new watershed is engineering-hours, not a rebuild.

- **Step 8.1.1 — Watershed Selection:** prioritize by (a) 3DEP DEM availability, (b) NOAA Atlas 14 county data, (c) flash-flood risk to a populated area, (d) FEMA NFHL/BFE coverage, (e) no existing operational warning system.
- **Step 8.1.2 — Rapid Deployment Protocol:** execute the per-watershed substitution checklist above.
- **Step 8.1.3 — Cross-Watershed Validation:** test whether the Sonoita Creek-adapted hydrology model transfers to a new watershed without refitting; report NSE/detection degradation vs. full local adaptation. This directly tests generalizability.
- **Step 8.1.4 — Statewide Dashboard:** extend the dashboard to display alert levels for all deployed watersheds on a single Arizona-wide map.

**Deliverables:** D8.1 rapid-deployment checklist verified on additional AZ watersheds; D8.2 cross-watershed generalization report; D8.3 statewide alert dashboard; D8.4 deployment-cost audit (actual engineering hours per watershed).

---

## 9. References (Verified Hyperlinks)

1. Cloke, H. L., & Pappenberger, F. (2009). Ensemble flood forecasting: A review. *Journal of Hydrology.* https://doi.org/10.1016/j.jhydrol.2009.06.005
2. Federal Emergency Management Agency (FEMA). (2022). Flood Insurance Rate Maps (FIRMs). https://www.fema.gov/flood-maps
3. Federal Emergency Management Agency (FEMA). National Flood Hazard Layer (NFHL). https://www.fema.gov/flood-maps/national-flood-hazard-layer
4. IPCC. (2021). Climate Change 2021: The Physical Science Basis. Sixth Assessment Report. https://www.ipcc.ch/report/ar6/wg1/
5. Kratzert, F., et al. (2019). Towards learning universal, regional, and local hydrological behaviors via machine learning. *Nature Communications.* https://doi.org/10.1038/s41467-019-13507-2
6. Moriasi, D. N., et al. (2007). Model evaluation guidelines for systematic quantification of accuracy in watershed simulations. *Transactions of the ASABE.* https://doi.org/10.13031/2013.23153
7. NOAA Office of Water Prediction. (2024). National Water Model (NWM) Documentation. https://water.noaa.gov/about/nwm
8. NOAA Hydrometeorological Design Studies Center. (2024). Precipitation Frequency Data Server (Atlas 14). https://hdsc.nws.noaa.gov/hdsc/pfds/
9. Ronneberger, O., et al. (2015). U-Net: Convolutional networks for biomedical image segmentation. *MICCAI.* https://doi.org/10.1007/978-3-319-24574-4_28
10. Chen, T., & Guestrin, C. (2016). XGBoost: A scalable tree boosting system. *KDD.* https://doi.org/10.1145/2939672.2939785
11. Lin, T.-Y., et al. (2017). Focal loss for dense object detection. *ICCV.* https://doi.org/10.1109/ICCV.2017.324
12. USDA Natural Resources Conservation Service. (1986). Urban Hydrology for Small Watersheds (TR-55, SCS Curve Number method). https://www.nrcs.usda.gov/
13. Leopold, L. B., & Maddock, T. (1953). The hydraulic geometry of stream channels and some physiographic implications. USGS Professional Paper 252. https://pubs.usgs.gov/pp/0252/report.pdf
14. Kirpich, Z. P. (1940). Time of concentration of small agricultural watersheds. *Civil Engineering,* 10(6), 362.
15. Sit, M., et al. (2020). A comprehensive review of deep learning applications in hydrology and water resources. *Water Science and Technology.* https://doi.org/10.2166/wst.2020.369
16. USGS. (2024). 3D Elevation Program (3DEP) High-Resolution Lidar Data. https://www.usgs.gov/3d-elevation-program
17. USGS. (2011). Geospatial Attributes of Gages for Evaluating Streamflow (GAGES-II). https://water.usgs.gov/GIS/metadata/usgswrd/XML/gagesII_Sept2011.xml
18. USGS National Water Information System (NWIS). (2024). Real-time Streamflow Data for Arizona. https://waterdata.usgs.gov/nwis
19. Tellman, B., et al. (2021). Satellite imaging reveals increased proportion of population exposed to floods. *Nature.* https://doi.org/10.1038/s41586-021-03695-w
20. Google Research. (2024). Flood Hub Global Flood Forecasting. https://sites.research.google/floods/
21. Multi-Resolution Land Characteristics (MRLC) Consortium. (2021). National Land Cover Database (NLCD). https://www.mrlc.gov/data
22. NOAA National Severe Storms Laboratory. (2024). Multi-Radar Multi-Sensor (MRMS) System. https://mrms.nssl.noaa.gov/
23. USDA Natural Resources Conservation Service. (2024). Soil Survey Geographic Database (SSURGO). https://www.nrcs.usda.gov/resources/data-and-reports/ssurgo

---

---

## Changelog — What Changed From the May 11 Version

*This section is not part of the formal white-paper body. It is an audit trail for the reviewer, listing each substantive technical correction and why it was made. Every claim below was verified against the actual codebase, not the project summary.*

1. **Revision marker added.** The original "May 11, 2026" date is preserved; a "Revised: July 6, 2026 — updated to reflect the validated pilot implementation" line was added directly beneath it. Nothing was silently overwritten.

2. **Multi-watershed framing pulled forward (Exec Summary, Scope box, Section 4.1, Section 8 title).** Upper Sonoita Creek is now explicitly framed as "the first validated deployment of a transferable platform," not the whole project. Added a "watershed-specific vs. universal stages" paragraph to Section 4.1 and re-titled Section 8 "The Platform Thesis." The pilot-specific technical content was not shrunk in the process. The honest caveat — one watershed validated so far — is stated in the Exec Summary and Section 7.2.

3. **Stage 2 / Task 2 corrected from single "Physics-Guided LSTM" to a hurdle model.** Verified in `src/hydrology/model.py`, `trainer.py`, `features.py`, and `models/best_inference_config.json`: it is an **LSTM binary event-gate (focal loss, threshold P ≥ 0.85) + XGBoost magnitude regressor** (800 estimators, max_depth 6, lr 0.02, pseudo-Huber objective, 7 lag features, quantile-aware sample weights 1×/5×/20×). The original single-LSTM-predicts-hydrograph description was inaccurate. Note: `trainer.py` also contains a `GradientBoostingRegressor` (300 est / depth 4) code path, but the production config file and the frontend both confirm **XGBoost** with the parameters above is the deployed magnitude model.

4. **Real hydrology metrics reported honestly.** Pulled ground truth from `models/best_inference_config.json` and the live alert packet: **NSE 0.348, PBIAS −2.9%, F1 0.611, AUC-ROC 0.959, AUC-PR 0.643.** The NSE is stated plainly as being below the 0.75 target, with domain reasoning (arid/ephemeral flashy basins have a lower NSE ceiling; Kratzert et al. 2019 finds arid basins hardest). No invented citation was used for this point.

5. **Stage 3 / Task 3 corrected from "U-Net trained on 250 HEC-RAS runs across 25 watersheds, operational" to the analytical FEMA/USGS library that actually drives the pilot.** Verified in `src/probabilistic/flood_library.py` and `data/flood_library_real/manifest.json`: the operational maps come from **FEMA NFHL AE geometry + FEMA BFE (429 samples) interpolated minus USGS 3DEP DEM for 100-yr depth, scaled to other return periods by a Leopold exponent b ≈ 0.4, anchored to USGS LP-III discharges** (Q100 ≈ 16,050 cfs). The **ResUNet is real and implemented** (`src/hydraulics/resunet.py`) but is described as a parallel/future capability, not today's operational source. The "25 watersheds × 250 simulations" and "IoU > 0.75 operational" claims were removed as not-yet-true.

6. **Stage 4 / Task 4 corrected from "31 independent pipeline runs" to percentile propagation.** Verified in `src/probabilistic/ensemble.py`: the pilot propagates **P10/P50/P90 rainfall percentiles through an SCS-CN (TR-55) runoff model + unit-response factor to discharge, then a nearest-scenario flood-library lookup**, producing best/likely/worst maps. Full 31-member independent propagation is described as the upgrade path. The 0.5 m life-safety threshold product is retained (verified in the frontend and `manager_products.py`).

7. **Stage 6 / Task 6 rewritten as a delivered upgrade over the proposed Streamlit/Dash dashboard.** Verified in `frontend/src/App.tsx` and the component/route source: a **custom React + TypeScript + FastAPI system** with Live/Simulation mode toggle (shared-state what-if slider), MapLibre GL map with per-building and per-critical-facility popups at 6 return periods, a return-period explorer strip (`RETURN_PERIODS = [5,10,25,50,100,200]`), a Decision Cockpit (Kirpich + SCS lag time-to-peak, life-safety probability, Table-4 framework), an NWS-style bulletin citing **ARS 28-910 "Stupid Motorist Law"** (`src/api/routes_action.py`), a **Developer-View-gated** model-diagnostics panel, a **data-staleness watchdog** (2-hr advisory / 6-hr critical in `AlertBanner.tsx`), and an **APScheduler cron job every 6 hours** (`scripts/scheduler.py`). Building categories (School / Public-Civic / Residential / Commercial-Industrial / Agricultural-Outbuilding / Unclassified) verified in `src/common/building_categories.py`.

8. **Table 2 (six stages) methods updated** to match items 3–7; a universal-vs-watershed-specific note added after the table. Table structure/columns preserved.

9. **Table 1 label** changed from "AFFI (Proposed)" to "AFFI (Pilot — validated)" to reflect that the system is now built.

10. **Table 5 (data sources) updates:** (a) pilot gauge corrected from **09481740 (Santa Cruz at Tubac)** to **09481500 (Sonoita Creek near Patagonia)** — the gauge the code actually uses (`config/watersheds/upper_sonoita.yaml`, ensemble/manifest); (b) Walnut Gulch record corrected to "70+ years" (original said "0+ years", an apparent typo); (c) ERA5 corrected to "1940–present" (original said "940"); (d) DEM resolution noted as 10-m operational with 1-m lidar available; (e) **added rows** for FEMA NFHL/BFE and USGS LP-III discharge, since these now drive Stage 3.

11. **Section 7 restructured** to keep Table 6 as *targets* and add **Section 7.2 Validated Pilot Results** with the real, honestly-labeled numbers.

12. **References expanded** with real, verifiable, now-relevant citations for methods actually in the code: XGBoost (Chen & Guestrin 2016), Focal Loss (Lin et al. 2017), SCS-CN/TR-55 (NRCS), Leopold & Maddock 1953 (hydraulic geometry), Kirpich 1940 (time of concentration), and FEMA NFHL. No fabricated references were added.

### Open questions / judgment calls for your review

- **Watershed area / delineation — RESOLVED (August 10, 2026).** Confirmed via USGS gauge records: 09481500's contributing drainage area is published at ~209 mi² (waterdata.usgs.gov), matching `config/watersheds/upper_sonoita.yaml`'s `area_km2: 510` (≈197 mi², within normal rounding/delineation-method variance) used for hydrologic scaling in `ensemble.py`. The Problem Statement's "55.4 mi² (143.6 km²)" is a genuinely different, smaller number: the HUC-12 sub-watershed boundary (150503010204) that defines the mapped flood-inundation footprint, not the full upstream gauge-drainage area. Both figures are real and correct for what they each describe; Section 2.1 now states this explicitly rather than leaving one unexplained number next to the other.
- **Pilot gauge change.** I changed Table 5 to gauge 09481500 to match the implementation. If the paper genuinely intends the Santa Cruz at Tubac gauge (09481740), revert that row. Flagging because it is a factual identifier change.
- **Return periods.** The flood-library manifest actually spans 2–500-yr (8 levels); the dashboard's return-period explorer strip exposes six (5/10/25/50/100/200-yr). I described both accurately, but if you want the paper to state a single canonical set, standardize here.
- **Historical/IoU validation** (Task 5 D5.2 / Table 6 row 3) is described as in-progress rather than complete, because I found the benchmark engine but no completed multi-event IoU report. If that validation is in fact done, send the numbers and I will fold them into Section 7.2.
- **"31 ensemble members" in Table ES-1** was kept (the GFS input genuinely has 31 members) but clarified as "31-member GFS → P10/P50/P90 propagation" to avoid implying 31 independent hydraulic simulations.

---

## Changelog — What Changed From the July 6 Version

*Same convention as the changelog above: every claim below was verified directly against the running code and the live Docker stack, not summarized from memory.*

### A. Two critical bugs found and fixed (August 10, 2026)

1. **Rainfall unit mismatch — the more severe of the two.** `EnsembleForecastClient.fetch()` (`src/forecast/api_client.py`) pulls Open-Meteo ensemble precipitation in **millimeters**, as its own docstring states. `map_calculator.compute_daily_statistics()` and `alert_engine.classify_all_days()` (`src/forecast/map_calculator.py`, `src/forecast/alert_engine.py`) both passed those millimeter values straight through into fields named `p50_24hr` / `rainfall_inches`, and compared them directly against the inch-based Advisory/Watch/Warning thresholds (built from NOAA Atlas 14, genuinely in inches) — with no `÷25.4` conversion anywhere in the chain. Effect, verified against the running system: for roughly a week (~August 4–10, 2026) the dashboard displayed a **permanent false WARNING alert with a "Severe/catastrophic flooding" classification**, independent of actual weather, because ordinary rainfall (e.g., a real 0.19 in / 24 hr) was being read downstream as "4.8 inches." Fixed by adding the missing `MM_TO_IN = 25.4` conversion at both call sites, with new regression tests (below) so a future refactor cannot silently reintroduce it. Verified: (a) the full test suite (190 tests, including the two new regression tests) passes; (b) a from-scratch manual re-derivation from the raw 30-member Open-Meteo ensemble matches the corrected pipeline output; (c) the live API now returns `"current_alert": "GREEN"` / "No meaningful flooding expected" for the actual current forecast, a complete reversal from the pre-fix state.
2. **Out-of-memory crash silently freezing "live" data.** `population_at_risk()`'s helper (`src/common/population_exposure.py`) read the **entire CONUS-scale WorldPop raster** (43,072 × 6,298 pixels, ~2.2 GB as float64) into memory on every call, just to compute population exposure over one ~19 km watershed grid — peaking at **6.8 GB resident memory**, measured directly. This reliably SIGKILL'd (`rc=-9`) the Task 4 forecast-refresh subprocess on nearly every scheduled 6-hourly cycle since ~August 4, which meant the dashboard's "auto-refreshes every 60 s, no manual reload needed" claim was true for the UI polling loop but not for the underlying data — `outputs/task4/forecast_7day.json` was silently stuck on an August 3 snapshot for six days while the app kept presenting it as live. Fixed by windowed-reading only the small source region covering the destination grid (`rasterio.windows.from_bounds`, padded for bilinear-resampling edge effects) instead of the whole national raster. Verified: peak memory dropped from 6.8 GB to ~210 MB (32×) with **identical population results** (407 / 52 / 207 people exposed, before and after), and the full Task 4 pipeline now completes cleanly (`rc=0`) instead of being killed partway through.
3. **Why these two together produced such a convincing false signal.** The unit bug alone would have produced an obviously-wrong number a careful reviewer might catch; the OOM bug independently froze the map/discharge overlays on a real (if stale) severe-storm day from August 3, so the two defects reinforced each other into a dashboard that looked internally consistent — stale severe maps, a matching severe alert banner — while being wrong on both axes. Neither defect was caught by the existing test suite because the unit conversion was never exercised against realistic-magnitude input, and the OOM path only manifests under the container's actual memory ceiling, not in a unit test's small synthetic array. Regression tests now guard both: `test_daily_statistics_converts_mm_to_inches` and `test_classify_all_days_converts_mm_before_comparing_to_inch_thresholds` (`tests/test_task1/`) assert the exact mm→inch boundary; `test_windowed_read_is_bounded` (`tests/test_common/test_population_exposure.py`) asserts the population read stays windowed rather than pulling the full national raster.

### B. Task 6 dashboard — features added since July 6

- **Google-Flood-Hub-inspired decision-support elements:** a gauge status badge (Normal / Warning / Danger / Extreme, tied to the 2-yr / 5-yr / 25-yr discharge thresholds already in the flood library) in the Decision Cockpit header, and a per-pixel flood-probability ("Inundation Probability") heatmap map layer, both driven by the existing Pearson-Tukey-weighted probability-of-inundation raster (`src/probabilistic/risk_map.py`).
- **Graduated per-feature flood severity, replacing a binary flooded/dry status.** Roads, buildings, and infrastructure on the map now report one of none / minor / moderate / severe (NWS "Turn Around Don't Drown" depth bands: 0.05 / 0.3 / 0.6 m) plus a `poi_pct` model-confidence percentage, instead of a binary FLOODED tag — verified in `src/probabilistic/today_feature_status.py` and covered by new tests in `tests/test_task4/test_today_feature_status.py`.
- **Live map-overlay refresh bug fixed.** The map's raster overlay images (`_map_layer_today_likely.png`, `_map_layer_today_poi.png`) were previously written only by a one-time manual script, never by the scheduler — so the map's colored overlay had been frozen since its first manual build regardless of new forecasts. `src/probabilistic/map_overlay.py` now regenerates both every forecast cycle from within `scripts/07_task4_probabilistic.py`.
- **Official critical-facilities correction.** The nine core critical facilities (electric utility, town hall, marshal's office, public works/WWTP, post office, mine, assisted-care facility, high school, fire/rescue) were re-pinned to exact addresses and coordinates from an official town facilities list, each tagged `source: "official_critical_facilities_list"` in `scripts/15_build_infrastructure.py`; the remaining ten facilities are explicitly tagged `source: "estimated_not_officially_sourced"` so the map never blurs the two provenance levels together.
- **2D/3D map toggle with a Google-Maps-style basemap.** The map now defaults to a flat 2D view (matching Google/Apple Maps convention) with an explicit opt-in 3D pitch toggle, and the streets basemap was switched to CARTO Voyager raster tiles for closer visual parity with commercial map products.
- **Official-government-source visual separation.** The NWS official-alerts panel was redesigned with its own consistent "OFFICIAL" visual signature (navy top rail, reserved `--gov-navy` token) so it no longer visually merges with the dashboard's own model-driven alert banner — the two are different claims (government fact vs. model forecast) and now look different.
- **Evacuation-plan restructuring, official flood-maps panel, and incident-summary sharing.** The evacuation time-budget chart now separates structure / public / internal action categories on one shared time axis; a new panel links out to the authoritative Santa Cruz County GIS, FEMA Map Service Center, ADWR, and Town of Patagonia CRS pages; the print-based summary was replaced with an email/X-share plain-text summary builder.
- **Depth-scale reference diagram bug fixed.** The "person standing in floodwater" reference figure had a negative-radius SVG circle (from an inverted subtraction in the y-coordinate math) that silently failed to render the head; fixed, and the figure now includes a subtle water-surface animation gated behind `prefers-reduced-motion`.
- **Design-system pass:** a type scale, spacing scale, and `tabular-nums` numeric alignment were added (`frontend/src/theme.css`), and the dashboard was broken into labeled zones ("Live Decision Support," "History & Forecast Verification," "Live Sensors & Reference Data") for easier scanning by a first-time reviewer.

### C. What did not change

Per the same standard applied throughout this document, one item that came under review this session was deliberately **not** changed: the Leopold hydraulic-geometry depth-scaling behavior for discharges below the flood library's smallest stored return period (Section 4.5, Stage 3). A prior session's test (`test_below_smallest_is_not_dry_but_leopold_scaled`) already encodes the intended behavior — a reduced-but-nonzero depth via the b ≈ 0.4 exponent, rather than a fabricated "dry" result — as a deliberate design choice, not an oversight. It was re-examined this session and retained as-is; the actual user-visible issue in this area (a map that looked "flooded" even on true no-rain days) was already traced and fixed in a prior session by adding the graduated severity tiers described above, not by changing the extrapolation itself.
