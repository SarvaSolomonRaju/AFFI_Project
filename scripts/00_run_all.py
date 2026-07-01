#!/usr/bin/env python3
"""
scripts/00_run_all.py - end-to-end orchestrator for FloodAI

Runs the full real-data pipeline in order:
    1. FEMA NFHL flood-zone polygons              (scripts/09)
    2. USGS NWIS peaks + Bulletin 17C LP-III       (scripts/10)
    3. USGS 3DEP 10-m DEM                          (scripts/11)
    4. FEMA FIS profiles (BFE, XS, WaterLn)        (scripts/12)
    5. Build 8-map real flood library              (scripts/13)
    6. Task 4 probabilistic forecast (real library) (scripts/07)
    7. Task 5 benchmarking + validation             (scripts/08)
    8. Interactive Leaflet/Folium map               (src.dashboard.interactive_map)
    9. Full HTML dashboard                           (scripts/build_dashboard)

Usage:
    python scripts/00_run_all.py              # full pipeline
    python scripts/00_run_all.py --skip-data  # skip data downloads (steps 1-5)
    python scripts/00_run_all.py --only map   # only rebuild map + dashboard
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

STEPS = [
    ("data", "FEMA NFHL flood zones",       [sys.executable, "scripts/09_acquire_fema_nfhl.py"]),
    ("data", "USGS NWIS + LP-III",          [sys.executable, "scripts/10_acquire_usgs_streamstats.py"]),
    ("data", "USGS 3DEP 10-m DEM",          [sys.executable, "scripts/11_acquire_3dep_dem.py"]),
    ("data", "FEMA FIS profiles (BFE/XS)",  [sys.executable, "scripts/12_acquire_fis_profiles.py"]),
    ("data", "Build real flood library",    [sys.executable, "scripts/13_build_real_flood_library.py"]),
    ("data", "Local assets (OSM roads/bldgs)", [sys.executable, "scripts/14_build_local_assets.py"]),
    ("data", "Critical infrastructure GeoJSON", [sys.executable, "scripts/15_build_infrastructure.py"]),
    ("forecast", "Task 4 probabilistic",    [sys.executable, "scripts/07_task4_probabilistic.py", "--library", "real"]),
    ("forecast", "Task 5 benchmarking",     [sys.executable, "scripts/08_task5_benchmarking.py", "--library", "real"]),
    ("map", "Interactive Leaflet map",      [sys.executable, "-m", "src.dashboard.interactive_map"]),
    ("map", "HTML dashboard",               [sys.executable, "scripts/build_dashboard.py"]),
]


def run(step_name, cmd):
    print(f"\n{'=' * 78}\n  >> {step_name}\n  $ {' '.join(cmd)}\n{'=' * 78}")
    t0 = time.time()
    rc = subprocess.call(cmd, cwd=ROOT)
    dt = time.time() - t0
    if rc != 0:
        print(f"  [FAIL] {step_name} exited {rc} after {dt:.1f}s")
        return False
    print(f"  [OK]   {step_name} done in {dt:.1f}s")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-data", action="store_true",
                    help="Skip data acquisition steps (1-5); use cached data.")
    ap.add_argument("--only", choices=["data", "forecast", "map"], default=None,
                    help="Run only this phase.")
    args = ap.parse_args()

    selected = []
    for phase, name, cmd in STEPS:
        if args.only is not None and phase != args.only:
            continue
        if args.skip_data and phase == "data":
            continue
        selected.append((phase, name, cmd))

    print(f"FloodAI pipeline: {len(selected)} step(s) to run")
    failures = []
    for phase, name, cmd in selected:
        if not run(f"[{phase}] {name}", cmd):
            failures.append(name)

    print("\n" + "=" * 78)
    if failures:
        print(f"COMPLETED WITH FAILURES: {failures}")
        return 1
    print("ALL STEPS COMPLETED SUCCESSFULLY")
    print(f"Open: file://{ROOT}/outputs/dashboard.html")
    print(f"Map : file://{ROOT}/outputs/dashboard_map.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
