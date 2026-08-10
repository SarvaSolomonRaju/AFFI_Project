from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
_src = ROOT / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from scripts.run_task1 import run_task1 as _run_task1
from src.common.logging_setup import configure_logging, get_logger

log = get_logger(__name__)


def run_task1() -> dict:
    return _run_task1()


def run_script(path: Path) -> None:
    runpy.run_path(str(path), run_name="__main__")


def rebuild_dashboard() -> None:
    log.info("Rebuilding dashboard with fresh results")
    try:
        from scripts.build_dashboard import generate_html
        html = generate_html()
        out = ROOT / "outputs" / "dashboard.html"
        out.write_text(html, encoding="utf-8")
        log.info("Dashboard written to: %s", out)
    except Exception as e:
        log.error("Dashboard rebuild failed: %s", e)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task1-only", action="store_true")
    parser.add_argument("--skip-task2-download", action="store_true")
    parser.add_argument("--skip-task2-baselines", action="store_true")
    parser.add_argument("--skip-task2-train", action="store_true")
    parser.add_argument("--skip-task2-eval", action="store_true")
    args = parser.parse_args()

    configure_logging(level="INFO", to_file=True)

    log.info("Starting unified pipeline")
    run_task1()
    log.info("Task 1 complete")

    if args.task1_only:
        log.info("Task 2 skipped by --task1-only")
        rebuild_dashboard()
        return 0

    if not args.skip_task2_download:
        run_script(ROOT / "scripts" / "01_download_data.py")

    if not args.skip_task2_baselines:
        run_script(ROOT / "scripts" / "02_run_baselines.py")

    if not args.skip_task2_train:
        run_script(ROOT / "scripts" / "03_train_hurdle.py")

    if not args.skip_task2_eval:
        run_script(ROOT / "scripts" / "04_evaluate.py")

    if not args.skip_task2_train:
        log.info("Running Sonoita Creek transfer model")
        run_script(ROOT / "scripts" / "05_transfer_sonoita.py")

    rebuild_dashboard()

    log.info("Unified pipeline complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())