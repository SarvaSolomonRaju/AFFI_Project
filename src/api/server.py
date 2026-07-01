from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key, require_role
from src.api.routes_map import router as map_router
from src.api.routes_action import router as action_router
from src.api.routes_bulletin import router as bulletin_router
from src.api.routes_historical import router as historical_router
from src.api.routes_cockpit import router as cockpit_router
from common.logging_setup import configure_logging, get_logger

configure_logging(level="INFO", to_file=True, log_dir=ROOT / "outputs" / "logs")
log = get_logger("affi.api")

OUTPUTS_DIR = ROOT / "outputs"
TASK1_DIR = OUTPUTS_DIR / "task1"
MODELS_DIR = ROOT / "models"

app = FastAPI(
    title="AFFI — Arizona Flash Flood Inundation AI",
    description=(
        "Government API for real-time probabilistic flood inundation forecasting. "
        "Provides alert packets, forecast data, flood maps, and EOC dashboard data "
        "for authorized emergency management personnel."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

_default_origins = "http://localhost:5173,http://localhost:3000"
_cors_origins = [
    o.strip() for o in os.environ.get("AFFI_CORS_ORIGINS", _default_origins).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(map_router)
app.include_router(action_router)
app.include_router(bulletin_router)
app.include_router(historical_router)
app.include_router(cockpit_router)


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    last_forecast_utc: Optional[str] = None
    watershed: str = "Upper Sonoita Creek"

_START_TIME = time.time()


class RunPipelineRequest(BaseModel):
    watershed_id: str = Field(default="upper_sonoita_creek", description="Watershed identifier")
    force_refresh: bool = Field(default=False, description="Force new GFS data fetch")


class RunPipelineResponse(BaseModel):
    run_id: int
    watershed: str
    current_alert: str
    max_7day_alert: str
    data_source: str
    generated_utc: str
    alert_packet_url: str
    dashboard_url: str


class AlertHistoryEntry(BaseModel):
    id: int
    run_time: str
    watershed_name: str
    current_alert: str
    max_alert_7day: Optional[str] = None
    p50_max_24hr: Optional[float] = None
    p90_max_24hr: Optional[float] = None
    storm_index_max: Optional[float] = None
    data_source: str


def _load_latest_alert_packet() -> Optional[dict]:
    paths = [
        TASK1_DIR / "task1_alert_packet.json",
        OUTPUTS_DIR / "task1_alert_packet.json",
    ]
    for p in paths:
        if p.exists():
            return json.loads(p.read_text())
    return None


def _get_db():
    from common.database import FloodDatabase
    db_path = str(OUTPUTS_DIR / "floodai.db")
    if not Path(db_path).exists():
        db_path = str(TASK1_DIR / "floodai.db")
    return FloodDatabase(db_path)


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    packet = _load_latest_alert_packet()
    last_utc = packet.get("generated_utc") if packet else None
    return HealthResponse(
        status="operational",
        version="1.0.0",
        uptime_seconds=round(time.time() - _START_TIME, 1),
        last_forecast_utc=last_utc,
    )


@app.get("/api/v1/alert/current", tags=["Alerts"])
async def get_current_alert(user: dict = Depends(validate_api_key)):
    packet = _load_latest_alert_packet()
    if packet is None:
        raise HTTPException(status_code=404, detail="No forecast data available. Run the pipeline first.")
    log.info("Alert query by %s — level=%s", user.get("owner"), packet.get("current_alert"))
    return {
        "current_alert": packet.get("current_alert", "GREEN"),
        "max_7day_alert": packet.get("max_7day_alert", "GREEN"),
        "generated_utc": packet.get("generated_utc"),
        "watershed": packet.get("watershed", {}),
        "data_source": packet.get("data_source", "unknown"),
    }


@app.get("/api/v1/alert/packet", tags=["Alerts"])
async def get_alert_packet(user: dict = Depends(validate_api_key)):
    packet = _load_latest_alert_packet()
    if packet is None:
        raise HTTPException(status_code=404, detail="No forecast data available.")
    log.info("Full packet query by %s", user.get("owner"))
    return packet


@app.get("/api/v1/alert/history", tags=["Alerts"])
async def get_alert_history(
    limit: int = Query(default=30, ge=1, le=365, description="Number of recent runs"),
    user: dict = Depends(validate_api_key),
):
    try:
        db = _get_db()
        rows = db.get_recent_runs(limit)
        db.close()
        return {"count": len(rows), "runs": rows}
    except Exception as e:
        log.error("History query failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/forecast/days", tags=["Forecast"])
async def get_forecast_days(user: dict = Depends(validate_api_key)):
    packet = _load_latest_alert_packet()
    if packet is None:
        raise HTTPException(status_code=404, detail="No forecast data available.")
    return {
        "generated_utc": packet.get("generated_utc"),
        "forecast_days": packet.get("forecast_days", []),
    }


@app.get("/api/v1/forecast/return_periods", tags=["Forecast"])
async def get_return_periods(user: dict = Depends(validate_api_key)):
    packet = _load_latest_alert_packet()
    if packet is None:
        raise HTTPException(status_code=404, detail="No forecast data available.")
    days = packet.get("forecast_days", [])
    return {
        "generated_utc": packet.get("generated_utc"),
        "idf_10yr_benchmarks_inches": packet.get("idf_10yr_benchmarks_inches", {}),
        "days": [
            {
                "date": d.get("date"),
                "alert_level": d.get("alert_level"),
                "storm_index_24hr": d.get("storm_index_24hr"),
                "return_period": d.get("return_period", {}),
            }
            for d in days
        ],
    }


@app.get("/api/v1/model/metrics", tags=["Model"])
async def get_model_metrics(user: dict = Depends(validate_api_key)):
    packet = _load_latest_alert_packet()
    metrics = packet.get("model_metrics", {}) if packet else {}
    cfg_path = MODELS_DIR / "best_inference_config.json"
    inference_cfg = {}
    if cfg_path.exists():
        inference_cfg = json.loads(cfg_path.read_text())
    return {"task1_metrics": metrics, "task2_inference_config": inference_cfg}


@app.post("/api/v1/pipeline/run", tags=["Pipeline"])
async def run_pipeline(
    req: RunPipelineRequest,
    user: dict = Depends(require_role("operator")),
):
    log.info("Pipeline trigger by %s for watershed=%s", user.get("owner"), req.watershed_id)
    try:
        from scripts.run_task1 import run_task1
        packet = run_task1()
        run_id = 0
        try:
            db = _get_db()
            run_id = db.save_forecast_run(packet, packet.get("data_source", "api"))
            db.close()
        except Exception as e:
            log.error("DB save failed after pipeline: %s", e)

        return RunPipelineResponse(
            run_id=run_id,
            watershed=packet.get("watershed", {}).get("name", req.watershed_id),
            current_alert=packet.get("current_alert", "GREEN"),
            max_7day_alert=packet.get("max_7day_alert", "GREEN"),
            data_source=packet.get("data_source", "unknown"),
            generated_utc=packet.get("generated_utc", ""),
            alert_packet_url="/api/v1/alert/packet",
            dashboard_url="/api/v1/dashboard/index",
        )
    except Exception as e:
        log.error("Pipeline execution failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {e}")


@app.get("/api/v1/dashboard/{filename}", tags=["Dashboard"])
async def get_dashboard_file(filename: str, user: dict = Depends(validate_api_key)):
    safe_names = {
        "index": "index.html",
        "precipitation": "dashboard_precipitation.html",
        "probabilities": "dashboard_probabilities.html",
        "return_periods": "dashboard_return_periods.html",
        "summary": "dashboard_summary.html",
        "forecast_dashboard": "task1_forecast_dashboard.png",
    }
    actual = safe_names.get(filename, filename)
    fpath = TASK1_DIR / actual
    if not fpath.exists():
        raise HTTPException(status_code=404, detail=f"Dashboard file not found: {actual}")
    media = "text/html" if actual.endswith(".html") else "image/png"
    return FileResponse(fpath, media_type=media)


@app.get("/api/v1/watershed/config", tags=["Watershed"])
async def get_watershed_config(user: dict = Depends(validate_api_key)):
    from config.settings import load_settings
    try:
        s = load_settings()
        return {
            "watershed": {
                "name": s.watershed.name,
                "huc": s.watershed.huc,
                "state": s.watershed.state,
                "county": s.watershed.county,
                "area_km2": s.watershed.area_km2,
                "pour_point": {
                    "lat": s.watershed.pour_point.lat,
                    "lon": s.watershed.pour_point.lon,
                    "description": s.watershed.pour_point.description,
                },
                "bbox": {
                    "north": s.watershed.bbox.north,
                    "south": s.watershed.bbox.south,
                    "east": s.watershed.bbox.east,
                    "west": s.watershed.bbox.west,
                },
                "usgs_gauge": s.watershed.usgs_gauge,
            },
            "idf_benchmarks": s.idf_benchmarks,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
