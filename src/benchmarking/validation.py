"""Pipeline-level validation checks (sanity + physical-bounds)."""
from __future__ import annotations
from typing import Callable, List


def pipeline_validation(library, alert_packet: dict,
                        max_reasonable_q_cms: float = 1000.0,
                        max_reasonable_depth_m: float = 15.0) -> dict:
    """Run a battery of consistency checks across the end-to-end pipeline."""
    checks: List[dict] = []

    # Library checks
    n = library.n_maps
    checks.append({
        "name": "library_has_maps",
        "passed": bool(n >= 5),
        "detail": f"{n} maps available",
    })
    checks.append({
        "name": "library_q_monotonic",
        "passed": bool(all(library.discharges_cms[i] <= library.discharges_cms[i + 1]
                           for i in range(n - 1))),
        "detail": "discharges_cms sorted ascending",
    })
    # Depth non-negative everywhere
    nonneg = bool((library.depth_maps >= 0).all())
    checks.append({
        "name": "depth_nonnegative",
        "passed": nonneg,
        "detail": "all depth pixels >= 0",
    })
    # Depth within physical bounds
    max_d = float(library.depth_maps.max())
    checks.append({
        "name": "depth_within_physical_bounds",
        "passed": bool(max_d <= max_reasonable_depth_m),
        "detail": f"max depth in library = {max_d:.3f} m",
    })

    # Alert packet checks
    days = alert_packet.get("forecast_days", [])
    checks.append({
        "name": "alert_packet_has_forecast_days",
        "passed": bool(len(days) >= 1),
        "detail": f"{len(days)} forecast day(s)",
    })
    pct_ok = all(
        d.get("p10_24hr", 0) <= d.get("p50_24hr", 0) <= d.get("p90_24hr", 0)
        for d in days
    )
    checks.append({
        "name": "rainfall_percentiles_ordered",
        "passed": bool(pct_ok),
        "detail": "P10 <= P50 <= P90 on all days",
    })

    # Library covers typical forecast range
    max_p90 = max((d.get("p90_24hr", 0.0) for d in days), default=0.0)
    checks.append({
        "name": "library_covers_typical_forecast",
        "passed": bool(library.q_max_cms >= 5.0),
        "detail": f"q_max = {library.q_max_cms:.1f} cms, max forecast P90 rain = {max_p90:.2f}\"",
    })

    n_pass = sum(1 for c in checks if c["passed"])
    return {
        "n_checks": len(checks),
        "n_passed": n_pass,
        "n_failed": len(checks) - n_pass,
        "all_passed": n_pass == len(checks),
        "checks": checks,
    }


def score_report(validation: dict, event_replays: list,
                 return_table: list) -> dict:
    """Compose final benchmark report."""
    if event_replays:
        residuals = [e["depth_residual_m"] for e in event_replays
                     if e.get("depth_residual_m") is not None]
        if residuals:
            mae = sum(abs(r) for r in residuals) / len(residuals)
            bias = sum(residuals) / len(residuals)
        else:
            mae = None
            bias = None
    else:
        mae = None
        bias = None

    return {
        "validation": validation,
        "historical_events": event_replays,
        "return_period_table": return_table,
        "scores": {
            "depth_mae_m": mae,
            "depth_bias_m": bias,
            "n_events_replayed": len(event_replays),
        },
    }


def classification_accuracy(events: list, discharge_to_return_period_fn: Callable,
                            tolerance_factor: float = 2.0) -> dict:
    """
    Task 5 D5.5 — return-period classification accuracy vs. the historical
    event catalog's own approx_return_period_yr labels (whitepaper-cited
    engineering estimates from USGS gauge records / NWS event summaries,
    not new ground truth).

    "Correct" means the system's discharge-derived return-period estimate
    lands within `tolerance_factor` of the catalog's labeled return period
    (e.g. factor 2.0 = within half to double) -- return periods are
    inherently statistical estimates, not exact values, so exact-match
    would be the wrong bar. This is a scalar/discharge-based accuracy
    check, not the spatial (IoU) validation against post-event survey
    polygons that Task 5 D5.2 still lacks -- no such polygon ground truth
    exists in this project's data yet, and this function does not claim
    to close that gap.
    """
    rows = []
    for ev in events:
        q = ev.get("peak_q_cms")
        labeled_rp = ev.get("approx_return_period_yr")
        if q is None or labeled_rp is None:
            continue
        est = discharge_to_return_period_fn(q)
        predicted_rp = est["rp_yr_estimate"]
        ratio = predicted_rp / labeled_rp if labeled_rp > 0 else float("inf")
        correct = (1.0 / tolerance_factor) <= ratio <= tolerance_factor
        rows.append({
            "name": ev.get("name"),
            "date": ev.get("date"),
            "q_cms": q,
            "labeled_rp_yr": labeled_rp,
            "predicted_rp_yr": round(predicted_rp, 1),
            "ratio_predicted_over_labeled": round(ratio, 2),
            "correct_within_2x": bool(correct),
        })
    n_correct = sum(1 for r in rows if r["correct_within_2x"])
    return {
        "tolerance_factor": tolerance_factor,
        "n_events": len(rows),
        "n_correct": n_correct,
        "accuracy": (n_correct / len(rows)) if rows else None,
        "events": rows,
        "not_covered": (
            "Spatial (IoU) validation against post-event survey polygons "
            "(Task 5 D5.2) is a separate, still-open gap -- no polygon "
            "ground truth exists in data/historical_events/ to validate "
            "against. This is a scalar discharge/return-period check only."
        ),
    }


def sensitivity_analysis(rainfall_to_discharge_fn: Callable,
                         baseline_rainfall_in: float,
                         baseline_basin_area_km2: float,
                         rainfall_pct: float = 0.20,
                         area_pct: float = 0.10) -> dict:
    """
    Task 5 D5.4 — sensitivity of predicted discharge to (a) GFS forecast
    rainfall error and (b) basin-attribute (area) uncertainty, the two
    error sources named in the whitepaper's Section 5 Step 5.5.

    DEM-resolution sensitivity is NOT included here -- testing it for
    real would mean regenerating the flood library at a different DEM
    resolution, which this function does not do; that scope is left
    honestly open rather than approximated.
    """
    q_base = rainfall_to_discharge_fn(baseline_rainfall_in, basin_area_km2=baseline_basin_area_km2)

    def pct_change(q):
        return ((q - q_base) / q_base * 100.0) if q_base > 0 else None

    q_rain_hi = rainfall_to_discharge_fn(baseline_rainfall_in * (1 + rainfall_pct), basin_area_km2=baseline_basin_area_km2)
    q_rain_lo = rainfall_to_discharge_fn(baseline_rainfall_in * (1 - rainfall_pct), basin_area_km2=baseline_basin_area_km2)
    q_area_hi = rainfall_to_discharge_fn(baseline_rainfall_in, basin_area_km2=baseline_basin_area_km2 * (1 + area_pct))
    q_area_lo = rainfall_to_discharge_fn(baseline_rainfall_in, basin_area_km2=baseline_basin_area_km2 * (1 - area_pct))

    return {
        "baseline": {
            "rainfall_24hr_in": baseline_rainfall_in,
            "basin_area_km2": baseline_basin_area_km2,
            "q_cms": q_base,
        },
        "rainfall_sensitivity": {
            "perturbation_pct": rainfall_pct * 100,
            f"q_at_+{int(rainfall_pct*100)}pct_rainfall_cms": q_rain_hi,
            f"q_at_-{int(rainfall_pct*100)}pct_rainfall_cms": q_rain_lo,
            "pct_change_at_high": pct_change(q_rain_hi),
            "pct_change_at_low": pct_change(q_rain_lo),
        },
        "basin_area_sensitivity": {
            "perturbation_pct": area_pct * 100,
            f"q_at_+{int(area_pct*100)}pct_area_cms": q_area_hi,
            f"q_at_-{int(area_pct*100)}pct_area_cms": q_area_lo,
            "pct_change_at_high": pct_change(q_area_hi),
            "pct_change_at_low": pct_change(q_area_lo),
        },
        "dem_resolution_sensitivity": "not tested -- would require regenerating "
            "the flood library at a different DEM resolution; left as future work.",
    }
