from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

OUTPUTS_DIR = ROOT / "outputs"
TASK1_DIR = OUTPUTS_DIR / "task1"
MODELS_DIR = ROOT / "models"
FIGURES_DIR = OUTPUTS_DIR / "figures"

ALERT_COLORS = {
    "GREEN": "#2ecc71",
    "ADVISORY": "#f1c40f",
    "WATCH": "#e67e22",
    "WARNING": "#e74c3c",
}

ALERT_ICONS = {
    "GREEN": "🟢",
    "ADVISORY": "🟡",
    "WATCH": "🟠",
    "WARNING": "🔴",
}


def load_alert_packet() -> dict | None:
    for p in [TASK1_DIR / "task1_alert_packet.json", OUTPUTS_DIR / "task1_alert_packet.json"]:
        if p.exists():
            return json.loads(p.read_text())
    return None


def load_task2_config() -> dict | None:
    cfg_path = MODELS_DIR / "best_inference_config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text())
    return None


st.set_page_config(
    page_title="AFFI — Flood Warning EOC Dashboard",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main {background-color: #0e1117;}
    .alert-box {padding: 1.5rem; border-radius: 12px; text-align: center; margin-bottom: 1rem;}
    .metric-card {background: #1a1a2e; padding: 1rem; border-radius: 8px; border: 1px solid #333;}
    </style>
    """,
    unsafe_allow_html=True,
)

packet = load_alert_packet()

st.sidebar.title("🌊 AFFI EOC Dashboard")
st.sidebar.markdown("**Arizona Flash Flood Inundation AI**")
st.sidebar.markdown("---")

if packet:
    ws = packet.get("watershed", {})
    st.sidebar.markdown(f"**Watershed:** {ws.get('name', 'N/A')}")
    st.sidebar.markdown(f"**HUC:** {ws.get('huc', 'N/A')}")
    st.sidebar.markdown(f"**Area:** {ws.get('area_km2', 'N/A')} km²")
    st.sidebar.markdown(f"**Gauge:** USGS {ws.get('usgs_gauge', 'N/A')}")
    st.sidebar.markdown(f"**Data Source:** {packet.get('data_source', 'N/A')}")
    st.sidebar.markdown(f"**Generated:** {packet.get('generated_utc', 'N/A')[:19]}")
else:
    st.sidebar.warning("No forecast data loaded")

st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("Auto-refresh (60s)", value=False)
if auto_refresh:
    st.rerun()

page = st.sidebar.radio(
    "Navigation",
    ["Alert Summary", "Precipitation Forecast", "Return Period Analysis", "Model Performance", "Alert History"],
)

if packet is None:
    st.error("No forecast data available. Run the pipeline first: `python main.py --task1-only`")
    st.stop()

current_alert = packet.get("current_alert", "GREEN")
max_7day = packet.get("max_7day_alert", "GREEN")
days = packet.get("forecast_days", [])
idf_10yr = packet.get("idf_10yr_benchmarks_inches", {})

if page == "Alert Summary":
    st.title("AFFI — Current Alert Status")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        color = ALERT_COLORS[current_alert]
        st.markdown(
            f'<div class="alert-box" style="background:{color}; color: black;">'
            f'<h2>{ALERT_ICONS[current_alert]} {current_alert}</h2>'
            f'<p>Current Alert Level</p></div>',
            unsafe_allow_html=True,
        )
    with col2:
        color = ALERT_COLORS[max_7day]
        st.markdown(
            f'<div class="alert-box" style="background:{color}; color: black;">'
            f'<h2>{ALERT_ICONS[max_7day]} {max_7day}</h2>'
            f'<p>7-Day Maximum</p></div>',
            unsafe_allow_html=True,
        )
    with col3:
        peak_p90 = max((d.get("p90_24hr", 0) for d in days), default=0)
        st.metric("Peak Forecast (P90)", f'{peak_p90:.2f}"', help="90th percentile 24hr accumulation")
    with col4:
        bench = idf_10yr.get("24hr", 3.1)
        st.metric("10-Year Benchmark", f'{bench:.1f}"', help="NOAA Atlas 14 10-year 24hr rainfall")

    st.markdown("---")
    st.subheader("7-Day Forecast Summary")

    if days:
        df = pd.DataFrame(days)
        display_cols = ["date", "alert_level", "p10_24hr", "p50_24hr", "p90_24hr", "storm_index_24hr"]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(
            df[available].style.applymap(
                lambda v: f"background-color: {ALERT_COLORS.get(v, 'transparent')}; color: black"
                if v in ALERT_COLORS else "",
                subset=["alert_level"] if "alert_level" in available else [],
            ),
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("---")
    st.subheader("Alert Timeline")
    if days:
        dates = [d.get("date", f"Day {i}") for i, d in enumerate(days)]
        alerts = [d.get("alert_level", "GREEN") for d in days]
        alert_vals = {"GREEN": 0, "ADVISORY": 1, "WATCH": 2, "WARNING": 3}
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=dates,
            y=[alert_vals[a] for a in alerts],
            marker_color=[ALERT_COLORS[a] for a in alerts],
            text=alerts,
            textposition="auto",
        ))
        fig.update_layout(
            yaxis=dict(
                tickvals=[0, 1, 2, 3],
                ticktext=["GREEN", "ADVISORY", "WATCH", "WARNING"],
            ),
            template="plotly_dark",
            height=300,
            margin=dict(l=50, r=20, t=30, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)


elif page == "Precipitation Forecast":
    st.title("Ensemble Precipitation Forecast")

    if days:
        dates = [d.get("date", "") for d in days]
        p10 = [d.get("p10_24hr", 0) for d in days]
        p50 = [d.get("p50_24hr", 0) for d in days]
        p90 = [d.get("p90_24hr", 0) for d in days]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=p90, mode="lines", name="P90 (worst case)",
            line=dict(color="#e74c3c", dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=p10, mode="lines", name="P10 (best case)",
            line=dict(color="#3498db", dash="dash"),
            fill="tonexty", fillcolor="rgba(52, 152, 219, 0.2)",
        ))
        fig.add_trace(go.Scatter(
            x=dates, y=p50, mode="lines+markers", name="P50 (median)",
            line=dict(color="#3498db", width=3),
        ))
        bench_24 = idf_10yr.get("24hr", 3.1)
        fig.add_hline(y=bench_24, line_dash="dot", line_color="#f39c12",
                       annotation_text=f"10-yr benchmark ({bench_24}\")")
        fig.update_layout(
            yaxis_title="24-hr Rainfall (inches)",
            template="plotly_dark",
            height=450,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Storm Severity Index")
        si = [d.get("storm_index_24hr", 0) for d in days]
        alerts = [d.get("alert_level", "GREEN") for d in days]
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=dates, y=si,
            marker_color=[ALERT_COLORS[a] for a in alerts],
            name="Storm Index",
        ))
        fig2.add_hline(y=1.0, line_dash="dash", line_color="#f39c12",
                        annotation_text="= 10-year storm")
        fig2.update_layout(
            yaxis_title="Storm Index (P50 / 10yr)",
            template="plotly_dark",
            height=350,
        )
        st.plotly_chart(fig2, use_container_width=True)


elif page == "Return Period Analysis":
    st.title("Return Period Classification")

    if days:
        for d in days:
            rp = d.get("return_period", {})
            if rp:
                with st.expander(f"{d.get('date', 'N/A')} — {d.get('alert_level', 'GREEN')}", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"**Classification:** {rp.get('classification', 'N/A')}")
                        st.markdown(f"**Storm Index:** {d.get('storm_index_24hr', 0):.3f}")
                    with col2:
                        st.markdown(f"**P50 24hr:** {d.get('p50_24hr', 0):.2f}\"")
                        st.markdown(f"**P90 24hr:** {d.get('p90_24hr', 0):.2f}\"")

    st.markdown("---")
    st.subheader("IDF Benchmark Table (NOAA Atlas 14 — Santa Cruz County)")
    idf_all = packet.get("idf_10yr_benchmarks_inches", {})
    if idf_all:
        st.json(packet.get("idf_10yr_benchmarks_inches", {}))


elif page == "Model Performance":
    st.title("Model Performance — Task 2 Hurdle Model")

    t2_cfg = load_task2_config()
    if t2_cfg:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Classifier Threshold", f"{t2_cfg.get('threshold', 'N/A'):.2f}")
        with col2:
            st.metric("P90 Flow (cms)", f"{t2_cfg.get('p90_threshold', 'N/A'):.3f}")
        with col3:
            nse_val = t2_cfg.get("nse", "N/A")
            st.metric("Test NSE", f"{nse_val:.3f}" if isinstance(nse_val, (int, float)) else str(nse_val))

    st.markdown("---")
    st.subheader("Evaluation Figures")
    fig_path = ROOT / "reports" / "figures" / "task2_evaluation.png"
    if fig_path.exists():
        st.image(str(fig_path), caption="Task 2 Evaluation — Hurdle Model")
    else:
        fig_files = sorted(FIGURES_DIR.glob("*.png")) if FIGURES_DIR.exists() else []
        if fig_files:
            for f in fig_files:
                st.image(str(f), caption=f.stem.replace("_", " ").title())
        else:
            st.info("No evaluation figures found. Run: `python scripts/04_evaluate.py`")

    metrics_from_packet = packet.get("model_metrics", {})
    if metrics_from_packet:
        st.subheader("Task 2 Metrics from Alert Packet")
        st.json(metrics_from_packet)


elif page == "Alert History":
    st.title("Alert History")

    db_paths = [OUTPUTS_DIR / "floodai.db", TASK1_DIR / "floodai.db"]
    db_path = None
    for p in db_paths:
        if p.exists():
            db_path = p
            break

    if db_path:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, run_time, watershed_name, current_alert, max_alert_7day, "
            "p50_max_24hr, p90_max_24hr, storm_index_max, data_source "
            "FROM forecast_runs ORDER BY id DESC LIMIT 100"
        ).fetchall()
        conn.close()

        if rows:
            df = pd.DataFrame([dict(r) for r in rows])
            st.dataframe(df, use_container_width=True, hide_index=True)

            alerts_count = df["current_alert"].value_counts()
            fig = go.Figure(data=[go.Pie(
                labels=alerts_count.index.tolist(),
                values=alerts_count.values.tolist(),
                marker_colors=[ALERT_COLORS.get(a, "#888") for a in alerts_count.index],
            )])
            fig.update_layout(template="plotly_dark", height=350, title="Alert Distribution")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No historical runs in database.")
    else:
        st.warning("Database not found. Run the pipeline first.")
