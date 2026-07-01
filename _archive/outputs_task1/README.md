# TASK 1 FLOOD FORECAST DASHBOARD

## Overview
This interactive dashboard presents the ensemble-based precipitation forecast for the **Upper Sonoita Creek** watershed (HUC: 15050301, Arizona).

## Current Status
- **Current Alert**: GREEN (Safe conditions)
- **7-Day Maximum Alert**: WARNING (Severe rainfall expected Apr 30 - May 1)
- **Peak Forecast (P90)**: 16.02" (5.1x the 10-year benchmark)
- **Data Source**: Ensemble Forecast API (100% success rate)

## Dashboard Components

### 1. **index.html** (Main Dashboard)
The primary entry point. Contains all visualizations with:
- Alert level banner
- Key statistics cards
- Embedded interactive charts
- Interpretive guidance

### 2. **dashboard_precipitation.html**
24-hour precipitation forecast with:
- **P10/P50/P90 ensemble percentiles** showing forecast uncertainty
- **Alert level backgrounds** (GREEN/ADVISORY/WATCH/WARNING)
- **10-year benchmark threshold** (3.1") as reference line
- Interactive hover for detailed values

### 3. **dashboard_probabilities.html**
Probability of Exceedance (PoE) for alert thresholds:
- Left panel: 24-hour rainfall thresholds
- Right panel: 1-hour rainfall thresholds
- Three levels: Advisory (10%), Watch (50%), Warning (90%)
- Shows confidence in forecast across ensemble members

### 4. **dashboard_return_periods.html**
Storm rarity analysis:
- P90 24-hour precipitation compared to historical return periods
- Color-coded markers:
  - Green: <2-year (common)
  - Yellow: 2-25 year (notable)
  - Orange: 25-100 year (rare)
  - Dark red: 100+ year (extreme)

### 5. **dashboard_summary.html**
Tabular summary of:
- Watershed metadata (name, HUC, area, gauge)
- Current alert levels
- Forecast statistics
- Data quality metrics

## Key Findings

### 🔴 Critical Alert for Apr 30 - May 1
Days 3-4 show WARNING level with:
- **P50 (median)**: 5.9-6.7" → ~2x the 10-year benchmark
- **P90 (worst case)**: 16.0-16.1" → ~5x the benchmark
- **PoE at WARNING**: 70% probability rainfall exceeds 2.02" threshold
- **Return Period**: 100-year event (1% annual probability)

### 📊 Forecast Evolution
- **Days 0-2**: GREEN (low probability of exceedance)
- **Days 3-4**: WARNING (high probability of extreme rainfall)
- **Days 5-6**: Advisory to GREEN (system moving out)

### 🎯 Confidence
- 100% API success rate (5/5 grid points fetched successfully)
- Forecast based on 10+ ensemble members
- P10-P90 spread indicates moderate uncertainty

## How to Use

1. **For Emergency Management**: Monitor Days 3-4 closely. 70% chance of flooding-significant rainfall.

2. **For Water Resource Planning**: P50 forecast suggests 5.9-6.7" over 48 hours. Plan spillway releases accordingly.

3. **For Hydrologic Modeling**: Use P50 as primary scenario, P10/P90 for sensitivity analysis.

4. **For Communication**: Current alert status allows public messaging:
   - Day 0: "Monitor forecast"
   - Day 2: "Advisory issued"
   - Days 3-4: "WARNING: Extreme rainfall possible"

## Technical Details

### Data Source
- **Provider**: Ensemble Forecast API
- **Model**: Multiple forecasting models blended
- **Resolution**: 5 grid points across watershed
- **Weighting**: Center (30%), Cardinal (20%), Diagonal (15%)
- **Grid Points**: Center, North, South, East, West

### Calculations
- **MAP (Mean Areal Precipitation)**: Weighted average of 5-point grid
- **Alert Thresholds**: Based on 10-year rainfall depths (IDF curves)
- **Return Period**: Calculated vs. historical frequency analysis
- **PoE**: Computed from ensemble member exceedances

### Update Frequency
This dashboard is regenerated every 6 hours with latest ensemble forecast.

## Interpretation Guide

### Alert Levels
- 🟢 **GREEN**: <10% probability of threshold exceedance. Normal operations.
- 🟡 **ADVISORY**: 25-50% probability. Precautionary measures recommended.
- 🟠 **WATCH**: 50-70% probability. Active monitoring. Prepare response.
- 🔴 **WARNING**: >70% probability. Implement emergency protocols.

### Ensemble Percentiles
- **P10**: 10th percentile = "optimistic" forecast (1 in 10 members)
- **P50**: 50th percentile = "best guess" median (most likely)
- **P90**: 90th percentile = "pessimistic" forecast (9 in 10 members)

### Return Period
- **<2yr**: Common rainfall (happens every year)
- **10yr**: 10% annual probability (significant event)
- **100yr**: 1% annual probability (rare extreme event)

## Files Reference
```
outputs/task1/
├── index.html                           (Main dashboard - open this!)
├── dashboard_precipitation.html          (Forecast & alerts)
├── dashboard_probabilities.html          (PoE analysis)
├── dashboard_return_periods.html         (Storm rarity)
├── dashboard_summary.html                (Metadata table)
├── task1_alert_packet.json              (Raw data packet)
├── task1_forecast_dashboard.png         (Static map visualization)
├── floodai.db                           (SQLite database)
└── README.md                            (This file)
```

## Browser Compatibility
- Chrome/Chromium: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- Edge: ✅ Full support
- Mobile: ⚠️ Responsive but best on desktop (1200px+)

## Contact & Support
For questions about methodology or forecast interpretation, consult:
- NOAA National Water Center (docs)
- Ensemble Forecast API documentation
- Hydrologic Engineering Center (HEC) guidelines

---
**Generated**: 2026-04-27 15:54:22 UTC | **Version**: 2.0.0
