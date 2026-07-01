"""
task1_forecast.py — Task 1 Production Pipeline
=================================================
THIS IS THE ORCHESTRATOR.
    It doesn't DO the work — it COORDINATES the workers:

    1. grid.py          → "Where should we measure rainfall?"
    2. api_client.py    → "Go fetch the forecast data"
    3. validators.py    → "Check the data is clean"
    4. map_calculator.py → "Combine the points into one value"
    5. alert_engine.py  → "What alert level should we issue?"
    6. database.py      → "Save everything permanently"
    7. dashboard        → "Create the visualization"

    Think of it like a restaurant:
    - task1_forecast.py = the HEAD CHEF (coordinates)
    - grid.py = the PREP COOK (prepares ingredients)
    - api_client.py = the DELIVERY DRIVER (gets ingredients)
    - map_calculator.py = the LINE COOK (does the cooking)
    - alert_engine.py = the FOOD CRITIC (evaluates the result)
    - database.py = the ACCOUNTANT (records everything)

WHY SEPARATE FILES?
    Your original code was ONE 250-line file.
    Problems with that:
    1. Can't test individual pieces
    2. Can't reuse pieces (Task 2 also needs grid.py)
    3. Hard to find bugs (which of the 250 lines is wrong?)
    4. Hard to collaborate (two people can't edit one file)

    Separate files = each file has ONE job.
    If the alert logic is wrong, you KNOW it's in alert_engine.py.
    If the API fails, you KNOW it's in api_client.py.
    This is called "Separation of Concerns" — the #1 principle
    of professional software engineering.
"""

import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

_src_dir = _project_root / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from config.settings import Settings, load_settings
from src.forecast.grid import build_grid_points
from src.forecast.api_client import EnsembleForecastClient
from src.forecast.map_calculator import (
    compute_map,
    compute_rolling_accumulations,
    compute_daily_statistics
)
from src.forecast.alert_engine import AlertEngine, build_return_period_comparison
from src.common.logging_setup import get_logger
from src.common.database import FloodDatabase
from src.common.validators import validate_bbox, validate_idf_table

logger = get_logger(__name__)


# ============================================================
# ALERT COLORS — used in dashboard visualization
# ============================================================
ALERT_COLORS = {
    "GREEN": "#2ecc71",
    "ADVISORY": "#f1c40f",
    "WATCH": "#e67e22",
    "WARNING": "#e74c3c"
}


class Task1Pipeline:
    """
    Complete Task 1 pipeline: Fetch forecast → Classify → Alert → Save.

    HOW TO USE:
        # Option 1: Use default config
        pipeline = Task1Pipeline()
        result = pipeline.run()

        # Option 2: Use custom config
        settings = load_settings("config/watersheds/rillito_creek.yaml")
        pipeline = Task1Pipeline(settings)
        result = pipeline.run()
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the pipeline.

        WHAT HAPPENS:
        1. Load configuration (from YAML)
        2. Validate the config (catch errors early)
        3. Create the API client
        4. Create the alert engine
        5. Open the database
        """
        # Load settings
        if settings is None:
            self.settings = load_settings()
        else:
            self.settings = settings

        s = self.settings
        ws = s.watershed

        logger.info("=" * 60)
        logger.info("TASK 1 — Flood Forecast Pipeline")
        logger.info("=" * 60)
        logger.info("Watershed: %s (HUC: %s)", ws.name, ws.huc)
        logger.info("Area: %.0f km² | Gauge: USGS %s", ws.area_km2, ws.usgs_gauge)
        logger.info("Pour Point: %s", ws.pour_point.description)

        # Validate configuration
        bbox_dict = {
            "north": ws.bbox.north, "south": ws.bbox.south,
            "east": ws.bbox.east, "west": ws.bbox.west
        }
        if not validate_bbox(bbox_dict):
            raise ValueError("Invalid bounding box in configuration")

        if not validate_idf_table(s.idf_benchmarks):
            raise ValueError("Invalid IDF table in configuration")

        # Build grid points
        self.grid_points = build_grid_points(
            bbox_dict,
            center_weight=s.grid.center_weight,
            cardinal_weight=s.grid.cardinal_weight,
            diagonal_weight=s.grid.diagonal_weight
        )

        # Create API client
        self.api_client = EnsembleForecastClient(
            base_url=s.api.ensemble_url,
            model=s.api.model,
            forecast_days=s.api.forecast_days,
            timeout=s.api.timeout_seconds,
            max_retries=s.api.max_retries,
            retry_delay=s.api.retry_delay_seconds,
            timezone=s.api.timezone
        )

        # Create alert engine
        self.alert_engine = AlertEngine(
            idf_10yr=s.idf_10yr,
            alert_config=s.alert_thresholds
        )

        # Output directory
        self.output_dir = Path("outputs") / "task1"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        Path("outputs").mkdir(exist_ok=True)

        logger.info("Pipeline initialized successfully")

    def run(self, save_to_db: bool = True) -> Dict:
        """
        Execute the complete Task 1 pipeline.

        STEPS:
        1. Fetch ensemble forecasts for all grid points
        2. Compute Mean Areal Precipitation (MAP)
        3. Compute rolling accumulations
        4. Compute daily statistics
        5. Classify alerts
        6. Build alert packet
        7. Save to database
        8. Generate dashboard
        9. Return results

        Returns
        -------
        dict
            The complete alert packet (also saved as JSON)
        """
        logger.info("-" * 40)
        logger.info("STEP 1: Fetching ensemble forecasts")
        logger.info("-" * 40)

        all_point_data = {}
        data_sources = []

        for pt in self.grid_points:
            df, source = self.api_client.fetch(
                lat=pt["lat"], lon=pt["lon"], point_id=pt["id"]
            )
            all_point_data[pt["id"]] = df
            data_sources.append(source)

        # Determine overall data source
        if all(s == "api" for s in data_sources):
            overall_source = "api"
        elif all(s == "synthetic" for s in data_sources):
            overall_source = "synthetic"
        else:
            overall_source = "mixed"

        logger.info("Data source: %s", overall_source)

        # ---- STEP 2: Compute MAP ----
        logger.info("-" * 40)
        logger.info("STEP 2: Computing Mean Areal Precipitation")
        logger.info("-" * 40)

        map_matrix = compute_map(all_point_data, self.grid_points)

        # ---- STEP 3: Rolling accumulations ----
        logger.info("-" * 40)
        logger.info("STEP 3: Computing rolling accumulations")
        logger.info("-" * 40)

        accumulations = compute_rolling_accumulations(map_matrix)

        # ---- STEP 4: Daily statistics ----
        logger.info("-" * 40)
        logger.info("STEP 4: Computing daily statistics")
        logger.info("-" * 40)

        daily_stats = compute_daily_statistics(
            map_matrix, accumulations, 
            n_days=self.settings.api.forecast_days
        )

        # ---- STEP 5: Alert classification ----
        logger.info("-" * 40)
        logger.info("STEP 5: Classifying alerts")
        logger.info("-" * 40)

        classified_days = self.alert_engine.classify_all_days(
            daily_stats, accumulations, map_matrix
        )

        # ---- STEP 6: Return period comparison ----
        logger.info("-" * 40)
        logger.info("STEP 6: Return period benchmarking")
        logger.info("-" * 40)

        for day in classified_days:
            rp = build_return_period_comparison(
                day, self.settings.idf_benchmarks
            )
            day["return_period"] = rp

        # ---- STEP 7: Build alert packet ----
        logger.info("-" * 40)
        logger.info("STEP 7: Building alert packet")
        logger.info("-" * 40)

        ws = self.settings.watershed
        alert_packet = {
            "generated_utc": datetime.utcnow().isoformat(),
            "pipeline_version": "2.0.0",
            "data_source": overall_source,
            "watershed": {
                "name": ws.name,
                "huc": ws.huc,
                "state": ws.state,
                "county": ws.county,
                "pour_point": {
                    "lat": ws.pour_point.lat,
                    "lon": ws.pour_point.lon,
                    "desc": ws.pour_point.description
                },
                "bbox": {
                    "north": ws.bbox.north,
                    "south": ws.bbox.south,
                    "east": ws.bbox.east,
                    "west": ws.bbox.west
                },
                "area_km2": ws.area_km2,
                "usgs_gauge": ws.usgs_gauge
            },
            "idf_10yr_benchmarks_inches": self.settings.idf_10yr,
            "current_alert": classified_days[0]["alert_level"] if classified_days else "GREEN",
            "max_7day_alert": max(
                (d["alert_level"] for d in classified_days),
                key=lambda x: {"GREEN": 0, "ADVISORY": 1, "WATCH": 2, "WARNING": 3}[x],
                default="GREEN"
            ),
            "api_stats": self.api_client.get_stats(),
             "forecast_days": classified_days,
             "model_metrics": self._load_task2_metrics()
        }

        # Save JSON
        json_path = self.output_dir / "task1_alert_packet.json"
        with open(json_path, "w") as f:
            json.dump(alert_packet, f, indent=2, default=str)
        logger.info("Saved: %s", json_path)

        root_json = Path("outputs") / "task1_alert_packet.json"
        with open(root_json, "w") as f:
            json.dump(alert_packet, f, indent=2, default=str)
        logger.info("Saved (compat copy): %s", root_json)

        # ---- STEP 8: Save to database ----
        if save_to_db:
            logger.info("-" * 40)
            logger.info("STEP 8: Saving to database")
            logger.info("-" * 40)

            try:
                with FloodDatabase() as db:
                    run_id = db.save_forecast_run(alert_packet, overall_source)
                    logger.info("Saved as run #%d", run_id)
            except Exception as e:
                logger.error("Database save failed: %s", e)

        # ---- STEP 9: Generate dashboard ----
        logger.info("-" * 40)
        logger.info("STEP 9: Generating dashboard")
        logger.info("-" * 40)

        self._generate_dashboard(classified_days)

        # ---- STEP 10: Rebuild unified HTML dashboard ----
        logger.info("-" * 40)
        logger.info("STEP 10: Rebuilding unified HTML dashboard")
        logger.info("-" * 40)

        self._rebuild_unified_dashboard()

        # ---- SUMMARY ----
        logger.info("=" * 60)
        logger.info("TASK 1 COMPLETE")
        logger.info("  Current alert: %s", alert_packet["current_alert"])
        logger.info("  Max 7-day alert: %s", alert_packet["max_7day_alert"])
        logger.info("  Data source: %s", overall_source)
        logger.info("  API success rate: %s%%",
                    self.api_client.get_stats()["success_rate_pct"])
        logger.info("=" * 60)

        return alert_packet

    def _generate_dashboard(self, classified_days):
        """
        Generate the 4-panel forecast dashboard.

        Panel 1 (top-left):  24-hr rainfall forecast with P10/P50/P90 bands
        Panel 2 (top-right): Storm Index comparison to 10-year storm
        Panel 3 (bot-left):  Probability of exceedance by alert level
        Panel 4 (bot-right): 7-day alert status calendar
        """
        ws = self.settings.watershed
        idf_10yr = self.settings.idf_10yr

        fig, axes = plt.subplots(2, 2, figsize=(16, 11))
        fig.patch.set_facecolor("#1a1a2e")

        for ax in axes.flat:
            ax.set_facecolor("#16213e")
            ax.tick_params(colors="white")
            ax.xaxis.label.set_color("white")
            ax.yaxis.label.set_color("white")
            ax.title.set_color("white")
            for spine in ax.spines.values():
                spine.set_edgecolor("#444")

        dates = [d["date"] for d in classified_days]
        p10 = [d["p10_24hr"] for d in classified_days]
        p50 = [d["p50_24hr"] for d in classified_days]
        p90 = [d["p90_24hr"] for d in classified_days]
        si = [d["storm_index_24hr"] for d in classified_days]
        alerts = [d["alert_level"] for d in classified_days]
        x = np.arange(len(dates))

        # ---- Panel 1: P10/P50/P90 bands ----
        ax = axes[0, 0]
        ax.fill_between(x, p10, p90, alpha=0.3, color="#3498db", label="P10–P90 band")
        ax.plot(x, p50, "o-", color="#3498db", lw=2, ms=6, label="P50 (median)")
        ax.plot(x, p90, "--", color="#e74c3c", lw=1.5, alpha=0.8, label="P90")
        ax.axhline(idf_10yr["24hr"], color="#f39c12", lw=2, ls="--",
                   label=f"10-yr 24hr ({idf_10yr['24hr']}\")")
        ax.set_xticks(x)
        ax.set_xticklabels([d[5:] for d in dates], rotation=30, color="white", fontsize=8)
        ax.set_ylabel("Rainfall (inches)", color="white")
        ax.set_title("24-hr Rainfall Forecast (P10/P50/P90)", color="white", fontweight="bold")
        ax.legend(fontsize=8, facecolor="#1a1a2e", labelcolor="white")
        ax.grid(alpha=0.2, color="white")

        # ---- Panel 2: Storm Index ----
        ax = axes[0, 1]
        bar_colors = [ALERT_COLORS[a] for a in alerts]
        bars = ax.bar(x, si, color=bar_colors, edgecolor="white", linewidth=0.5)
        ax.axhline(1.0, color="#f39c12", lw=2, ls="--", label="= 10-year storm")
        ax.axhline(0.5, color="#2ecc71", lw=1, ls=":", alpha=0.7, label="= 5-year storm")
        ax.set_xticks(x)
        ax.set_xticklabels([d[5:] for d in dates], rotation=30, color="white", fontsize=8)
        ax.set_ylabel("Storm Index (P50 / 10-yr 24hr)", color="white")
        ax.set_title("10-Year Storm Comparison Index", color="white", fontweight="bold")
        ax.legend(fontsize=8, facecolor="#1a1a2e", labelcolor="white")
        ax.grid(alpha=0.2, color="white", axis="y")
        for bar, val in zip(bars, si):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                    f"{val:.2f}", ha="center", va="bottom", color="white", fontsize=8)

        # ---- Panel 3: Probability of Exceedance ----
        ax = axes[1, 0]
        poe_adv = [d.get("poe_advisory_24hr", 0) for d in classified_days]
        poe_wat = [d.get("poe_watch_24hr", 0) for d in classified_days]
        poe_warn = [d.get("poe_warning_24hr", 0) for d in classified_days]

        adv_thr = round(self.settings.alert_thresholds.advisory.fraction_of_10yr_24hr * idf_10yr["24hr"], 2)
        wat_thr = round(self.settings.alert_thresholds.watch.fraction_of_10yr_24hr * idf_10yr["24hr"], 2)
        warn_thr = round(self.settings.alert_thresholds.warning.fraction_of_10yr_24hr * idf_10yr["24hr"], 2)

        ax.plot(x, poe_adv, "s-", color="#f1c40f", lw=2, ms=6, label=f"Advisory (>{adv_thr}\")")
        ax.plot(x, poe_wat, "D-", color="#e67e22", lw=2, ms=6, label=f"Watch (>{wat_thr}\")")
        ax.plot(x, poe_warn, "o-", color="#e74c3c", lw=2, ms=6, label=f"Warning (>{warn_thr}\")")
        ax.axhline(30, color="white", lw=1, ls="--", alpha=0.5, label="30% trigger line")
        ax.set_xticks(x)
        ax.set_xticklabels([d[5:] for d in dates], rotation=30, color="white", fontsize=8)
        ax.set_ylabel("Probability (%)", color="white")
        ax.set_ylim(0, 105)
        ax.set_title("Probability of Exceedance by Alert Level", color="white", fontweight="bold")
        ax.legend(fontsize=8, facecolor="#1a1a2e", labelcolor="white")
        ax.grid(alpha=0.2, color="white")

        # ---- Panel 4: Alert Calendar ----
        ax = axes[1, 1]
        ax.set_xlim(-0.5, len(dates) - 0.5)
        ax.set_ylim(-0.5, 1.5)
        for i, (date, alert) in enumerate(zip(dates, alerts)):
            color = ALERT_COLORS[alert]
            rect = mpatches.FancyBboxPatch(
                (i - 0.4, 0.1), 0.8, 0.8,
                boxstyle="round,pad=0.05",
                facecolor=color, edgecolor="white", linewidth=1.5
            )
            ax.add_patch(rect)
            ax.text(i, 0.5, alert, ha="center", va="center",
                    color="white" if alert != "ADVISORY" else "black",
                    fontsize=8, fontweight="bold")
            ax.text(i, -0.1, date[5:], ha="center", va="top", 
                    color="white", fontsize=8)
        # Add Task 2 model metrics as text
        model_metrics = self._load_task2_metrics()
        metrics_text = (
            "Task 2 LSTM Model:\n"
            f"NSE: {model_metrics['nse']:.3f}\n"
            f"F1: {model_metrics['f1']:.3f}\n"
            f"AUC-ROC: {model_metrics['auc_roc']:.3f}\n"
            f"AUC-PR: {model_metrics['auc_pr']:.3f}"
         )
        ax.text(
              -0.3, 0.5, metrics_text, ha="left", va="center",
            color="white", fontsize=7,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#2c3e50", edgecolor="white", linewidth=1)
          )

        ax.set_title("7-Day Alert Status Calendar", color="white", fontweight="bold")
        ax.axis("off")
        legend_patches = [mpatches.Patch(color=v, label=k) for k, v in ALERT_COLORS.items()]
        ax.legend(handles=legend_patches, loc="upper right", fontsize=8,
                  facecolor="#1a1a2e", labelcolor="white")

        # ---- Title ----
        fig.suptitle(
            f"TASK 1 — {ws.name} Flood Forecast Dashboard\n"
            f"HUC: {ws.huc} | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"10-yr 24hr benchmark: {idf_10yr['24hr']}\"",
            color="white", fontsize=13, fontweight="bold", y=0.98
        )

        plt.tight_layout(rect=[0, 0, 1, 0.96])

        png_path = self.output_dir / "task1_forecast_dashboard.png"
        plt.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
        plt.close(fig)

        logger.info("Saved: %s", png_path)

        import shutil
        root_png = Path("outputs") / "task1_forecast_dashboard.png"
        shutil.copy2(png_path, root_png)
        logger.info("Saved (compat copy): %s", root_png)


    def _load_task2_metrics(self) -> Dict:
        """Load Task 2 model performance metrics if available."""
        models_dir = Path("models")
        config_path = models_dir / "best_inference_config.json"

        if config_path.exists():
            try:
                with open(config_path) as f:
                    config = json.load(f)
                return {
                     "nse": config.get("test_nse", 0.0),
                     "f1": config.get("f1_score", 0.0),
                     "auc_roc": config.get("auc_roc", 0.0),
                     "auc_pr": config.get("auc_pr", 0.0),
                 }
            except Exception:
                pass

        return {"nse": 0.0, "f1": 0.0, "auc_roc": 0.0, "auc_pr": 0.0}

    def _rebuild_unified_dashboard(self) -> None:
        """Rebuild the unified HTML dashboard with latest task1 and task2 results."""
        try:
            from scripts.build_dashboard import generate_html
            html = generate_html()
            dashboard_path = Path("outputs") / "dashboard.html"
            dashboard_path.write_text(html, encoding="utf-8")
            logger.info("✓ Unified dashboard updated: %s", dashboard_path)
        except Exception as e:
            logger.error("✗ Dashboard rebuild failed: %s", e)
            import traceback
            logger.error(traceback.format_exc())


# ── Module-level convenience function for main.py entrypoint ──
def run_task1(save_to_db: bool = True) -> Dict:
    """Run the complete Task 1 pipeline and return the alert packet."""
    pipeline = Task1Pipeline()
    return pipeline.run(save_to_db=save_to_db)
