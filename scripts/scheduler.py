from __future__ import annotations

import subprocess
import sys
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.common.logging_setup import configure_logging, get_logger

configure_logging(level="INFO", to_file=True, log_dir=ROOT / "outputs" / "logs")
log = get_logger("affi.scheduler")

_running = True


def run_forecast_pipeline():
    log.info("Scheduled pipeline execution starting")
    try:
        from scripts.run_task1 import run_task1
        packet = run_task1()
        alert = packet.get("current_alert", "GREEN")
        log.info("Scheduled run complete — alert=%s at %s", alert, datetime.now(timezone.utc).isoformat())

        try:
            from src.common.database import FloodDatabase
            db = FloodDatabase(str(ROOT / "outputs" / "floodai.db"))
            run_id = db.save_forecast_run(packet, packet.get("data_source", "api"))
            db.close()
            log.info("Saved to DB as run #%d", run_id)
        except Exception as e:
            log.error("DB save failed: %s", e)

        # Task 1 only refreshes task1_alert_packet.json. The dashboard's
        # 7-day outlook and probabilistic maps read outputs/task4/forecast_7day.json,
        # a SEPARATE file that Task 1 never touches — without this, that file
        # (and everything the frontend derives from it) goes stale forever even
        # while this scheduler is "running". Same "forecast" pair as `make forecast`.
        try:
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "07_task4_probabilistic.py"), "--library", "real"],
                cwd=str(ROOT), capture_output=True, text=True, timeout=600,
            )
            if result.returncode != 0:
                log.error("Task 4 refresh failed (rc=%d): %s", result.returncode, result.stderr[-2000:])
            else:
                log.info("Task 4 (7-day probabilistic forecast) refreshed")
        except Exception as e:
            log.error("Task 4 refresh raised: %s", e)

    except Exception as e:
        log.error("Scheduled pipeline failed: %s", e)


def main():
    global _running
    log.info("AFFI Forecast Scheduler starting")
    log.info("Schedule: every 6 hours (00:00, 06:00, 12:00, 18:00 UTC)")

    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_forecast_pipeline,
        trigger=CronTrigger(hour="0,6,12,18", minute=15),
        id="forecast_pipeline",
        name="AFFI Forecast Pipeline",
        misfire_grace_time=3600,
    )
    scheduler.start()

    log.info("Scheduler active. Press Ctrl+C to stop.")
    log.info("Running initial forecast now...")
    run_forecast_pipeline()

    def _shutdown(signum, frame):
        global _running
        log.info("Shutdown signal received")
        _running = False

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while _running:
        time.sleep(1)

    scheduler.shutdown(wait=True)
    log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
