"""Prediction vs. reality endpoint — surfaces the forecast track record and
self-correction signal (src/verification/forecast_verification.py)."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, Depends

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.api.auth import validate_api_key

router = APIRouter(prefix="/api/v1", tags=["Verification"])

DB_PATH = ROOT / "outputs" / "floodai.db"


@router.get("/forecast-verification")
async def get_forecast_verification(limit: int = 30, user: dict = Depends(validate_api_key)):
    from src.common.database import FloodDatabase
    from src.verification.forecast_verification import build_verification

    runs: list[dict] = []
    if DB_PATH.exists():
        db = FloodDatabase(str(DB_PATH))
        try:
            runs = db.get_recent_runs(n=limit)
        finally:
            db.close()

    return build_verification(runs)
