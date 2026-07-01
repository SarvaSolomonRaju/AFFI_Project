"""
build_dashboard.py — Generate self-contained HTML dashboard for advisor presentation.

Embeds Task 1 (precipitation forecast, alert engine, IDF benchmarks) and
Task 2 (LSTM classifier + XGBoost magnitude) results with base64-encoded images.

Usage:
    python scripts/build_dashboard.py
    open outputs/dashboard.html
"""

import sys
import json
import base64
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

OUTPUTS = ROOT / "outputs"
FIGURES = OUTPUTS / "figures"
PLOTS = OUTPUTS / "plots"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports" / "figures"
DATA = ROOT / "data"


def img_to_base64(path: Path) -> str:
    if not path.exists():
        return ""
    data = path.read_bytes()
    encoded = base64.b64encode(data).decode("utf-8")
    suffix = path.suffix.lower().lstrip(".")
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(suffix, "image/png")
    return f"data:{mime};base64,{encoded}"


def load_alert_packet() -> dict:
    for p in [OUTPUTS / "task1_alert_packet.json", OUTPUTS / "task1" / "task1_alert_packet.json"]:
        if p.exists():
            return json.loads(p.read_text())
    return {}


def load_inference_config() -> dict:
    p = MODELS / "best_inference_config.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def load_diagnostic_summary() -> str:
    p = PLOTS / "diagnostic_summary.txt"
    if p.exists():
        return p.read_text()
    return ""


def build_forecast_rows(packet: dict) -> str:
    days = packet.get("forecast_days", [])
    if not days:
        return '<tr><td colspan="6" style="padding:20px;color:#888;">No forecast data</td></tr>'
    rows = []
    for d in days:
        alert = d.get("alert_level", "GREEN")
        badge_cls = f"badge-{alert.lower()}"
        rp = d.get("return_period", {})
        rows.append(f"""<tr>
            <td class="date-col">{d.get('date','--')}</td>
            <td>{d.get('p50_24hr',0):.2f}"</td>
            <td class="p90-col">{d.get('p90_24hr',0):.2f}"</td>
            <td>{d.get('p50_1hr',0):.3f}"</td>
            <td>{rp.get('nearest_return_period','--')}</td>
            <td><span class="alert-badge {badge_cls}">{alert}</span></td>
        </tr>""")
    return "\n".join(rows)


def build_image_section(title: str, path: Path, description: str = "") -> str:
    if not path.exists():
        return ""
    b64 = img_to_base64(path)
    desc_html = f'<p class="img-desc">{description}</p>' if description else ""
    return f"""
    <div class="image-panel">
        <h3>{title}</h3>
        {desc_html}
        <img src="{b64}" alt="{title}" class="result-img">
    </div>"""


def parse_diagnostics(text: str) -> dict:
    metrics = {}
    for line in text.strip().split("\n"):
        if line.startswith("Overall NSE:"):
            metrics["nse"] = line.split(":")[1].strip()
        elif line.startswith("Overall PBIAS:"):
            metrics["pbias"] = line.split(":")[1].strip()
        elif line.startswith("AUC-ROC:"):
            metrics["auc_roc"] = line.split(":")[1].strip()
        elif line.startswith("AUC-PR:"):
            metrics["auc_pr"] = line.split(":")[1].strip()
    return metrics


def build_regime_table(text: str) -> str:
    lines = text.strip().split("\n")
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("Regime"):
            header_idx = i
            break
    if header_idx is None:
        return ""
    rows = []
    for line in lines[header_idx + 2:]:
        if line.startswith("==="):
            break
        parts = line.split()
        if len(parts) >= 7:
            regime = parts[0]
            if regime == "Low" or regime == "Mid" or regime == "High" or regime == "Extreme":
                regime = " ".join(parts[0:2])
                parts = [regime] + parts[2:]
            elif regime == "Dry":
                regime = "Dry Season"
                parts = [regime] + parts[2:]
            n = parts[1]
            nse = parts[2]
            pbias = parts[3]
            try:
                nse_val = float(nse)
            except ValueError:
                continue
            nse_class = "metric-good" if nse_val > 0.5 else ("metric-ok" if nse_val > 0 else "metric-bad")
            rows.append(f"""<tr>
                <td class="regime-name">{regime}</td>
                <td>{n}</td>
                <td class="{nse_class}">{nse}</td>
                <td>{pbias}%</td>
            </tr>""")
    return "\n".join(rows)




def load_task4_forecast() -> dict:
    p = OUTPUTS / "task4" / "forecast_7day.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def load_task5_report() -> dict:
    p = OUTPUTS / "task5" / "benchmark_report.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


def _embed_image(path: Path, alt: str, cls: str = "result-img") -> str:
    if not path.exists():
        return f'<div class="img-desc">[image missing: {path.name}]</div>'
    return f'<img src="{img_to_base64(path)}" alt="{alt}" class="{cls}">'


def generate_sim_pngs() -> dict:
    """Render depth rasters for T=5,10,25,50,100,200 yr to PNG at build time.
    Returns {T_int: {"b64": "data:image/png;base64,...", "Q_cms": ..., "max_depth_m": ..., "wet_area_km2": ...}}
    """
    try:
        import rasterio
        import numpy as np
        import matplotlib.cm as _cm
        import matplotlib.colors as _mcolors
        from PIL import Image as _Image
        from rasterio.warp import reproject as _reproject, Resampling, calculate_default_transform
    except ImportError:
        return {}

    manifest_path = DATA / "flood_library_real" / "manifest.json"
    if not manifest_path.exists():
        return {}
    manifest = json.loads(manifest_path.read_text())
    rp_stats = manifest.get("return_periods", {})
    files = manifest.get("files", {})

    SIM_DIR = OUTPUTS / "sim"
    SIM_DIR.mkdir(exist_ok=True)

    result = {}
    for T in [5, 10, 25, 50, 100, 200]:
        tif_name = files.get(str(T))
        if not tif_name:
            continue
        tif_path = DATA / "flood_library_real" / tif_name
        if not tif_path.exists():
            continue
        stats = rp_stats.get(str(T), {})
        try:
            with rasterio.open(tif_path) as src:
                arr = np.nan_to_num(src.read(1), nan=0.0).astype(np.float32)
                src_crs, src_transform = src.crs, src.transform
                h, w = arr.shape
                left = src_transform.c
                top = src_transform.f
                right = left + w * src_transform.a
                bottom = top + h * src_transform.e
                dst_transform, dst_w, dst_h = calculate_default_transform(
                    src_crs, "EPSG:4326", w, h, left, bottom, right, top
                )
                dst = np.zeros((dst_h, dst_w), dtype=np.float32)
                _reproject(
                    source=arr, destination=dst,
                    src_transform=src_transform, src_crs=src_crs,
                    dst_transform=dst_transform, dst_crs="EPSG:4326",
                    resampling=Resampling.bilinear,
                    src_nodata=0.0, dst_nodata=0.0,
                )
            cmap_fn = _cm.get_cmap("Blues")
            norm = _mcolors.Normalize(vmin=0, vmax=12, clip=True)
            rgba = (cmap_fn(norm(dst)) * 255).astype(np.uint8)
            rgba[..., 3] = np.where(dst > 0.05, 200, 0).astype(np.uint8)
            out_png = SIM_DIR / f"depth_T{T:03d}yr.png"
            _Image.fromarray(rgba, "RGBA").save(out_png)
            b64 = img_to_base64(out_png)
        except Exception:
            b64 = ""
        result[T] = {
            "b64": b64,
            "Q_cms": round(stats.get("Q_cms", 0)),
            "max_depth_m": round(stats.get("max_depth_m", 0.0), 2),
            "wet_area_km2": round(stats.get("wet_area_km2", 0.0), 4),
        }
    return result


def build_sim_data_js(sim_data: dict) -> str:
    defaults = {
        5:   {"roads": 82,  "infra": 4,  "alert": "YELLOW", "severity": "Minor",    "prob": "20%"},
        10:  {"roads": 105, "infra": 7,  "alert": "ORANGE", "severity": "Moderate", "prob": "10%"},
        25:  {"roads": 132, "infra": 10, "alert": "ORANGE", "severity": "Major",    "prob": "4%"},
        50:  {"roads": 146, "infra": 11, "alert": "RED",    "severity": "Major",    "prob": "2%"},
        100: {"roads": 154, "infra": 12, "alert": "RED",    "severity": "Severe",   "prob": "1%"},
        200: {"roads": 162, "infra": 14, "alert": "RED",    "severity": "Severe",   "prob": "0.5%"},
    }
    steps = [5, 10, 25, 50, 100, 200]
    data_entries = []
    img_entries = []
    for T in steps:
        d = sim_data.get(T, {})
        defs = defaults[T]
        Q = d.get("Q_cms", 0)
        maxD = d.get("max_depth_m", 0)
        wetA = d.get("wet_area_km2", 0)
        b64 = d.get("b64", "")
        data_entries.append(
            f"  {T}: {{Q:{Q}, maxDepth:{maxD}, wetArea:{wetA}, roads:{defs['roads']}, infra:{defs['infra']}, alert:'{defs['alert']}', severity:'{defs['severity']}', prob:'{defs['prob']}'}}"
        )
        img_entries.append(f"  {T}: {repr(b64)}")
    sim_data_js = "const SIM_STEPS = [5, 10, 25, 50, 100, 200];\n"
    sim_data_js += "const SIM_DATA = {\n" + ",\n".join(data_entries) + "\n};\n"
    sim_data_js += "const SIM_IMGS = {\n" + ",\n".join(img_entries) + "\n};"
    return sim_data_js


def build_user_view(packet: dict, task4: dict, sim_data: dict = None) -> str:
    """Build the user-facing view HTML block."""
    sim_data = sim_data or {}
    ws = packet.get("watershed", {})
    current_alert = packet.get("current_alert", "GREEN")
    alert_lower = current_alert.lower()
    today = task4.get("today", {}) if task4 else {}
    days = task4.get("forecast_7day", []) if task4 else []
    today_cls = today.get("likely_classification", {})
    worst_cls = today.get("worst_classification", {})
    today_qs = today.get("discharge_cms", {})
    today_rain = today.get("rainfall_inches", {})
    today_likely_stats = today.get("scenarios_stats", {}).get("likely", {})
    today_worst_stats = today.get("scenarios_stats", {}).get("worst", {})
    today_best_stats = today.get("scenarios_stats", {}).get("best", {})
    mgr_prod = task4.get("manager_products", {}) if task4 else {}
    ttp = mgr_prod.get("time_to_peak_hours", {})
    ttp_p50 = ttp.get("p50_hours", "n/a")
    ttp_p10 = ttp.get("p10_hours", "n/a")
    ttp_p90 = ttp.get("p90_hours", "n/a")
    sigma_max = mgr_prod.get("uncertainty_max_m", 0.0)
    p05_max = mgr_prod.get("prob_gt_05m_max", 0.0)
    map_prob05 = _embed_image(OUTPUTS / "task4" / "today_prob_gt_05m.png", "P(depth > 0.5m)")
    map_uncert = _embed_image(OUTPUTS / "task4" / "today_uncertainty.png", "Uncertainty (sigma)")
    map_hydro  = _embed_image(OUTPUTS / "task4" / "today_ensemble_hydrograph.png", "Ensemble hydrograph")

    severity = today_cls.get("severity", "Minor")
    caption_main = today_cls.get("caption",
        "Today's forecast indicates baseline creek conditions.")
    worst_severity = worst_cls.get("severity", severity)

    map_likely = _embed_image(OUTPUTS / "task4" / "today_likely.png", "Likely flood map today")
    map_best = _embed_image(OUTPUTS / "task4" / "today_best.png", "Best case")
    map_worst = _embed_image(OUTPUTS / "task4" / "today_worst.png", "Worst case")
    map_poi = _embed_image(OUTPUTS / "task4" / "today_poi.png", "Probability of inundation")

    roads_summary = DATA / "local_assets" / "flooded_roads_summary.csv"
    flooded_roads_count = 0
    if roads_summary.exists():
        try:
            import csv as _csv
            with open(roads_summary) as _f:
                flooded_roads_count = sum(1 for r in _csv.DictReader(_f)
                                          if r.get("status", "").upper() == "FLOODED")
        except Exception:
            flooded_roads_count = 154
    else:
        flooded_roads_count = 154

    # 7-day mini cards
    day_cards = []
    for d in days:
        thumb_path = OUTPUTS / "task4" / d.get("likely", {}).get("thumbnail", "")
        img = _embed_image(thumb_path, d.get("date", ""))
        alert = d.get("alert_level", "GREEN")
        badge_cls = "badge-" + alert.lower()
        wet_km2 = d.get("likely", {}).get("wet_area_km2", 0.0)
        sev = d.get("likely", {}).get("scenario_class", "None")
        day_cards.append(f"""
        <div class="day-card">
            <div class="day-date">{d.get('date','--')}</div>
            {img}
            <div class="day-meta">Wet: {wet_km2:.3f} km&#178;</div>
            <div class="day-meta">{sev}</div>
            <span class="day-badge {badge_cls}">{alert}</span>
        </div>""")
    day_strip = "\n".join(day_cards) if day_cards else "<div class='img-desc'>No forecast loaded.</div>"

    # Action items based on severity
    if severity in ("Major", "Severe") or worst_severity in ("Major", "Severe"):
        actions = """
        <li class="warn"><strong>Evacuate</strong> low-lying property along Sonoita Creek; do not cross flooded roadways.</li>
        <li class="warn">Monitor NWS Tucson alerts and local emergency broadcasts.</li>
        <li>Move livestock and equipment to higher ground.</li>
        <li>Stay clear of the Hwy 82 bridge crossing during peak runoff.</li>
        """
    elif severity == "Moderate" or worst_severity == "Moderate":
        actions = """
        <li class="warn">Avoid the immediate floodplain and low-water crossings during the next 24 hours.</li>
        <li>Secure outdoor items and clear culverts near your property.</li>
        <li>Check on neighbors in flood-prone parcels along the creek.</li>
        <li>Charge phones and prepare a small emergency kit.</li>
        """
    elif severity == "Minor":
        actions = """
        <li>Stay aware: minor overbank flow possible along the creek banks.</li>
        <li class="ok">No evacuation needed; normal precautions for monsoon-season weather.</li>
        <li>Do not drive through any standing or moving water on roadways.</li>
        """
    else:
        actions = """
        <li class="ok">No flood action required at this time.</li>
        <li>Conditions are dry to near-normal. Continue routine monitoring.</li>
        """

    method_blurb = (task4.get("method") if task4 else
        "Discharge-indexed flood-map library lookup with P10/P50/P90 rainfall ensemble.")

    html = f"""
    <div id="mode-bar" style="position:sticky; top:0; z-index:1000; background:#0f1f3a;
         padding:10px 18px; display:flex; align-items:center; gap:16px; flex-wrap:wrap;
         border-bottom:3px solid #b71c1c; margin-bottom:0;">
      <span style="color:#cfd8e3; font-weight:600; font-size:0.9rem;">Dashboard Mode:</span>
      <button id="btn-live-mode" onclick="setMode('live', this)"
        style="padding:7px 18px; border-radius:20px; border:none; font-weight:700;
               background:#2bb673; color:#fff; cursor:pointer;">
        📡 Live Forecast
      </button>
      <button id="btn-sim-mode" onclick="setMode('sim', this)"
        style="padding:7px 18px; border-radius:20px; border:2px solid #e65100;
               background:transparent; color:#e65100; font-weight:700; cursor:pointer;">
        🧪 Simulation Mode
      </button>
      <span id="mode-desc" style="color:#adb5bd; font-size:0.85rem; font-style:italic;">
        Showing today's real forecast data
      </span>
    </div>

    <div id="live-view">
    <div class="alert-banner alert-{alert_lower}">
        Current Alert Level: {current_alert} &nbsp; | &nbsp; {ws.get('name','Upper Sonoita Creek')}
    </div>

    <div class="hero-alert">
        <div class="hero-map">
            <h3 style="margin:0 0 10px;color:var(--accent-blue);">Today's Flood Map ({today.get('date','--')})</h3>
            <p class="img-desc">Most-likely flood extent given the median (P50) rainfall forecast for the Upper Sonoita Creek watershed.</p>
            {map_likely}
        </div>
        <div class="hero-side">
            <div class="hero-status">Today's Severity</div>
            <div class="hero-level" style="color:var(--accent-{('red' if severity in ('Major','Severe') else 'orange' if severity=='Moderate' else 'green') });">{severity}</div>
            <div class="hero-caption">{caption_main}</div>
            <div class="hero-metrics">
                <div class="hero-metric">
                    <div class="v">{today_rain.get('p50',0):.2f}&quot;</div>
                    <div class="l">Expected rain today (24hr)</div>
                </div>
                <div class="hero-metric">
                    <div class="v">{today_qs.get('p50',0):.1f}</div>
                    <div class="l">Likely peak Q (cms)</div>
                </div>
                <div class="hero-metric">
                    <div class="v">{today_likely_stats.get('max_depth_m',0):.2f} m</div>
                    <div class="l">Max water depth</div>
                </div>
                <div class="hero-metric">
                    <div class="v">{today_likely_stats.get('wet_area_km2',0):.3f}</div>
                    <div class="l">Flood area (km&#178;)</div>
                </div>
            </div>
        </div>
    </div>

    <!-- INTERACTIVE MAP (Folium / Leaflet) -->
    <div style="margin: 22px 0 10px;">
        <h3 style="color:var(--accent-blue); margin-bottom:6px;">
            Interactive Flood Probability Map (pan / zoom / toggle layers)
        </h3>
        <p class="img-desc" style="margin-bottom:8px;">
            Real-world Leaflet map of the Upper Sonoita Creek pilot. Toggle the FEMA 1% (100-yr) reference depth,
            today's likely flood depth, today's probability-of-inundation heatmap, FEMA NFHL flood zones,
            Base Flood Elevation lines, and the Sonoita Creek centerline. All overlays use REAL government data
            (FEMA NFHL + FEMA BFE Layer 16 + USGS 3DEP DEM + USGS NWIS 09481500).
        </p>
        <iframe src="dashboard_map.html"
                style="width:100%; height:640px; border:1px solid #d0d7de; border-radius:10px; background:#fff;"
                title="FloodAI interactive flood probability map">
        </iframe>
        <div style="font-size:0.78rem;color:#666;margin-top:6px;">
            Source: <code>outputs/dashboard_map.html</code> &middot; rebuild with
            <code>python -m src.dashboard.interactive_map</code>
        </div>
    </div>

    <!-- EMERGENCY FLOOD DECISION CENTRAL (Whitepaper Table 3 + EOC Emergency Protocol) -->
    <div class="card" id="efd-central" style="border-left:6px solid #b71c1c; background:#fff8f8;">
        <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:10px; margin-bottom:6px;">
            <div>
                <h3 style="color:#b71c1c; margin:0 0 2px 0;">&#x26A0; Emergency Flood Decision Central</h3>
                <p class="img-desc" style="margin:0;">
                    AFFI whitepaper <b>Table 3</b> products &mdash; for Emergency Operations Center staff.
                    Test storm below exceeds the <b>10-year event (Q&nbsp;=&nbsp;230&nbsp;cms)</b>.
                </p>
            </div>
            <div style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
                <button id="btn-10yr" onclick="setStorm('10yr')"
                    style="padding:6px 14px; border-radius:4px; border:2px solid #e65100;
                           background:#fff3e0; color:#e65100; font-weight:700; cursor:pointer; font-size:0.85rem;">
                    &#x2611; 10-Year Event (Q=230 cms)
                </button>
                <button id="btn-100yr" onclick="setStorm('100yr')"
                    style="padding:6px 14px; border-radius:4px; border:2px solid #b71c1c;
                           background:#ffebee; color:#b71c1c; font-weight:700; cursor:pointer; font-size:0.85rem;">
                    100-Year Design (Q=455 cms)
                </button>
            </div>
        </div>

        <!-- Initial Concerns Strip for EOC -->
        <div style="background:#ffebee; border:1px solid #ef9a9a; border-radius:6px;
                    padding:10px 14px; margin-bottom:12px; font-size:0.88rem; color:#333;">
            <b style="color:#b71c1c;">Initial EOC Concerns &mdash; Test Storm (&gt; 10-yr event):</b>
            <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px,1fr)); gap:4px 20px; margin-top:6px;">
                <div>&#x1F534; <b>Life safety:</b> potential loss of life in low-lying areas</div>
                <div>&#x1F6A8; <b>Evacuations:</b> routes + shelters (Patagonia HS &amp; Sports Complex)</div>
                <div>&#x1F3E0; <b>Property:</b> {today_likely_stats.get('wet_area_km2',0):.2f} km&#178; inundated (P50 estimate)</div>
                <div>&#x1F6A7; <b>Roads/Bridges:</b> {flooded_roads_count} road segments at risk &mdash; see map</div>
                <div>&#x1F3E5; <b>Hospitals:</b> check proximity to flood extent &mdash; layer below</div>
                <div>&#x1F691; <b>Fire / Police:</b> stations shown on map; access routes checked</div>
                <div>&#x1F4A7; <b>Water supply (wells):</b> contamination risk if inundated</div>
                <div>&#x267B; <b>Wastewater:</b> potential sewage spill if WWTP flooded</div>
                <div>&#x26A1; <b>Power &amp; telecom:</b> substations, cell towers on map</div>
                <div>&#x1F4F6; <b>Cell towers:</b> coverage loss if flooded or power cut</div>
                <div>&#x1F527; <b>Public Works:</b> staff/materials pre-positioned per DPW plan</div>
                <div>&#x1F6B0; <b>Water/sewer lines:</b> break risk at creek crossings</div>
            </div>
        </div>

        <!-- 6-panel grid -->
        <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:14px; margin-top:4px;">
            <div class="image-panel"><h3>1. Median Depth (P50)</h3>
                <p class="img-desc">Most-likely 24-hr flood depth.</p>
                {map_likely}
                <div class="scenario-stats"><div>max: <b>{today_likely_stats.get('max_depth_m',0):.2f} m</b></div><div>wet: <b>{today_likely_stats.get('wet_area_km2',0):.3f} km&#178;</b></div></div>
            </div>
            <div class="image-panel"><h3>2. 90th-percentile (P90)</h3>
                <p class="img-desc">Plausible worst case for planning.</p>
                {map_worst}
                <div class="scenario-stats"><div>max: <b>{today_worst_stats.get('max_depth_m',0):.2f} m</b></div><div>wet: <b>{today_worst_stats.get('wet_area_km2',0):.3f} km&#178;</b></div></div>
            </div>
            <div class="image-panel"><h3>3. P(depth &gt; 0.5 m)</h3>
                <p class="img-desc">Life-safety threshold (whitepaper 4.6).</p>
                {map_prob05}
                <div class="scenario-stats"><div>P-max: <b>{p05_max:.2f}</b></div></div>
            </div>
            <div class="image-panel"><h3>4. Uncertainty (&sigma;)</h3>
                <p class="img-desc">Std-dev across P10/P50/P90; high &sigma; = members disagree.</p>
                {map_uncert}
                <div class="scenario-stats"><div>&sigma;-max: <b>{sigma_max:.3f} m</b></div></div>
            </div>
            <div class="image-panel"><h3>5. Ensemble Hydrograph</h3>
                <p class="img-desc">0-24 h Q(t) with P10-P90 envelope at Sonoita Creek outlet.</p>
                {map_hydro}
            </div>
            <div class="image-panel" style="background:#fff3e0;">
                <h3>6. Time-to-Peak (Tp)</h3>
                <p class="img-desc">Kirpich Tc + SCS lag (HUC-12 150503010204).</p>
                <div style="font-size:2.2rem;color:#b71c1c;font-weight:700;line-height:1.1;">T+{ttp_p50} h</div>
                <div class="scenario-stats" style="margin-top:6px;">
                    <div>Earliest: <b>T+{ttp_p90} h</b></div>
                    <div>Median: <b>T+{ttp_p50} h</b></div>
                    <div>Latest: <b>T+{ttp_p10} h</b></div>
                </div>
                <p class="img-desc" style="margin-top:8px;">
                    Lead time from forecast issue to peak flow. &lt; 2 h = flash-flood protocol.
                </p>
            </div>
        </div>

        <!-- Action triggers -->
        <div style="margin-top:14px; padding:10px 14px; background:#fff; border-left:4px solid #b71c1c; border-radius:4px; font-size:0.92rem; color:#444;">
            <b style="color:#b71c1c;">EOC Action Triggers:</b>
            <span>P(&gt;0.5 m) &ge; 0.30 &rarr; pre-position swift-water teams &amp; open shelters;</span>
            <span>&sigma; &ge; 0.5 m &rarr; widen evacuation buffer;</span>
            <span>Tp &le; 2 h &rarr; flash-flood protocol &amp; mandatory evacuation of low-lying zones.</span>
        </div>

        <!-- 10-year event info box (hidden by default) -->
        <div id="storm-10yr-box" style="display:none; margin-top:12px; padding:10px 14px;
                background:#fff3e0; border-left:4px solid #e65100; border-radius:4px; font-size:0.90rem;">
            <b style="color:#e65100;">&#x2611; 10-Year Event selected (Q = 230 cms | T<sub>p</sub> &asymp; 3 h)</b><br>
            <div style="margin-top:6px; color:#444;">
                This storm has a <b>10% annual probability</b> of being exceeded.
                Depth maps shown are from library raster <code>depth_T010yr_Q230cms.tif</code>.<br>
                <b>Expected impacts at 10-yr level:</b> Sonoita Creek overbanks at railroad bridge; SR-82 near creek crossings
                may become impassable; low-lying residential lots on Red Rock Road at risk; USGS gauge reading
                approaches ~1.5 m stage. Well heads and septic systems within 30 m of channel likely inundated.
                Wastewater treatment influent pump station may require sandbagging. No major hospital impact expected
                at this level but access roads to Patagonia Health Center may be cut off.
            </div>
        </div>

        <!-- 100-year event info box (shown by default) -->
        <div id="storm-100yr-box" style="display:block; margin-top:12px; padding:10px 14px;
                background:#ffebee; border-left:4px solid #b71c1c; border-radius:4px; font-size:0.90rem;">
            <b style="color:#b71c1c;">100-Year Design Event (Q = 455 cms | T<sub>p</sub> &asymp; 3 h)</b><br>
            <div style="margin-top:6px; color:#444;">
                This storm has a <b>1% annual probability</b> (FEMA regulatory standard).
                Depth maps are from <code>depth_T100yr_Q455cms.tif</code> (FEMA BFE-IDW method).<br>
                <b>Expected impacts:</b> 154 road segments and 512 buildings within SFHA inundated.
                SR-82 bridge critical; cell tower on Sonoita Ridge loses power; water treatment well field
                at Patagonia Water Co. likely submerged; WWTP lift station requires emergency bypass;
                all critical-infrastructure referencing their emergency plan should be activated.
            </div>
        </div>
    </div>

    <script>
    function setStorm(type) {{
        var b10 = document.getElementById('btn-10yr');
        var b100 = document.getElementById('btn-100yr');
        var box10 = document.getElementById('storm-10yr-box');
        var box100 = document.getElementById('storm-100yr-box');
        if (type === '10yr') {{
            b10.style.background = '#e65100'; b10.style.color = '#fff';
            b100.style.background = '#ffebee'; b100.style.color = '#b71c1c';
            box10.style.display = 'block'; box100.style.display = 'none';
        }} else {{
            b100.style.background = '#b71c1c'; b100.style.color = '#fff';
            b10.style.background = '#fff3e0'; b10.style.color = '#e65100';
            box10.style.display = 'none'; box100.style.display = 'block';
        }}
    }}

    {build_sim_data_js(sim_data)}

    function updateSim(T) {{
      const d = SIM_DATA[T];
      if (!d) return;
      document.getElementById('sim-label').textContent =
        'T = ' + T + '-yr  |  Q = ' + d.Q + ' cms  |  ' + d.prob + ' annual probability';
      const colors = {{RED:'#b71c1c', ORANGE:'#e65100', YELLOW:'#f9a825', GREEN:'#2e7d32'}};
      const badge = document.getElementById('sim-alert-badge');
      badge.textContent = d.alert + ' — ' + d.severity;
      badge.style.background = colors[d.alert] || '#555';
      document.getElementById('sim-q').textContent = d.Q;
      document.getElementById('sim-maxdepth').textContent = d.maxDepth.toFixed(2) + ' m';
      document.getElementById('sim-wetarea').textContent = d.wetArea.toFixed(3) + ' km²';
      document.getElementById('sim-roads').textContent = d.roads;
      if (SIM_IMGS[T]) document.getElementById('sim-depth-img').src = SIM_IMGS[T];
      document.getElementById('sim-eoc-wetarea').textContent = d.wetArea.toFixed(2) + ' km²';
      document.getElementById('sim-eoc-roads').textContent = d.roads + ' road segments';
      document.getElementById('sim-eoc-infra').textContent = d.infra + ' of 16 POIs';
      const actions = document.getElementById('sim-actions');
      if (d.alert === 'RED' && T >= 50) {{
        actions.innerHTML = '<li class="warn"><b>Evacuate</b> low-lying areas along Sonoita Creek.</li>' +
          '<li class="warn">Do not cross flooded roadways — SR-82 may be closed.</li>' +
          '<li>Open shelters: Patagonia HS (350 cap) + Sports Complex (500 cap).</li>' +
          '<li>Activate all critical-infrastructure emergency plans (WWTP, water supply, power).</li>';
      }} else if (d.severity === 'Major' || d.severity === 'Moderate') {{
        actions.innerHTML = '<li class="warn">Avoid floodplain and low-water crossings for next 24 h.</li>' +
          '<li>Pre-position swift-water teams; open shelters on standby.</li>' +
          '<li>Well field and WWTP — sandbagging may be needed.</li>';
      }} else {{
        actions.innerHTML = '<li class="ok">Minor flooding possible — stay aware.</li>' +
          '<li>No evacuation required; normal monsoon-season precautions.</li>';
      }}
      const iframe = document.getElementById('flood-map-iframe');
      if (iframe && iframe.contentWindow) {{
        iframe.contentWindow.postMessage({{type:'showSimLayer', T: T}}, '*');
      }}
    }}

    function setMode(mode, btn) {{
      const liveView = document.getElementById('live-view');
      const simView  = document.getElementById('sim-view');
      const btnLive  = document.getElementById('btn-live-mode');
      const btnSim   = document.getElementById('btn-sim-mode');
      const desc     = document.getElementById('mode-desc');
      if (mode === 'sim') {{
        liveView.style.display = 'none';
        simView.style.display  = 'block';
        btnSim.style.background  = '#e65100';
        btnSim.style.color       = '#fff';
        btnLive.style.background = 'transparent';
        btnLive.style.color      = '#2bb673';
        desc.textContent = 'Simulation mode — drag slider to test different storm return periods';
        var sl = document.getElementById('sim-slider');
        if (sl) updateSim(SIM_STEPS[parseInt(sl.value)]);
      }} else {{
        liveView.style.display = 'block';
        simView.style.display  = 'none';
        btnLive.style.background = '#2bb673';
        btnLive.style.color      = '#fff';
        btnSim.style.background  = 'transparent';
        btnSim.style.color       = '#e65100';
        desc.textContent = "Showing today's real forecast data";
      }}
    }}
    </script>

    <h3 style="color:var(--accent-blue); margin-bottom:14px;">What could happen today (3 scenarios)</h3>
    <div class="scenario-strip">
        <div class="scenario-card">
            <h4>Best Case (10% chance drier)</h4>
            {map_best}
            <div class="scenario-stats">
                <div>Rain: <strong>{today_rain.get('p10',0):.2f}&quot;</strong></div>
                <div>Q: <strong>{today_qs.get('p10',0):.1f} cms</strong></div>
                <div>Wet: <strong>{today_best_stats.get('wet_area_km2',0):.3f} km&#178;</strong></div>
            </div>
        </div>
        <div class="scenario-card likely">
            <h4>Most Likely</h4>
            {map_likely}
            <div class="scenario-stats">
                <div>Rain: <strong>{today_rain.get('p50',0):.2f}&quot;</strong></div>
                <div>Q: <strong>{today_qs.get('p50',0):.1f} cms</strong></div>
                <div>Wet: <strong>{today_likely_stats.get('wet_area_km2',0):.3f} km&#178;</strong></div>
            </div>
        </div>
        <div class="scenario-card worst">
            <h4>Worst Case (10% chance wetter)</h4>
            {map_worst}
            <div class="scenario-stats">
                <div>Rain: <strong>{today_rain.get('p90',0):.2f}&quot;</strong></div>
                <div>Q: <strong>{today_qs.get('p90',0):.1f} cms</strong></div>
                <div>Wet: <strong>{today_worst_stats.get('wet_area_km2',0):.3f} km&#178;</strong></div>
            </div>
        </div>
    </div>

    <div class="grid-2">
        <div class="card">
            <h3>Where is flooding most likely? (Probability map)</h3>
            <p class="img-desc">Each pixel shows how confidently the model expects water to be there today. White = dry, deep red = almost certain.</p>
            {map_poi}
        </div>
        <div class="card">
            <h3>What This Means</h3>
            <ul class="action-list">
                {actions}
            </ul>
            <p class="img-desc" style="margin-top:14px;">
                <strong>Worst case today:</strong> {worst_severity} &nbsp;|&nbsp;
                Peak Q could reach <strong>{today_qs.get('p90',0):.1f} cms</strong>, max depth
                <strong>{today_worst_stats.get('max_depth_m',0):.2f} m</strong>.
            </p>
        </div>
    </div>

    <div class="card">
        <h3>7-Day Outlook</h3>
        <p class="img-desc">Day-by-day "most likely" flood footprint based on the GFS ensemble forecast.</p>
        <div class="day-strip">
            {day_strip}
        </div>
    </div>

    <div class="card green">
        <h3>How this prediction is made</h3>
        <div style="color:var(--text-secondary); font-size:0.95rem; line-height:1.7;">
            <p>{method_blurb}</p>
            <div class="provenance" style="background:#0f1f3a;border-left:4px solid #2bb673;padding:10px 14px;border-radius:6px;margin:10px 0;">
                <div style="font-weight:600;color:#2bb673;font-size:0.85rem;">DATA PROVENANCE (real, public, government-issued):</div>
                <ul style="margin:6px 0 0 18px;font-size:0.85rem;line-height:1.6;color:#cfd8e3;">
                    <li><b>FEMA NFHL</b> &mdash; 92 effective flood-hazard zones for HUC-12 150503010204 (DFIRM 04023C, Santa Cruz County, AZ).</li>
                    <li><b>FEMA BFE Layer 16</b> &mdash; 85 base-flood-elevation lines (1227.7-1258.8 m NAVD88) along Sonoita Creek.</li>
                    <li><b>USGS 3DEP</b> &mdash; real 10-m terrain raster (1778x1903) for HUC-12 (143.6 km<sup>2</sup>), UTM 12N.</li>
                    <li><b>USGS NWIS 09481500</b> &mdash; 45 yrs of annual peak discharge (1930-1983) fitted with Bulletin 17C LP-III; Q<sub>100</sub> = 455 cms (16 053 cfs).</li>
                    <li><b>NOAA Atlas 14 / OWP HAND-FIM</b> &mdash; return-period rainfall and stage-discharge reference.</li>
                </ul>
            </div>
            <ol style="margin-top:12px; padding-left:22px;">
                <li>GFS ensemble forecast gives 7-day rainfall percentiles (10th / 50th / 90th).</li>
                <li>SCS Curve-Number runoff converts rainfall to expected peak discharge.</li>
                <li>A pre-computed library of 8 <b>real</b> flood maps (FEMA AE/X polygons + BFE WSE + USGS DEM, scaled by Leopold hydraulic geometry) is searched for the matching discharge value.</li>
                <li>Three depth maps (best / likely / worst) and a probability-of-inundation raster are produced for today.</li>
            </ol>
        </div>
    </div><!-- end #live-view -->

    <!-- SIMULATION VIEW -->
    <div id="sim-view" style="display:none;">
    <div class="card" style="border-left:6px solid #b71c1c; background:#fff8f8; margin-top:0;">
      <h3 style="color:#b71c1c;">🌧 Rainfall Simulation — Return Period Selector</h3>
      <p style="color:#666; font-size:0.9rem;">
        Select a storm return period (5-yr to 200-yr). All panels update automatically.
        Use this to test "what would happen if" scenarios for emergency planning.
      </p>

      <div style="display:flex; align-items:center; gap:12px; margin:16px 0 8px;">
        <span style="font-weight:700; color:#555; min-width:36px;">5-yr</span>
        <input type="range" id="sim-slider" min="0" max="5" step="1" value="4"
               oninput="updateSim(SIM_STEPS[this.value])"
               style="flex:1; height:8px; accent-color:#b71c1c; cursor:pointer;">
        <span style="font-weight:700; color:#555; min-width:46px;">200-yr</span>
      </div>
      <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#888; margin:0 46px 12px;">
        <span>5</span><span>10</span><span>25</span><span>50</span><span>100</span><span>200</span>
      </div>

      <div id="sim-label" style="text-align:center; font-size:1.3rem; font-weight:700; color:#b71c1c; margin:8px 0;">
        T = 100-yr | Q = 455 cms | 1% annual probability
      </div>
      <div id="sim-alert-badge" style="text-align:center; margin:4px auto; display:inline-block;
           padding:6px 24px; border-radius:20px; font-weight:700; font-size:1rem;
           background:#b71c1c; color:#fff;">
        RED — Severe
      </div>

      <div class="hero-metrics" style="margin-top:16px;">
        <div class="hero-metric">
          <div class="v" id="sim-q">455</div><div class="l">Peak Q (cms)</div>
        </div>
        <div class="hero-metric">
          <div class="v" id="sim-maxdepth">12.00 m</div><div class="l">Max water depth</div>
        </div>
        <div class="hero-metric">
          <div class="v" id="sim-wetarea">5.28 km²</div><div class="l">Flood area</div>
        </div>
        <div class="hero-metric">
          <div class="v" id="sim-roads">154</div><div class="l">Roads at risk</div>
        </div>
      </div>
    </div>

    <div class="card">
      <h3 style="color:var(--accent-blue);">Simulated Flood Depth Map</h3>
      <img id="sim-depth-img" src="{sim_data.get(100, {}).get('b64', '')}"
           style="width:100%; border-radius:8px; max-width:900px; margin:0 auto; display:block;">
      <p style="color:#888; font-size:0.8rem; margin-top:6px; text-align:center;">
        Depth raster: FEMA BFE-IDW WSE − USGS 3DEP DEM, scaled by Leopold Q<sup>0.4</sup>.
        Fixed Blues colormap 0–12 m for cross-period comparability.
      </p>
    </div>

    <div class="card" style="border-left:6px solid #b71c1c; background:#fff8f8;">
      <b style="color:#b71c1c;">EOC Concerns for Selected Storm:</b>
      <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(220px,1fr)); gap:4px 20px; margin-top:8px; font-size:0.88rem;">
        <div>🔴 <b>Life safety:</b> potential loss of life in low-lying areas</div>
        <div>🚨 <b>Evacuations:</b> Patagonia HS + Sports Complex shelters</div>
        <div>🏠 <b>Property:</b> <span id="sim-eoc-wetarea">5.28 km²</span> inundated</div>
        <div>🚧 <b>Roads/Bridges:</b> <span id="sim-eoc-roads">154 road segments</span> at risk</div>
        <div>🏥 <b>Infrastructure:</b> <span id="sim-eoc-infra">12 of 16 POIs</span> flooded</div>
        <div>💧 <b>Water supply:</b> contamination risk if inundated</div>
        <div>♻ <b>Wastewater:</b> potential sewage spill</div>
        <div>⚡ <b>Power & telecom:</b> substations + cell towers at risk</div>
      </div>
    </div>

    <div class="card green">
      <h3>Recommended Actions</h3>
      <ul class="action-list" id="sim-actions">
        <li class="warn"><b>Evacuate</b> low-lying areas along Sonoita Creek.</li>
        <li class="warn">Do not cross flooded roadways — SR-82 may be closed.</li>
        <li>Open shelters: Patagonia HS (350 cap) + Sports Complex (500 cap).</li>
        <li>Activate all critical-infrastructure emergency plans (WWTP, water supply, power).</li>
      </ul>
    </div>

    <div style="margin:22px 0 10px;">
      <h3 style="color:var(--accent-blue);">Interactive Map — Simulation Layer</h3>
      <p style="color:#666; font-size:0.85rem; margin-bottom:8px;">
        The flood depth layer updates to show the selected return period (controlled via postMessage).
      </p>
      <iframe id="flood-map-iframe" src="dashboard_map.html"
        style="width:100%; height:640px; border:1px solid #d0d7de; border-radius:10px; background:#fff;">
      </iframe>
    </div>

    </div><!-- end #sim-view -->
    """
    return html


def build_task4_tab(task4: dict) -> str:
    """Developer-view Task 4 tab."""
    if not task4:
        return '<div class="card"><h3>Task 4 data not available</h3><p class="img-desc">Run <code>python scripts/07_task4_probabilistic.py</code> first.</p></div>'
    lib = task4.get("library", {})
    today = task4.get("today", {})
    days = task4.get("forecast_7day", [])

    # Forecast table rows
    rows = []
    for d in days:
        rows.append(f"""<tr>
            <td class="date-col">{d.get('date','--')}</td>
            <td>{d.get('rainfall_inches',{}).get('p50',0):.2f}&quot;</td>
            <td class="p90-col">{d.get('rainfall_inches',{}).get('p90',0):.2f}&quot;</td>
            <td>{d.get('discharge_cms',{}).get('p50',0):.2f}</td>
            <td>{d.get('discharge_cms',{}).get('p90',0):.2f}</td>
            <td>{d.get('likely',{}).get('max_depth_m',0):.2f}</td>
            <td>{d.get('likely',{}).get('wet_area_km2',0):.3f}</td>
            <td>{d.get('likely',{}).get('scenario_class','--')}</td>
        </tr>""")
    rows_html = "\n".join(rows) or "<tr><td colspan='8'>No data</td></tr>"

    return f"""
    <div class="card">
        <h3>Task 4: Probabilistic Flood Mapping (Library Lookup + Ensemble)</h3>
        <p class="img-desc">Pre-computed flood-map library indexed by discharge; linearly interpolates between two nearest stored maps for any predicted Q. Pattern follows NOAA OWP FIM and FEMA flood-library systems.</p>
        <div class="grid-4">
            <div class="metric-card"><div class="value">{lib.get('n_maps','--')}</div><div class="label">Library maps</div></div>
            <div class="metric-card"><div class="value">{lib.get('q_min_cms',0):.1f}-{lib.get('q_max_cms',0):.1f}</div><div class="label">Q range (cms)</div></div>
            <div class="metric-card green"><div class="value">{lib.get('grid_size','--')}&#178;</div><div class="label">Grid (cells)</div></div>
            <div class="metric-card orange"><div class="value">{lib.get('resolution_m','--')} m</div><div class="label">Pixel size</div></div>
        </div>
    </div>

    <div class="card">
        <h3>Today's Ensemble Output ({today.get('date','--')})</h3>
        <div class="grid-3">
            <div class="image-panel"><h3>Best (P10 rain)</h3>{_embed_image(OUTPUTS/'task4'/'today_best.png','best')}</div>
            <div class="image-panel"><h3>Likely (P50 rain)</h3>{_embed_image(OUTPUTS/'task4'/'today_likely.png','likely')}</div>
            <div class="image-panel"><h3>Worst (P90 rain)</h3>{_embed_image(OUTPUTS/'task4'/'today_worst.png','worst')}</div>
        </div>
        <div class="grid-2" style="margin-top:18px;">
            <div class="image-panel"><h3>Probability of Inundation</h3><p class="img-desc">Per-cell PoI using Pearson-Tukey 0.25/0.50/0.25 weighting over P10/P50/P90.</p>{_embed_image(OUTPUTS/'task4'/'today_poi.png','poi')}</div>
            <div class="image-panel"><h3>Expected Depth (weighted mean)</h3><p class="img-desc">Weighted mean depth raster across the ensemble.</p>{_embed_image(OUTPUTS/'task4'/'today_expected.png','expected')}</div>
        </div>
    </div>

    <div class="card">
        <h3>7-Day Forecast Table</h3>
        <table>
            <tr><th>Date</th><th>P50 Rain</th><th>P90 Rain</th><th>Q50 (cms)</th><th>Q90 (cms)</th><th>Max Depth (m)</th><th>Wet Area (km&#178;)</th><th>Class</th></tr>
            {rows_html}
        </table>
    </div>
    """


def build_task5_tab(task5: dict) -> str:
    """Developer-view Task 5 tab."""
    if not task5:
        return '<div class="card"><h3>Task 5 data not available</h3><p class="img-desc">Run <code>python scripts/08_task5_benchmarking.py</code> first.</p></div>'

    val = task5.get("validation", {})
    events = task5.get("historical_events", [])
    rp_table = task5.get("return_period_table", [])
    scores = task5.get("scores", {})
    atlas14 = task5.get("atlas14_24hr_in", {})
    fc_rp = task5.get("forecast_return_periods", [])

    # validation rows
    val_rows = "".join(
        f'<tr><td class="regime-name">{c["name"]}</td>'
        f'<td><span class="metric-{"good" if c["passed"] else "bad"}">{"PASS" if c["passed"] else "FAIL"}</span></td>'
        f'<td style="text-align:left;">{c["detail"]}</td></tr>'
        for c in val.get("checks", [])
    )

    # event rows
    def _ev_row(e: dict) -> str:
        obs = e.get("observed_peak_stage_m")
        res = e.get("depth_residual_m")
        obs_s = f"{obs:.2f}" if obs is not None else "--"
        res_s = f"{res:+.2f}" if res is not None else "--"
        return (
            f'<tr><td class="regime-name">{e.get("name","--")}</td>'
            f'<td>{e.get("date","--")}</td>'
            f'<td>{e.get("q_used_cms",0):.1f}</td>'
            f'<td>{e.get("predicted_max_depth_m",0):.2f}</td>'
            f'<td>{obs_s}</td>'
            f'<td>{res_s}</td></tr>'
        )
    ev_rows = "".join(_ev_row(e) for e in events)

    # return-period rows
    rp_rows = "".join(
        f'<tr><td class="regime-name">{r["return_period_yr"]}-yr</td>'
        f'<td>{r["atlas14_24hr_in"]:.2f}&quot;</td>'
        f'<td>{r["estimated_peak_q_cms"]:.1f}</td></tr>'
        for r in rp_table
    )

    # forecast RP rows
    fc_rows = "".join(
        f'<tr><td class="date-col">{r["date"]}</td>'
        f'<td>{r["rainfall_p50_in"]:.2f}&quot;</td>'
        f'<td>{r["rainfall_p90_in"]:.2f}&quot;</td>'
        f'<td>{r["q50_cms"]:.2f}</td>'
        f'<td>{r["q90_cms"]:.2f}</td>'
        f'<td>{r["rp_q50"]["nearest_rp_yr"]}</td>'
        f'<td>{r["rp_q90"]["nearest_rp_yr"]}</td></tr>'
        for r in fc_rp
    )

    mae = scores.get("depth_mae_m")
    bias = scores.get("depth_bias_m")
    mae_str = f"{mae:.3f} m" if mae is not None else "--"
    bias_str = f"{bias:+.3f} m" if bias is not None else "--"

    return f"""
    <div class="card">
        <h3>Task 5: Benchmarking & Validation</h3>
        <p class="img-desc">NOAA Atlas-14 return-period benchmarks, Sonoita Creek historical event replay, and end-to-end pipeline sanity checks.</p>
        <div class="grid-4">
            <div class="metric-card green"><div class="value">{val.get('n_passed',0)}/{val.get('n_checks',0)}</div><div class="label">Validation checks passed</div></div>
            <div class="metric-card"><div class="value">{scores.get('n_events_replayed',0)}</div><div class="label">Historical events replayed</div></div>
            <div class="metric-card orange"><div class="value">{mae_str}</div><div class="label">Depth MAE (events)</div></div>
            <div class="metric-card purple"><div class="value">{bias_str}</div><div class="label">Depth bias (events)</div></div>
        </div>
    </div>

    <div class="card">
        <h3>Pipeline Validation</h3>
        <table>
            <tr><th>Check</th><th>Result</th><th>Detail</th></tr>
            {val_rows}
        </table>
    </div>

    <div class="card">
        <h3>Historical Event Replay (Sonoita Creek)</h3>
        <p class="img-desc">Curated catalogue of documented floods; each Q is looked up through the library and compared to the observed peak stage.</p>
        <table>
            <tr><th>Event</th><th>Date</th><th>Q used (cms)</th><th>Predicted max depth (m)</th><th>Observed stage (m)</th><th>Residual (m)</th></tr>
            {ev_rows}
        </table>
    </div>

    <div class="card">
        <h3>NOAA Atlas-14 Return-Period Table (Patagonia AZ, 24-hr)</h3>
        <table>
            <tr><th>Return Period</th><th>Atlas-14 24hr Rainfall</th><th>Est. Peak Q (cms)</th></tr>
            {rp_rows}
        </table>
    </div>

    <div class="card">
        <h3>7-Day Forecast — Return-Period Context</h3>
        <table>
            <tr><th>Date</th><th>P50 Rain</th><th>P90 Rain</th><th>Q50 (cms)</th><th>Q90 (cms)</th><th>RP @ Q50</th><th>RP @ Q90</th></tr>
            {fc_rows}
        </table>
    </div>
    """


def generate_html() -> str:
    packet = load_alert_packet()
    config = load_inference_config()
    diag_text = load_diagnostic_summary()
    diag_metrics = parse_diagnostics(diag_text)
    task4 = load_task4_forecast()
    task5 = load_task5_report()
    task4_dir = OUTPUTS / "task4"

    ws = packet.get("watershed", {})
    current_alert = packet.get("current_alert", "GREEN")
    alert_lower = current_alert.lower()
    generated = packet.get("generated_utc", datetime.now().isoformat())
    pour_point_desc = ws.get("pour_point", {}).get("desc", "Hwy 82 Bridge")
    api_stats = packet.get("api_stats", {})
    api_total_calls = api_stats.get("total_calls", "--")
    api_success_pct = api_stats.get("success_rate_pct", "--")

    task1_img = build_image_section(
        "Task 1: GFS Ensemble Precipitation Forecast",
        OUTPUTS / "task1_forecast_dashboard.png",
        "31-member GFS ensemble precipitation forecast with IDF return period analysis for Upper Sonoita Creek watershed."
    )

    task2_images = ""
    img_map = [
        ("Observed vs Predicted Hydrograph", FIGURES / "hydrograph.png", "LSTM classifier + XGBoost magnitude model predicted discharge vs USGS observed streamflow."),
        ("ROC and Precision-Recall Curves", FIGURES / "roc_pr_curves.png", "Binary classifier performance — AUC-ROC and AUC-PR on test set."),
        ("Confusion Matrix", FIGURES / "confusion_matrix.png", "Classification performance at optimal F1 threshold."),
        ("Scatter: Observed vs Predicted Events", FIGURES / "scatter_events.png", "Event-day discharge prediction scatter plot."),
        ("Monthly Performance (NSE)", FIGURES / "monthly_performance.png", "Monthly Nash-Sutcliffe Efficiency showing monsoon season performance."),
        ("Training Progression", FIGURES / "progression.png", "Loss and metric curves during LSTM training."),
    ]
    plots_map = [
        ("Hydrograph (Full Test Period)", PLOTS / "01_hydrograph.png", "Full test period hydrograph comparison."),
        ("Scatter: Observed vs Predicted", PLOTS / "02_scatter_obs_vs_pred.png", "Scatter plot of predicted vs observed discharge."),
        ("Confusion Matrix (Diagnostic)", PLOTS / "03_confusion_matrix.png", "Diagnostic confusion matrix."),
        ("Residual vs Observed", PLOTS / "04_residual_vs_observed.png", "Residual analysis — bias patterns across flow regimes."),
        ("Monthly NSE", PLOTS / "05_monthly_nse.png", "Monthly Nash-Sutcliffe Efficiency."),
        ("Flow Duration Curve", PLOTS / "06_flow_duration_curve.png", "Exceedance probability comparison."),
        ("Cumulative Volume", PLOTS / "07_cumulative_volume.png", "Cumulative volume tracking accuracy."),
    ]

    for title, path, desc in img_map:
        task2_images += build_image_section(title, path, desc)
    for title, path, desc in plots_map:
        task2_images += build_image_section(title, path, desc)

    task2_eval = build_image_section(
        "Task 2: 4-Panel Evaluation Summary",
        REPORTS / "task2_evaluation.png",
        "Comprehensive evaluation: hydrograph, scatter, confusion matrix, and monthly NSE."
    )

    sonoita_eval = build_image_section(
        "Task 2: Sonoita Creek Transfer (USGS 09481500)",
        REPORTS / "task2_sonoita_transfer.png",
        "XGBoost hurdle model transferred to Sonoita Creek target watershed. NSE=0.676, PBIAS=-24.5%, F1=0.708."
    )

    sonoita_config = {}
    sonoita_cfg_path = MODELS / "sonoita" / "inference_config.json"
    if sonoita_cfg_path.exists():
        sonoita_config = json.loads(sonoita_cfg_path.read_text())

    data_diag = build_image_section(
        "Data Diagnostics",
        FIGURES / "data_diagnostics.png",
        "Input data quality and distribution diagnostics."
    )

    baseline_img = build_image_section(
        "Baseline Comparison",
        FIGURES / "baseline_results.png",
        "Hurdle model performance compared to statistical baselines."
    )

    forecast_rows = build_forecast_rows(packet)
    regime_rows = build_regime_table(diag_text)

    fixes = config.get("fixes_applied", [])
    fixes_html = "".join(f"<li>{f}</li>" for f in fixes) if fixes else "<li>Standard configuration</li>"

    idf = packet.get("idf_10yr_benchmarks_inches", {})
    idf_html = ""
    if idf:
        idf_html = "<br>".join(f"<strong>{k}:</strong> {v} in" for k, v in idf.items())


    # Generate simulation mode data (return periods 5,10,25,50,100,200)
    sim_data = generate_sim_pngs()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AFFI Project Dashboard — Sonoita Creek Flood Forecasting</title>
    <style>
        :root {{
            --bg-primary: #0f1923;
            --bg-secondary: #1a2332;
            --bg-card: #1e2d3d;
            --border: rgba(255,255,255,0.08);
            --text-primary: #e8edf2;
            --text-secondary: #8899aa;
            --accent-blue: #4ea8de;
            --accent-green: #2ecc71;
            --accent-orange: #f39c12;
            --accent-red: #e74c3c;
            --accent-purple: #9b59b6;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
        }}
        .container {{ max-width: 1600px; margin: 0 auto; padding: 30px 40px; }}

        /* Header */
        .header {{
            text-align: center;
            padding: 40px 0 30px;
            border-bottom: 2px solid var(--accent-blue);
            margin-bottom: 40px;
        }}
        .header h1 {{
            font-size: 2.4rem;
            font-weight: 700;
            color: var(--accent-blue);
            letter-spacing: -0.5px;
        }}
        .header .subtitle {{
            font-size: 1.1rem;
            color: var(--text-secondary);
            margin-top: 8px;
        }}
        .header .author {{
            font-size: 0.95rem;
            color: var(--accent-purple);
            margin-top: 12px;
            font-weight: 500;
        }}

        /* Navigation Tabs */
        .nav-tabs {{
            display: flex;
            gap: 0;
            margin-bottom: 30px;
            border-bottom: 2px solid var(--border);
            overflow-x: auto;
        }}
        .nav-tab {{
            padding: 14px 28px;
            cursor: pointer;
            color: var(--text-secondary);
            font-weight: 600;
            font-size: 0.95rem;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
            white-space: nowrap;
        }}
        .nav-tab:hover {{ color: var(--text-primary); }}
        .nav-tab.active {{
            color: var(--accent-blue);
            border-bottom-color: var(--accent-blue);
        }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}

        /* Alert Banner */
        .alert-banner {{
            text-align: center;
            padding: 18px 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            font-size: 1.6rem;
            font-weight: 700;
            letter-spacing: 1px;
        }}
        .alert-green {{ background: linear-gradient(135deg, #27ae60, #2ecc71); }}
        .alert-advisory {{ background: linear-gradient(135deg, #f39c12, #f1c40f); color: #000; }}
        .alert-watch {{ background: linear-gradient(135deg, #e67e22, #f39c12); }}
        .alert-warning {{ background: linear-gradient(135deg, #c0392b, #e74c3c); }}

        /* Cards & Panels */
        .card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
        }}
        .card h3 {{
            color: var(--accent-blue);
            font-size: 1.15rem;
            margin-bottom: 16px;
            padding-bottom: 10px;
            border-bottom: 1px solid var(--border);
        }}
        .card.green h3 {{ color: var(--accent-green); }}
        .card.orange h3 {{ color: var(--accent-orange); }}
        .card.purple h3 {{ color: var(--accent-purple); }}

        /* Grids */
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
        .grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }}
        .grid-4 {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }}
        @media (max-width: 1000px) {{
            .grid-2, .grid-3 {{ grid-template-columns: 1fr; }}
            .grid-4 {{ grid-template-columns: repeat(2, 1fr); }}
        }}

        /* Metric Cards */
        .metric-card {{
            background: rgba(78, 168, 222, 0.1);
            border: 1px solid rgba(78, 168, 222, 0.2);
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }}
        .metric-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--accent-blue);
        }}
        .metric-card .label {{
            font-size: 0.82rem;
            color: var(--text-secondary);
            margin-top: 6px;
        }}
        .metric-card.green .value {{ color: var(--accent-green); }}
        .metric-card.orange .value {{ color: var(--accent-orange); }}
        .metric-card.red .value {{ color: var(--accent-red); }}
        .metric-card.purple .value {{ color: var(--accent-purple); }}
        .metric-good {{ color: var(--accent-green) !important; font-weight: 600; }}
        .metric-ok {{ color: var(--accent-orange) !important; font-weight: 600; }}
        .metric-bad {{ color: var(--accent-red) !important; font-weight: 600; }}

        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            background: rgba(78, 168, 222, 0.15);
            padding: 12px 10px;
            text-align: center;
            font-weight: 600;
            font-size: 0.9rem;
            color: var(--accent-blue);
        }}
        td {{
            padding: 10px;
            text-align: center;
            border-bottom: 1px solid var(--border);
            font-size: 0.9rem;
        }}
        .date-col {{ font-weight: 600; color: var(--accent-blue); }}
        .p90-col {{ color: var(--accent-red); font-weight: 500; }}
        .regime-name {{ text-align: left; font-weight: 600; color: var(--accent-blue); }}

        /* Alert Badges */
        .alert-badge {{
            display: inline-block;
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 700;
            letter-spacing: 0.5px;
        }}
        .badge-green {{ background: var(--accent-green); color: #fff; }}
        .badge-advisory {{ background: var(--accent-orange); color: #000; }}
        .badge-watch {{ background: #e67e22; color: #fff; }}
        .badge-warning {{ background: var(--accent-red); color: #fff; }}

        /* Images */
        .image-panel {{
            margin-bottom: 30px;
        }}
        .image-panel h3 {{
            color: var(--accent-blue);
            font-size: 1.1rem;
            margin-bottom: 8px;
        }}
        .img-desc {{
            color: var(--text-secondary);
            font-size: 0.88rem;
            margin-bottom: 12px;
        }}
        .result-img {{
            width: 100%;
            border-radius: 10px;
            border: 1px solid var(--border);
        }}

        /* Watershed Info */
        .ws-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 12px;
        }}
        .ws-item {{
            background: rgba(78, 168, 222, 0.06);
            padding: 12px 16px;
            border-radius: 8px;
            border-left: 3px solid var(--accent-blue);
        }}
        .ws-item .ws-label {{ font-size: 0.78rem; color: var(--text-secondary); }}
        .ws-item .ws-value {{ font-size: 1rem; font-weight: 600; color: var(--text-primary); }}

        /* Pipeline Status */
        .pipeline {{
            display: flex;
            gap: 0;
            align-items: center;
            flex-wrap: wrap;
            margin: 20px 0;
        }}
        .pipeline-stage {{
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            text-align: center;
            flex: 1;
            min-width: 140px;
        }}
        .pipeline-arrow {{
            font-size: 1.5rem;
            color: var(--text-secondary);
            padding: 0 4px;
        }}
        .stage-done {{ background: rgba(46, 204, 113, 0.2); border: 1px solid rgba(46, 204, 113, 0.4); color: var(--accent-green); }}
        .stage-partial {{ background: rgba(243, 156, 18, 0.2); border: 1px solid rgba(243, 156, 18, 0.4); color: var(--accent-orange); }}
        .stage-pending {{ background: rgba(255,255,255,0.05); border: 1px solid var(--border); color: var(--text-secondary); }}

        /* Config List */
        .config-list {{ list-style: none; }}
        .config-list li {{
            padding: 8px 0;
            border-bottom: 1px solid var(--border);
            font-size: 0.9rem;
        }}
        .config-list li:last-child {{ border-bottom: none; }}
        .config-key {{ color: var(--accent-blue); font-weight: 600; }}

        /* Footer */
        .footer {{
            text-align: center;
            padding: 30px 0;
            margin-top: 40px;
            border-top: 1px solid var(--border);
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}

        /* View-Mode Switcher (User / Developer) */
        .mode-switch {{
            display: flex;
            justify-content: center;
            gap: 8px;
            margin: 20px auto 30px;
            background: var(--bg-secondary);
            padding: 6px;
            border-radius: 999px;
            max-width: 420px;
            border: 1px solid var(--border);
        }}
        .mode-btn {{
            padding: 10px 26px;
            border-radius: 999px;
            cursor: pointer;
            font-weight: 700;
            font-size: 0.95rem;
            color: var(--text-secondary);
            transition: all 0.2s;
        }}
        .mode-btn.active {{
            background: linear-gradient(135deg, var(--accent-blue), #6cb6f0);
            color: #fff;
            box-shadow: 0 4px 14px rgba(78,168,222,0.35);
        }}
        .view-pane {{ display: none; }}
        .view-pane.active {{ display: block; }}

        /* User View Hero */
        .hero-alert {{
            display: grid;
            grid-template-columns: 1.4fr 1fr;
            gap: 24px;
            align-items: stretch;
            margin-bottom: 28px;
        }}
        @media (max-width: 1000px) {{ .hero-alert {{ grid-template-columns: 1fr; }} }}
        .hero-map {{
            background: var(--bg-card);
            border-radius: 14px;
            padding: 14px;
            border: 1px solid var(--border);
        }}
        .hero-map img {{ width: 100%; border-radius: 10px; display: block; }}
        .hero-side {{
            background: linear-gradient(135deg, #1e2d3d 0%, #243a52 100%);
            border-radius: 14px;
            padding: 26px;
            border: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}
        .hero-status {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 1.5px;
            margin-bottom: 8px;
        }}
        .hero-level {{
            font-size: 2.6rem;
            font-weight: 800;
            margin-bottom: 14px;
            letter-spacing: -0.5px;
        }}
        .hero-caption {{
            font-size: 1.05rem;
            color: var(--text-primary);
            line-height: 1.55;
            margin-bottom: 18px;
        }}
        .hero-metrics {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }}
        .hero-metric {{
            background: rgba(0,0,0,0.25);
            padding: 12px 14px;
            border-radius: 8px;
        }}
        .hero-metric .v {{ font-size: 1.5rem; font-weight: 700; color: var(--accent-blue); }}
        .hero-metric .l {{ font-size: 0.78rem; color: var(--text-secondary); }}

        /* Three-scenario strip */
        .scenario-strip {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 18px;
            margin-bottom: 28px;
        }}
        @media (max-width: 1000px) {{ .scenario-strip {{ grid-template-columns: 1fr; }} }}
        .scenario-card {{
            background: var(--bg-card);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid var(--border);
        }}
        .scenario-card h4 {{ color: var(--accent-blue); margin-bottom: 10px; font-size: 1rem; }}
        .scenario-card.likely h4 {{ color: var(--accent-orange); }}
        .scenario-card.worst h4 {{ color: var(--accent-red); }}
        .scenario-card img {{ width: 100%; border-radius: 8px; display: block; }}
        .scenario-stats {{
            display: flex;
            justify-content: space-between;
            margin-top: 12px;
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}
        .scenario-stats strong {{ color: var(--text-primary); }}

        /* 7-Day strip */
        .day-strip {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            gap: 10px;
            margin-bottom: 28px;
        }}
        @media (max-width: 1000px) {{ .day-strip {{ grid-template-columns: repeat(2, 1fr); }} }}
        .day-card {{
            background: var(--bg-card);
            border-radius: 10px;
            padding: 10px;
            text-align: center;
            border: 1px solid var(--border);
        }}
        .day-card .day-date {{ font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 6px; }}
        .day-card img {{ width: 100%; border-radius: 6px; }}
        .day-card .day-meta {{ font-size: 0.75rem; color: var(--text-primary); margin-top: 6px; }}
        .day-card .day-badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; font-weight: 700; margin-top: 4px; }}
        .day-card .badge-green {{ background: var(--accent-green); color: #fff; }}
        .day-card .badge-watch {{ background: #e67e22; color: #fff; }}
        .day-card .badge-advisory {{ background: var(--accent-orange); color: #000; }}
        .day-card .badge-warning {{ background: var(--accent-red); color: #fff; }}

        /* Action list */
        .action-list {{ list-style: none; padding: 0; }}
        .action-list li {{
            padding: 12px 16px;
            margin-bottom: 8px;
            background: rgba(78,168,222,0.08);
            border-left: 4px solid var(--accent-blue);
            border-radius: 6px;
            font-size: 0.95rem;
        }}
        .action-list li.warn {{ background: rgba(231,76,60,0.10); border-left-color: var(--accent-red); }}
        .action-list li.ok {{ background: rgba(46,204,113,0.10); border-left-color: var(--accent-green); }}

    </style>
</head>
<body>
<div class="container">

    <div class="header">
        <h1>Arizona Flash Flood Inundation (AFFI)</h1>
        <div class="subtitle">AI Early Warning System — All 6 Pipeline Tasks Complete</div>
        <div class="author">Solman Raju Sarva | University of Arizona | MS Information Science — Machine Learning</div>
    </div>

    <!-- Mode Switch: User vs Developer View -->
    <div class="mode-switch">
        <button class="mode-btn active" onclick="switchMode('user', this)">User View</button>
        <button class="mode-btn" onclick="switchMode('developer', this)">Developer View</button>
    </div>

    <!-- ==================== USER VIEW PANE ==================== -->
    <div id="user-pane" class="view-pane active">
        {build_user_view(packet, task4, sim_data)}
    </div>

    <!-- ==================== DEVELOPER VIEW PANE ==================== -->
    <div id="developer-pane" class="view-pane">

    <!-- Pipeline Progress -->
    <div class="card">
        <h3>6-Stage Pipeline Progress</h3>
        <div class="pipeline">
            <div class="pipeline-stage stage-done">Task 1<br><small>Meteorology</small></div>
            <div class="pipeline-arrow">&#8594;</div>
            <div class="pipeline-stage stage-done">Task 2<br><small>Hydrology (XGBoost)</small></div>
            <div class="pipeline-arrow">&#8594;</div>
            <div class="pipeline-stage stage-done">Task 3<br><small>Hydraulics (Framework)</small></div>
            <div class="pipeline-arrow">&#8594;</div>
            <div class="pipeline-stage stage-done">Task 4<br><small>Probabilistic</small></div>
            <div class="pipeline-arrow">&#8594;</div>
            <div class="pipeline-stage stage-done">Task 5<br><small>Benchmarking</small></div>
            <div class="pipeline-arrow">&#8594;</div>
            <div class="pipeline-stage stage-done">Task 6<br><small>API + Dashboard</small></div>
        </div>
        <div style="margin-top:12px; color:var(--text-secondary); font-size:0.88rem;">
            <strong style="color:var(--accent-green);">&#9679;</strong> Complete &nbsp;
            <strong style="color:var(--accent-orange);">&#9679;</strong> In Progress &nbsp;
            <strong style="color:var(--text-secondary);">&#9679;</strong> Pending
        </div>
    </div>

    <!-- Navigation Tabs -->
    <div class="nav-tabs">
        <div class="nav-tab active" onclick="switchTab('overview', this)">Overview</div>
        <div class="nav-tab" onclick="switchTab('task1', this)">Task 1: Meteorology</div>
        <div class="nav-tab" onclick="switchTab('task2', this)">Task 2: Hydrology</div>
        <div class="nav-tab" onclick="switchTab('task2-plots', this)">Task 2: Diagnostic Plots</div>
        <div class="nav-tab" onclick="switchTab('task3', this)">Task 3: Hydraulics</div>
        <div class="nav-tab" onclick="switchTab('task4', this)">Task 4: Probabilistic</div>
        <div class="nav-tab" onclick="switchTab('task5', this)">Task 5: Benchmarking</div>
        <div class="nav-tab" onclick="switchTab('architecture', this)">Architecture</div>
    </div>

    <!-- ==================== OVERVIEW TAB ==================== -->
    <div id="tab-overview" class="tab-content active">
        <div class="alert-banner alert-{alert_lower}">
            Current Alert Level: {current_alert}
        </div>

        <div class="card">
            <h3>Watershed: {ws.get('name', 'Upper Sonoita Creek')}</h3>
            <div class="ws-info">
                <div class="ws-item"><div class="ws-label">HUC Code</div><div class="ws-value">{ws.get('huc', '15050301')}</div></div>
                <div class="ws-item"><div class="ws-label">Location</div><div class="ws-value">{ws.get('county', 'Santa Cruz')}, {ws.get('state', 'AZ')}</div></div>
                <div class="ws-item"><div class="ws-label">Drainage Area</div><div class="ws-value">{ws.get('area_km2', 510)} km&#178;</div></div>
                <div class="ws-item"><div class="ws-label">USGS Gauge</div><div class="ws-value">{ws.get('usgs_gauge', '09481500')}</div></div>
                <div class="ws-item"><div class="ws-label">Pour Point</div><div class="ws-value">{pour_point_desc}</div></div>
                <div class="ws-item"><div class="ws-label">Data Source</div><div class="ws-value">{packet.get('data_source', 'GFS Ensemble API')}</div></div>
            </div>
        </div>

        <div class="grid-2">
            <div class="card">
                <h3>Task 1 Summary — Precipitation Forecast</h3>
                <div class="grid-4">
                    <div class="metric-card green">
                        <div class="value">{api_total_calls}</div>
                        <div class="label">API Calls</div>
                    </div>
                    <div class="metric-card green">
                        <div class="value">{api_success_pct}%</div>
                        <div class="label">Success Rate</div>
                    </div>
                    <div class="metric-card">
                        <div class="value">31</div>
                        <div class="label">GFS Ensemble Members</div>
                    </div>
                    <div class="metric-card">
                        <div class="value">7</div>
                        <div class="label">Forecast Days</div>
                    </div>
                </div>
                <div style="margin-top:16px;">
                    <strong style="color:var(--accent-blue);">IDF 10-Year Benchmarks (NOAA Atlas 14):</strong><br>
                    <span style="color:var(--text-secondary); font-size:0.9rem;">{idf_html}</span>
                </div>
            </div>

            <div class="card green">
                <h3>Task 2 Summary — Hurdle Model (Babocomari River)</h3>
                <div class="grid-4">
                    <div class="metric-card green">
                        <div class="value">{config.get('auc_roc', diag_metrics.get('auc_roc', '--')):.4f}</div>
                        <div class="label">AUC-ROC</div>
                    </div>
                    <div class="metric-card green">
                        <div class="value">{config.get('auc_pr', diag_metrics.get('auc_pr', '--')):.4f}</div>
                        <div class="label">AUC-PR</div>
                    </div>
                    <div class="metric-card orange">
                        <div class="value">{config.get('test_nse', '--'):.4f}</div>
                        <div class="label">Test NSE</div>
                    </div>
                    <div class="metric-card purple">
                        <div class="value">{config.get('f1_score', '--'):.4f}</div>
                        <div class="label">F1 Score</div>
                    </div>
                </div>
                <div style="margin-top:16px;">
                    <strong style="color:var(--accent-green);">Status:</strong>
                    <span style="color:var(--accent-orange);">Base basin (Babocomari) trained. Transfer to Sonoita Creek pending.</span>
                </div>
            </div>
        </div>
    </div>

    <!-- ==================== TASK 1 TAB ==================== -->
    <div id="tab-task1" class="tab-content">
        <div class="alert-banner alert-{alert_lower}">
            Forecast Alert: {current_alert} | Generated: {generated}
        </div>

        <div class="card">
            <h3>7-Day Ensemble Precipitation Forecast</h3>
            <table>
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>P50 24hr</th>
                        <th>P90 24hr</th>
                        <th>P50 1hr</th>
                        <th>Return Period</th>
                        <th>Alert</th>
                    </tr>
                </thead>
                <tbody>
                    {forecast_rows}
                </tbody>
            </table>
        </div>

        {task1_img}

        <div class="card">
            <h3>Alert Threshold Logic (White Paper Section 4.7)</h3>
            <table>
                <thead>
                    <tr><th>Level</th><th>24hr Threshold</th><th>1hr Threshold</th><th>Condition</th></tr>
                </thead>
                <tbody>
                    <tr><td><span class="alert-badge badge-green">GREEN</span></td><td>&lt; 25% of 10yr IDF</td><td>&lt; 25% of 10yr IDF</td><td>No significant rainfall</td></tr>
                    <tr><td><span class="alert-badge badge-advisory">ADVISORY</span></td><td>25-40% of 10yr IDF</td><td>25-40% of 10yr IDF</td><td>Elevated rainfall, monitor</td></tr>
                    <tr><td><span class="alert-badge badge-watch">WATCH</span></td><td>40-65% of 10yr IDF</td><td>40-65% of 10yr IDF</td><td>Flash flood possible</td></tr>
                    <tr><td><span class="alert-badge badge-warning">WARNING</span></td><td>&gt; 65% of 10yr IDF</td><td>&gt; 65% of 10yr IDF</td><td>Flash flood expected</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <!-- ==================== TASK 2 TAB ==================== -->
    <div id="tab-task2" class="tab-content">
        <div class="card green">
            <h3>Hurdle Model Architecture</h3>
            <div class="grid-2">
                <div>
                    <h4 style="color:var(--accent-green); margin-bottom:10px;">Stage 1: LSTM Binary Classifier</h4>
                    <ul class="config-list">
                        <li><span class="config-key">Architecture:</span> LSTM (128 hidden, 2 layers, dropout=0.3)</li>
                        <li><span class="config-key">Input:</span> 30-day lookback window</li>
                        <li><span class="config-key">Output:</span> P(runoff event) via sigmoid</li>
                        <li><span class="config-key">Threshold:</span> {config.get('f1_threshold', 0.65):.2f} (F1-optimized)</li>
                        <li><span class="config-key">AUC-ROC:</span> {config.get('auc_roc', '--')}</li>
                        <li><span class="config-key">F1 Score:</span> {config.get('f1_score', '--')}</li>
                    </ul>
                </div>
                <div>
                    <h4 style="color:var(--accent-orange); margin-bottom:10px;">Stage 2: XGBoost Magnitude Regressor</h4>
                    <ul class="config-list">
                        <li><span class="config-key">Model:</span> {config.get('magnitude_model', 'XGBoost')}</li>
                        <li><span class="config-key">Method:</span> {config.get('method', 'hard_gate')}</li>
                        <li><span class="config-key">Temperature:</span> {config.get('temperature', '--')}</li>
                        <li><span class="config-key">Test NSE:</span> {config.get('test_nse', '--')}</li>
                        <li><span class="config-key">Fixes Applied:</span></li>
                    </ul>
                    <ul style="margin-left:20px; color:var(--text-secondary); font-size:0.85rem;">
                        {fixes_html}
                    </ul>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>Performance Metrics — Test Period (2019-2024)</h3>
            <div class="grid-4">
                <div class="metric-card green">
                    <div class="value">{diag_metrics.get('auc_roc', '--')}</div>
                    <div class="label">AUC-ROC</div>
                </div>
                <div class="metric-card green">
                    <div class="value">{diag_metrics.get('auc_pr', '--')}</div>
                    <div class="label">AUC-PR</div>
                </div>
                <div class="metric-card orange">
                    <div class="value">{diag_metrics.get('nse', '--')}</div>
                    <div class="label">Overall NSE</div>
                </div>
                <div class="metric-card red">
                    <div class="value">{diag_metrics.get('pbias', '--')}</div>
                    <div class="label">PBIAS</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>Regime-Based Performance Breakdown</h3>
            <table>
                <thead>
                    <tr><th style="text-align:left;">Regime</th><th>N Days</th><th>NSE</th><th>PBIAS</th></tr>
                </thead>
                <tbody>
                    {regime_rows}
                </tbody>
            </table>
        </div>

        {task2_eval}
        {sonoita_eval}

        <div class="card">
            <h3>Sonoita Creek Transfer Metrics</h3>
            <table class="data-table">
                <thead><tr><th>Metric</th><th>Babocomari (Base)</th><th>Sonoita (Transfer)</th></tr></thead>
                <tbody>
                    <tr><td>NSE</td><td>{config.get('test_nse', '--'):.4f}</td><td>{sonoita_config.get('test_nse', 0):.4f}</td></tr>
                    <tr><td>PBIAS</td><td>{config.get('test_pbias', '--')}</td><td>{sonoita_config.get('test_pbias', 0):.1f}%</td></tr>
                    <tr><td>F1 Score</td><td>{config.get('f1_score', '--'):.3f}</td><td>{sonoita_config.get('f1_score', 0):.3f}</td></tr>
                    <tr><td>AUC-ROC</td><td>{config.get('auc_roc', '--'):.4f}</td><td>{sonoita_config.get('auc_roc', 0):.4f}</td></tr>
                </tbody>
            </table>
        </div>

        {task2_images}
    </div>

    <!-- ==================== TASK 2 DIAGNOSTIC PLOTS TAB ==================== -->
    <div id="tab-task2-plots" class="tab-content">
        <div class="card">
            <h3>Diagnostic Summary</h3>
            <pre style="background:rgba(0,0,0,0.3); padding:16px; border-radius:8px; font-size:0.85rem; overflow-x:auto; color:var(--text-secondary);">{diag_text}</pre>
        </div>

        {data_diag}
        {baseline_img}
    </div>

    <!-- ==================== TASK 3: HYDRAULICS TAB ==================== -->
    <div id="tab-task3" class="tab-content">
        <div class="card">
            <h3>Task 3 — Hydraulic Surrogate Model (Phase 1 Complete)</h3>
            <p style="color:var(--text-secondary); margin-bottom:16px;">
                Physics-guided ResUNet deep learning model converts Task 2 discharge predictions into spatial flood depth and extent maps.
                Trained on 80 Manning's equation scenarios on synthetic DEM (256x256 @ 10m). Both performance targets met.
            </p>
        </div>

        <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:16px; margin-bottom:24px;">
            <div class="card" style="text-align:center;">
                <div style="font-size:0.8rem; color:var(--text-secondary);">Depth RMSE</div>
                <div style="font-size:1.8rem; font-weight:700; color:var(--accent-green);">0.034 m</div>
                <div style="font-size:0.75rem; color:var(--text-secondary);">Target &lt; 0.30m &#10003;</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:0.8rem; color:var(--text-secondary);">CSI</div>
                <div style="font-size:1.8rem; font-weight:700; color:var(--accent-green);">0.834</div>
                <div style="font-size:0.75rem; color:var(--text-secondary);">Target &gt; 0.70 &#10003;</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:0.8rem; color:var(--text-secondary);">Inundation F1</div>
                <div style="font-size:1.8rem; font-weight:700; color:var(--accent-green);">0.909</div>
                <div style="font-size:0.75rem; color:var(--text-secondary);">Wet/dry classification</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:0.8rem; color:var(--text-secondary);">Inundation Recall</div>
                <div style="font-size:1.8rem; font-weight:700; color:var(--accent-green);">0.998</div>
                <div style="font-size:0.75rem; color:var(--text-secondary);">Flood detection rate</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:0.8rem; color:var(--text-secondary);">Peak Depth RMSE</div>
                <div style="font-size:1.8rem; font-weight:700; color:var(--accent-green);">0.125 m</div>
                <div style="font-size:0.75rem; color:var(--text-secondary);">Depth &gt; 1m cells</div>
            </div>
            <div class="card" style="text-align:center;">
                <div style="font-size:0.8rem; color:var(--text-secondary);">Volume Error</div>
                <div style="font-size:1.8rem; font-weight:700; color:var(--accent-yellow);">+16.7%</div>
                <div style="font-size:0.75rem; color:var(--text-secondary);">Slight over-prediction</div>
            </div>
        </div>

        <div class="card">
            <h3>ResUNet Architecture &amp; Training</h3>
            <p style="color:var(--text-secondary); margin-bottom:12px;">
                4-channel input (log-discharge, DEM, slope, channel distance) &#8594; 256x256 grid at 10m resolution (6.55 km&#178;).
                Encoder: 4&#8594;32&#8594;64&#8594;128&#8594;256. Bottleneck: 512. Decoder with skip connections. 10.5M parameters.
            </p>
            <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px;">
                <div>
                    <h4 style="color:var(--accent-blue); margin-bottom:8px;">Model Details</h4>
                    <ul style="color:var(--text-secondary); font-size:0.85rem; padding-left:20px;">
                        <li>Loss: Balanced MSE + 5x Dice loss</li>
                        <li>Optimizer: AdamW (lr=1e-3, wd=1e-4)</li>
                        <li>Scheduler: CosineAnnealing, patience=30</li>
                        <li>Best epoch: 140/200 (early stopped at 170)</li>
                        <li>Training time: ~17 min on Apple MPS</li>
                    </ul>
                </div>
                <div>
                    <h4 style="color:var(--accent-blue); margin-bottom:8px;">Training Data</h4>
                    <ul style="color:var(--text-secondary); font-size:0.85rem; padding-left:20px;">
                        <li><strong>Phase 1 (COMPLETE):</strong> 80 Manning's scenarios</li>
                        <li>Synthetic DEM: 256x256 @ 10m grid</li>
                        <li>Q range: 1.0 - 300.0 cms</li>
                        <li><strong>Phase 2:</strong> HEC-RAS 2D (250 scenarios)</li>
                        <li><strong>Phase 3:</strong> Real event calibration</li>
                    </ul>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>Manning's 1-D Proxy Metrics</h3>
            <p style="color:var(--text-secondary); margin-bottom:12px;">
                Sonoita Creek channel geometry: channel 50m, floodplain 500m, bed slope 0.008, Manning's n = 0.045/0.080.
                Lookup table spans Q = 0.1-500 cms across 98 entries.
            </p>
            <div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px;">
                <div style="text-align:center; padding:8px;">
                    <div style="font-size:0.75rem; color:var(--text-secondary);">Manning's Depth RMSE</div>
                    <div style="font-size:1.3rem; font-weight:700; color:var(--accent-green);">0.101 m</div>
                </div>
                <div style="text-align:center; padding:8px;">
                    <div style="font-size:0.75rem; color:var(--text-secondary);">Manning's Depth Bias</div>
                    <div style="font-size:1.3rem; font-weight:700; color:var(--accent-green);">-0.005 m</div>
                </div>
                <div style="text-align:center; padding:8px;">
                    <div style="font-size:0.75rem; color:var(--text-secondary);">Manning's Inundation F1</div>
                    <div style="font-size:1.3rem; font-weight:700; color:var(--accent-green);">0.843</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h3>Next Steps</h3>
            <ul style="color:var(--text-secondary); font-size:0.9rem; line-height:2; padding-left:20px;">
                <li>Acquire USGS 3DEP 10m LiDAR DEM — retrain ResUNet on real terrain</li>
                <li>Build HEC-RAS 2D model for Phase 2 simulation library (250 scenarios)</li>
                <li>Validate against historical flood extents (FEMA, Sentinel-1 SAR)</li>
                <li>Implement Monte Carlo uncertainty propagation (N=100 ensemble)</li>
            </ul>
        </div>
    </div>

    <!-- ==================== TASK 4 TAB ==================== -->
    <div id="tab-task4" class="tab-content">
        {build_task4_tab(task4)}
    </div>

    <!-- ==================== TASK 5 TAB ==================== -->
    <div id="tab-task5" class="tab-content">
        {build_task5_tab(task5)}
    </div>

    <!-- ==================== ARCHITECTURE TAB ==================== -->
    <div id="tab-architecture" class="tab-content">
        <div class="card">
            <h3>AFFI 6-Stage Physics-Guided AI Pipeline</h3>
            <div style="font-size:0.95rem; color:var(--text-secondary); line-height:1.8;">
                <p><strong style="color:var(--accent-green);">Task 1 — Meteorology (COMPLETE):</strong>
                GFS 31-member ensemble ingestion via Open-Meteo API. MAP computation over watershed grid.
                NOAA Atlas 14 IDF benchmarking. Alert classification (GREEN/ADVISORY/WATCH/WARNING).</p>
                <br>
                <p><strong style="color:var(--accent-green);">Task 2 — Hydrology (COMPLETE):</strong>
                Hurdle model: XGBoost classifier (flood/no-flood) + XGBoost regressor (magnitude), blended with direct regression.
                Base model trained on Babocomari River (USGS 09471000, NSE=0.348). Transferred to Sonoita Creek (USGS 09481500, NSE=0.676).</p>
                <br>
                <p><strong style="color:var(--accent-green);">Task 3 — Hydraulics (PHASE 1 COMPLETE):</strong>
                ResUNet (10.5M params) trained on 80 Manning's scenarios on synthetic DEM. Depth RMSE=0.034m, CSI=0.834, F1=0.909.
                Converts Task 2 discharge to 256x256 spatial flood depth maps at 10m resolution.</p>
                <br>
                <p><strong style="color:var(--accent-green);">Task 4 — Probabilistic Output (COMPLETE):</strong>
                Flood-map library lookup with linear discharge interpolation. P10/P50/P90 rainfall ensemble propagated through SCS-CN runoff model into best/likely/worst depth maps + Probability-of-Inundation raster. Pattern mirrors NOAA OWP FIM library.</p>
                <br>
                <p><strong style="color:var(--accent-green);">Task 5 — Benchmarking (COMPLETE):</strong>
                NOAA Atlas-14 return-period benchmarking (1/2/5/10/25/50/100/200/500-yr), Sonoita Creek historical event replay (4 events catalogued), end-to-end pipeline validation (7 sanity checks).</p>
                <br>
                <p><strong style="color:var(--accent-green);">Task 6 — Alert & Dashboard (COMPLETE):</strong>
                FastAPI government API with role-based auth, Streamlit EOC dashboard,
                APScheduler auto-refresh (6hr GFS cycles), audit logging.</p>
            </div>
        </div>

        <div class="card">
            <h3>Technology Stack</h3>
            <div class="grid-3">
                <div>
                    <h4 style="color:var(--accent-blue); margin-bottom:8px;">Core ML</h4>
                    <ul class="config-list">
                        <li>Python 3.12</li>
                        <li>PyTorch (LSTM classifier)</li>
                        <li>XGBoost (magnitude regressor)</li>
                        <li>scikit-learn (evaluation)</li>
                    </ul>
                </div>
                <div>
                    <h4 style="color:var(--accent-green); margin-bottom:8px;">Data & API</h4>
                    <ul class="config-list">
                        <li>Open-Meteo GFS Ensemble API</li>
                        <li>USGS NWIS (streamflow)</li>
                        <li>NOAA Atlas 14 (IDF benchmarks)</li>
                        <li>SQLite (audit + forecast DB)</li>
                    </ul>
                </div>
                <div>
                    <h4 style="color:var(--accent-orange); margin-bottom:8px;">Infrastructure</h4>
                    <ul class="config-list">
                        <li>FastAPI + Uvicorn</li>
                        <li>Streamlit (EOC dashboard)</li>
                        <li>Docker + docker-compose</li>
                        <li>APScheduler (6hr refresh)</li>
                    </ul>
                </div>
            </div>
        </div>

        <div class="card purple">
            <h3>Training Data Summary</h3>
            <div class="grid-2">
                <div>
                    <h4 style="color:var(--accent-purple); margin-bottom:8px;">Base Basin: Babocomari River</h4>
                    <ul class="config-list">
                        <li><span class="config-key">USGS ID:</span> 09471000</li>
                        <li><span class="config-key">HUC:</span> 15050202</li>
                        <li><span class="config-key">Area:</span> 979 km&#178;</li>
                        <li><span class="config-key">Training:</span> 1990-01-01 to 2015-12-31</li>
                        <li><span class="config-key">Validation:</span> 2016-01-01 to 2019-12-31</li>
                        <li><span class="config-key">Test:</span> 2020-01-01 to 2024-12-31</li>
                    </ul>
                </div>
                <div>
                    <h4 style="color:var(--accent-orange); margin-bottom:8px;">Target Basin: Upper Sonoita Creek</h4>
                    <ul class="config-list">
                        <li><span class="config-key">USGS ID:</span> 09481500</li>
                        <li><span class="config-key">HUC:</span> 15050301</li>
                        <li><span class="config-key">Area:</span> 510 km&#178;</li>
                        <li><span class="config-key">Status:</span> <span style="color:var(--accent-green);">Transfer complete (NSE=0.657, F1=0.645)</span></li>
                    </ul>
                </div>
            </div>
        </div>
    </div>

    </div> <!-- /developer-pane -->

    <div class="footer">
        AFFI Project | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')} |
        Pipeline Version: {packet.get('pipeline_version', '2.0.0')} |
        University of Arizona — School of Information — Machine Learning
    </div>
</div>

<script>
    function switchTab(tabId, btn) {{
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
        document.getElementById('tab-' + tabId).classList.add('active');
        if (btn) btn.classList.add('active');
    }}
    function switchMode(mode, btn) {{
        document.querySelectorAll('.view-pane').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(mode + '-pane').classList.add('active');
        if (btn) btn.classList.add('active');
    }}
</script>
</body>
</html>"""


def main():
    html = generate_html()
    out_path = OUTPUTS / "dashboard.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Dashboard written to: {out_path}")
    print(f"Open in browser: file://{out_path}")


if __name__ == "__main__":
    main()
