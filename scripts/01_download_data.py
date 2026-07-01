"""
01_download_data.py — Download + clean Babocomari River & Sonoita Creek datasets.

CHANGE LOG:
    2026-05-27: Replaced Walnut Gulch (USDA-ARS, synthetic fallback) with
                Babocomari River USGS-09471000 (real approved daily records).
                Both basins now use the identical USGS → Open-Meteo pipeline.
                Removed _ensure_ars_data() and all synthetic fallback code.

Run from project root:
    python scripts/01_download_data.py

Expected output:
    data/raw/usgs/09471000_discharge.parquet   ← Babocomari (train basin)
    data/raw/usgs/09481500_discharge.parquet   ← Sonoita   (finetune basin)
    data/raw/openmeteo/09471000_forcing.parquet
    data/raw/openmeteo/09481500_forcing.parquet
    data/interim/babocomari_river_daily.parquet
    data/interim/sonoita_creek_daily.parquet

First run: ~30s per basin (4 API calls).
Subsequent runs: <2s (cache hits).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `src` importable when running as `python scripts/01_download_data.py`
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.common import configure_logging, ensure_dirs, get_logger, load_config
from src.hydrology import BasinSpec, build_basin_dataset

logger = get_logger(__name__)


def main() -> int:
    configure_logging(level="INFO", to_file=True)
    ensure_dirs()

    cfg = load_config()
    logger.info("Date range: %s -> %s", cfg.data.start_date, cfg.data.end_date)

    # ── Basin specs ────────────────────────────────────────────────────────
    # Both basins use the exact same USGS + Open-Meteo pipeline.
    # BasinSpec is a dataclass — no magic dicts, fully typed, IDE-friendly.
    base = cfg.data.base_basin
    finetune = cfg.data.finetune_basin

    basins = [
        BasinSpec(
            name=base.name,
            usgs_id=base.usgs_id,
            lat=base.lat,
            lon=base.lon,
            area_km2=base.area_km2,
            huc=base.huc,
        ),
        BasinSpec(
            name=finetune.name,
            usgs_id=finetune.usgs_id,
            lat=finetune.lat,
            lon=finetune.lon,
            area_km2=finetune.area_km2,
            huc=finetune.huc,
        ),
    ]

    # ── Download each basin ────────────────────────────────────────────────
    exit_code = 0
    for basin in basins:
        logger.info("=" * 50)
        logger.info("Processing basin: %s (USGS %s)", basin.name, basin.usgs_id)
        logger.info("=" * 50)
        try:
            df = build_basin_dataset(
                basin=basin,
                start_date=cfg.data.start_date,
                end_date=cfg.data.end_date,
                force_refresh=False,
            )
            logger.info(
                "✓ %s ready: %d rows x %d cols", basin.name, *df.shape
            )
        except Exception as e:
            logger.error("✗ Failed to build %s: %s", basin.name, e, exc_info=True)
            exit_code = 1          # mark failure but continue other basins

    if exit_code == 0:
        logger.info("All datasets built successfully — no synthetic data used.")
    else:
        logger.error("One or more basins failed. Check logs above.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
