# HOW TO RUN TASK 1 — Complete Guide

## Quick Start (TL;DR)

```bash
cd /workspace
export PYTHONPATH=.
python3 scripts/run_task1.py
```

Then open: `outputs/task1/index.html` in your browser.

---

## What is Task 1?

**Task 1** is an **ensemble-based flood forecast system** that:
1. Fetches 7-day precipitation forecasts from an API
2. Computes weighted average rainfall across a watershed (5-point grid)
3. Classifies alert levels (GREEN/ADVISORY/WATCH/WARNING)
4. Generates an interactive dashboard
5. Saves results to a database

**Watershed**: Upper Sonoita Creek (Arizona, 510 km²)

---

## Prerequisites

### 1. Python Environment
You need Python 3.10+ with required packages:

```bash
# Check Python version
python3 --version

# Install required packages (one-time setup)
pip3 install pandas matplotlib numpy scikit-learn pyyaml folium geopandas pytz plotly pydantic requests pytest python-dotenv pyproj
```

### 2. Project Structure
The code expects this layout:
```
/workspace/
├── config/
│   ├── settings.py
│   └── upper_sonoita.yaml
├── src/
│   ├── task1_meteorology/
│   │   ├── grid.py
│   │   ├── api_client.py
│   │   ├── map_calculator.py
│   │   └── alert_engine.py
│   └── common/
│       ├── database.py
│       ├── validators.py
│       └── logging_setup.py
├── scripts/
│   ├── run_task1.py
│   └── build_dashboard.py
└── outputs/
    └── task1/
```

All of this is already set up in `/workspace`.

---

## Step-by-Step Execution

### Step 1: Navigate to Workspace
```bash
cd /workspace
```

### Step 2: Set Python Path
This tells Python where to find the modules:
```bash
export PYTHONPATH=.
```

Or do it inline:
```bash
PYTHONPATH=. python3 scripts/run_task1.py
```

### Step 3: Run the Pipeline
```bash
python3 scripts/run_task1.py
```

**Expected Output:**
```
============================================================
TASK 1 — Flood Forecast Pipeline
============================================================
Watershed: Upper Sonoita Creek (HUC: 15050301)
Area: 510 km² | Gauge: USGS 09481500
Pour Point: Hwy 82 Bridge, Patagonia AZ

Pipeline initialized successfully
----------------------------------------
STEP 1: Fetching ensemble forecasts
----------------------------------------
Data source: api
...
[continues with processing steps]
...
✓ Training complete
```

### Step 4: Build the Dashboard
After Task 1 completes, build the interactive dashboard:

```bash
python3 scripts/build_dashboard.py
```

**Expected Output:**
```
✓ Saved: outputs/task1/dashboard_precipitation.html
✓ Saved: outputs/task1/dashboard_probabilities.html
✓ Saved: outputs/task1/dashboard_return_periods.html
✓ Saved: outputs/task1/dashboard_summary.html
✓ Saved: outputs/task1/index.html

======================================================================
TASK 1 DASHBOARD COMPLETE
======================================================================
Watershed: Upper Sonoita Creek (HUC: 15050301)
Current Alert: GREEN
7-Day Maximum: WARNING
Peak Forecast (P90): 16.02"
10-Year Benchmark: 3.1"
```

### Step 5: View the Dashboard
Open the main dashboard in your browser:

```bash
# On Linux/Mac
open outputs/task1/index.html

# Or just navigate to the file in your browser
# File path: /workspace/outputs/task1/index.html
```

---

## Complete One-Command Execution

Run both Task 1 and dashboard generation in sequence:

```bash
cd /workspace && \
export PYTHONPATH=. && \
python3 scripts/run_task1.py && \
python3 scripts/build_dashboard.py && \
echo "✓ Complete! Open: outputs/task1/index.html"
```

Or as a single line:
```bash
cd /workspace && PYTHONPATH=. python3 scripts/run_task1.py && python3 scripts/build_dashboard.py
```

---

## What Gets Generated

After running Task 1 and the dashboard builder, you'll have:

### Raw Outputs (from `run_task1.py`)
```
outputs/task1/
├── task1_alert_packet.json          (Structured forecast data)
├── task1_forecast_dashboard.png     (Static map visualization)
├── floodai.db                       (SQLite database with alert history)
└── floodai.log                      (Execution log)
```

### Dashboard Files (from `build_dashboard.py`)
```
outputs/task1/
├── index.html                       (Main dashboard - OPEN THIS)
├── dashboard_precipitation.html     (Ensemble forecast chart)
├── dashboard_probabilities.html     (PoE analysis chart)
├── dashboard_return_periods.html    (Return period chart)
├── dashboard_summary.html           (Summary table)
└── README.md                        (Interpretation guide)
```

---

## Understanding the Output

### Alert Packet (JSON)
The `task1_alert_packet.json` contains:
- Watershed metadata (name, HUC, area, coordinates)
- 7-day forecast with percentiles (P10, P50, P90)
- Alert classifications (GREEN/ADVISORY/WATCH/WARNING)
- Probability of exceedance (PoE) for each threshold
- Return period analysis
- API statistics

**Example structure:**
```json
{
  "generated_utc": "2026-04-27T15:54:22",
  "watershed": {
    "name": "Upper Sonoita Creek",
    "huc": "15050301",
    "area_km2": 510.0
  },
  "current_alert": "GREEN",
  "max_7day_alert": "WARNING",
  "forecast_days": [
    {
      "day": 0,
      "date": "2026-04-27",
      "p50_24hr": 0.0,
      "p90_24hr": 0.0,
      "alert_level": "GREEN"
    },
    ...
  ]
}
```

### Dashboard (HTML)
The `index.html` is a professional interactive dashboard with:
- **Alert banner** showing current status
- **Statistics cards** (API success rate, peak forecasts, benchmarks)
- **4 interactive Plotly charts**:
  1. Precipitation forecast (P10/P50/P90 + alerts)
  2. Probability of exceedance (PoE)
  3. Return period analysis
  4. Summary table
- **Interpretation guide** for non-technical users

---

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'config'"
**Solution**: Make sure you set `PYTHONPATH=.` before running:
```bash
export PYTHONPATH=.
python3 scripts/run_task1.py
```

### Issue: "No module named 'pandas'"
**Solution**: Install dependencies:
```bash
pip3 install pandas matplotlib numpy scikit-learn pyyaml folium geopandas pytz plotly pydantic requests
```

### Issue: "FileNotFoundError: config/upper_sonoita.yaml"
**Solution**: Make sure you're in the `/workspace` directory:
```bash
cd /workspace
```

### Issue: Dashboard shows empty charts
**Solution**: Make sure you ran `build_dashboard.py` AFTER `run_task1.py`:
```bash
python3 scripts/run_task1.py
python3 scripts/build_dashboard.py
```

### Issue: "Permission denied" when opening HTML
**Solution**: The HTML files are read-only. Just open them in your browser:
```bash
# Copy the file path and paste into browser address bar:
file:///workspace/outputs/task1/index.html
```

---

## Configuration

### Changing the Watershed
To run Task 1 for a different watershed, edit `config/upper_sonoita.yaml`:

```yaml
watershed:
  name: "Your Watershed Name"
  huc: "12345678"
  usgs_gauge: "09999999"
  area_km2: 500.0
  lat: 31.5
  lon: -110.7
  bbox:
    north: 31.85
    south: 31.47
    east: -110.5
    west: -110.9
```

Then run:
```bash
PYTHONPATH=. python3 scripts/run_task1.py
```

### Changing Forecast Days
Edit `config/settings.py` to change the forecast horizon:
```python
api:
  forecast_days: 7  # Change to 10, 14, etc.
```

### Changing Alert Thresholds
Edit `config/upper_sonoita.yaml`:
```yaml
alert_thresholds:
  advisory_poe: 0.25    # 25% probability
  watch_poe: 0.50       # 50% probability
  warning_poe: 0.70     # 70% probability
```

---

## Pipeline Architecture

Here's what happens when you run `run_task1.py`:

```
1. INITIALIZATION
   ├─ Load config (YAML)
   ├─ Validate settings
   ├─ Create API client
   └─ Create alert engine

2. FETCH FORECASTS
   ├─ Build 5-point grid (center, N, S, E, W)
   ├─ Fetch forecast for each point
   └─ Combine into all_point_data

3. COMPUTE MAP (Mean Areal Precipitation)
   ├─ Apply weights (center=30%, cardinal=20%, diagonal=15%)
   └─ Create daily precipitation matrix

4. ROLLING ACCUMULATIONS
   ├─ Compute 1-hr, 6-hr, 24-hr accumulations
   └─ Store in accumulations dict

5. DAILY STATISTICS
   ├─ Compute percentiles (P10, P50, P90)
   └─ Compute daily stats

6. ALERT CLASSIFICATION
   ├─ Compare to thresholds
   ├─ Compute PoE (Probability of Exceedance)
   └─ Assign alert levels (GREEN/ADVISORY/WATCH/WARNING)

7. RETURN PERIOD ANALYSIS
   ├─ Compare to IDF curves
   └─ Determine storm rarity

8. SAVE RESULTS
   ├─ Save JSON alert packet
   ├─ Save to SQLite database
   └─ Generate static PNG map

9. RETURN RESULTS
   └─ Return alert packet dict
```

---

## Key Concepts

### Ensemble Forecast
- **Multiple weather models** blended together
- **P10**: 10th percentile (optimistic, 1 in 10 members)
- **P50**: 50th percentile (median, most likely)
- **P90**: 90th percentile (pessimistic, 9 in 10 members)

### Mean Areal Precipitation (MAP)
- Weighted average of rainfall across 5 grid points
- Weights: Center (30%), Cardinal (20%), Diagonal (15%)
- Represents "average rainfall over the entire watershed"

### Probability of Exceedance (PoE)
- Percentage of ensemble members exceeding a threshold
- Example: "70% of models predict >2.02" rainfall"
- Used to classify alert levels

### Return Period
- How rare is a storm of this magnitude?
- "100-year event" = 1% annual probability
- Computed from historical IDF (Intensity-Duration-Frequency) curves

### Alert Levels
- 🟢 **GREEN**: <10% PoE (safe)
- 🟡 **ADVISORY**: 25-50% PoE (caution)
- 🟠 **WATCH**: 50-70% PoE (alert)
- 🔴 **WARNING**: >70% PoE (danger)

---

## Example: Full Workflow

```bash
# 1. Navigate to workspace
cd /workspace

# 2. Set Python path
export PYTHONPATH=.

# 3. Run Task 1 pipeline
echo "Running Task 1 pipeline..."
python3 scripts/run_task1.py

# 4. Build interactive dashboard
echo "Building dashboard..."
python3 scripts/build_dashboard.py

# 5. Open in browser
echo "Opening dashboard..."
open outputs/task1/index.html

# Or on Linux:
# xdg-open outputs/task1/index.html
```

---

## Output Files Reference

| File | Size | Purpose |
|------|------|---------|
| `index.html` | 11 KB | Main interactive dashboard |
| `dashboard_precipitation.html` | 4.7 MB | Ensemble forecast chart |
| `dashboard_probabilities.html` | 4.7 MB | PoE analysis chart |
| `dashboard_return_periods.html` | 4.7 MB | Return period chart |
| `dashboard_summary.html` | 4.7 MB | Summary table |
| `task1_alert_packet.json` | ~50 KB | Raw forecast data (JSON) |
| `task1_forecast_dashboard.png` | ~500 KB | Static map visualization |
| `floodai.db` | ~100 KB | SQLite database |
| `README.md` | ~10 KB | Interpretation guide |

---

## Next Steps

1. **Run Task 1**: `PYTHONPATH=. python3 scripts/run_task1.py`
2. **Build Dashboard**: `python3 scripts/build_dashboard.py`
3. **View Results**: Open `outputs/task1/index.html` in browser
4. **Interpret**: Read `outputs/task1/README.md` for guidance
5. **Customize**: Edit `config/upper_sonoita.yaml` for different watersheds

---

## Support

For issues or questions:
- Check the **Troubleshooting** section above
- Review the **README.md** in `outputs/task1/`
- Check the logs: `outputs/floodai.log`
- Examine the JSON: `outputs/task1/task1_alert_packet.json`

---

**Happy forecasting!** 🌊
