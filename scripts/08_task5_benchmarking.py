"""Task 5 - Benchmarking & Validation runner.

Loads the flood library + alert packet + historical event catalog,
runs pipeline validation, replays each historical event, builds the
return-period reference table, and writes a consolidated benchmark
report for the Developer dashboard.
"""
from __future__ import annotations
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import argparse
from src.probabilistic import FloodMapLibrary, rainfall_to_discharge
from src.probabilistic.flood_library import load_real_library
from src.benchmarking import (
    nws_atlas14_sonoita,
    discharge_to_return_period,
    load_events,
    replay_event,
    pipeline_validation,
    score_report,
)
from src.benchmarking.return_periods import return_period_table


LIBRARY_PATH = ROOT / "outputs/task3/spatial_predictions.npz"
ALERT_PATH = ROOT / "outputs/task1_alert_packet.json"
EVENTS_PATH = ROOT / "data/historical_events/sonoita_events.json"
OUT_DIR = ROOT / "outputs/task5"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 70)
    print("Task 5: Benchmarking & Validation")
    print("=" * 70)

    ap = argparse.ArgumentParser()
    ap.add_argument('--library', choices=['real','synthetic'], default='real')
    args, _ = ap.parse_known_args()
    if args.library == 'real':
        library = load_real_library(ROOT/'data/flood_library_real')
    else:
        library = FloodMapLibrary.load(LIBRARY_PATH)
    alert = json.loads(ALERT_PATH.read_text())
    events = load_events(EVENTS_PATH)
    print(f"[1/4] Loaded library ({library.n_maps} maps), "
          f"alert packet ({len(alert['forecast_days'])} days), "
          f"events ({len(events)})")

    # -- Pipeline validation --
    val = pipeline_validation(library, alert)
    print(f"[2/4] Pipeline validation: {val['n_passed']}/{val['n_checks']} passed")
    for c in val["checks"]:
        flag = "PASS" if c["passed"] else "FAIL"
        print(f"      [{flag}] {c['name']}: {c['detail']}")

    # -- Historical event replays --
    replays = [replay_event(ev, library, ensemble_fn=rainfall_to_discharge)
               for ev in events]
    print(f"[3/4] Replayed {len(replays)} historical events")
    for r in replays:
        msg = (f"      {r['name']}: Q={r['q_used_cms']:.1f} cms -> "
               f"predicted_median_d={r.get("predicted_median_wet_depth_m", r["predicted_max_depth_m"]):.2f} m (max={r["predicted_max_depth_m"]:.2f})")
        if r.get("observed_peak_stage_m") is not None:
            msg += f" (observed stage={r['observed_peak_stage_m']:.2f} m, "
            msg += f"residual={r['depth_residual_m']:+.2f} m)"
        print(msg)

    # -- Return-period table --
    rp_table = return_period_table()
    csv_path = OUT_DIR / "return_period_table.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rp_table[0].keys()))
        w.writeheader(); w.writerows(rp_table)

    # Per-day forecast -> Q -> return period
    forecast_rp = []
    for d in alert["forecast_days"]:
        q50 = rainfall_to_discharge(d["p50_24hr"])
        q90 = rainfall_to_discharge(d["p90_24hr"])
        forecast_rp.append({
            "day": d["day"], "date": d["date"],
            "rainfall_p50_in": d["p50_24hr"],
            "rainfall_p90_in": d["p90_24hr"],
            "q50_cms": q50, "q90_cms": q90,
            "rp_q50": discharge_to_return_period(q50),
            "rp_q90": discharge_to_return_period(q90),
        })

    # -- Compose report --
    report = score_report(val, replays, rp_table)
    report["atlas14_24hr_in"] = nws_atlas14_sonoita()
    report["forecast_return_periods"] = forecast_rp
    report["generated_utc"] = alert["generated_utc"]
    report["watershed"] = alert["watershed"]["name"]

    (OUT_DIR / "benchmark_report.json").write_text(json.dumps(report, indent=2))
    print(f"[4/4] Saved benchmark_report.json + return_period_table.csv to "
          f"{OUT_DIR.relative_to(ROOT)}/")
    if report["scores"]["depth_mae_m"] is not None:
        print(f"      Historical-event MAE: {report['scores']['depth_mae_m']:.3f} m "
              f"(bias {report['scores']['depth_bias_m']:+.3f} m)")
    print("DONE.")


if __name__ == "__main__":
    main()
