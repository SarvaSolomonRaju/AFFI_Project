"""Prediction vs. reality — the honesty engine.

A forecast tool nobody can check is a tool nobody should trust. This pairs
each past forecast (stored in floodai.db forecast_runs) with what actually
happened afterward, measured by the nearest real-time USGS gauge, scores
each as hit / miss / false-alarm / correct-calm, and reports a running track
record plus a self-correction signal (is the model systematically over- or
under-forecasting, and by how much).

Honest limits, stated in the API response, not hidden:
  * The pilot creek gauge (09481500) has no live telemetry, so "reality"
    comes from the nearest telemetered gauge downstream (09480500, Santa
    Cruz River near Nogales) — a PROXY in the same river system, not the
    exact bridge. A spike there is strong evidence of a regional event, not
    proof of flooding at one specific culvert.
  * Verification needs observed data for a forecast's target date. Future-
    dated runs read "awaiting observation" until that day passes — the track
    record grows over time, it isn't fabricated up front.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import httpx

NWIS_DV_URL = "https://waterservices.usgs.gov/nwis/dv/"
PROXY_GAUGE = {"id": "09480500", "name": "Santa Cruz River near Nogales, AZ"}

# Observed daily-mean discharge above this (cfs) at the proxy gauge counts as
# "a real event happened" for scoring. Santa Cruz near Nogales is ephemeral —
# near-zero most days, spiking in monsoon — so a modest floor separates a real
# pulse from baseflow noise. Deliberately conservative; tune with local data.
OBSERVED_EVENT_CFS = 50.0

# Our forecast alert levels that mean "we expect a flood."
_PREDICTED_FLOOD = {"WATCH", "WARNING", "ORANGE", "RED"}


def fetch_observed_daily(start_date: str, end_date: str) -> dict[str, float]:
    """{'YYYY-MM-DD': mean_cfs} of daily-mean discharge at the proxy gauge.

    Empty dict on any USGS failure — never invents observations.
    """
    params = {
        "sites": PROXY_GAUGE["id"],
        "parameterCd": "00060",   # discharge, cfs
        "statCd": "00003",        # daily mean
        "startDT": start_date,
        "endDT": end_date,
        "format": "json",
    }
    try:
        resp = httpx.get(NWIS_DV_URL, params=params, timeout=15.0,
                         headers={"User-Agent": "AFFI-FloodAI verification"})
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return {}

    out: dict[str, float] = {}
    for s in data.get("value", {}).get("timeSeries", []):
        for v in s["values"][0]["value"]:
            day = v["dateTime"][:10]
            try:
                out[day] = float(v["value"])
            except (TypeError, ValueError):
                continue
    return out


def _verdict(predicted_flood: bool, observed_cfs: float | None) -> tuple[str, str]:
    """(category, plain-language verdict)."""
    if observed_cfs is None:
        return "pending", "Awaiting observation"
    observed_event = observed_cfs >= OBSERVED_EVENT_CFS
    if predicted_flood and observed_event:
        return "hit", "Predicted a flood — one happened"
    if predicted_flood and not observed_event:
        return "false_alarm", "Predicted a flood — gauge stayed quiet"
    if not predicted_flood and observed_event:
        return "miss", "Called it calm — gauge spiked"
    return "correct_calm", "Called it calm — it stayed calm"


def build_verification(recent_runs: list[dict]) -> dict:
    """recent_runs: rows from FloodDatabase.get_recent_runs() (each has
    run_time, current_alert, p50_max_24hr, ...). Returns the paired
    prediction-vs-reality record, track-record summary, and self-correction
    signal.
    """
    if not recent_runs:
        return {
            "records": [], "summary": _empty_summary(),
            "self_correction": {"tendency": "unknown", "note": "No forecast history yet."},
            "observed_source": PROXY_GAUGE, "proxy_note": _PROXY_NOTE,
            "observed_event_threshold_cfs": OBSERVED_EVENT_CFS,
        }

    # date window covering the runs, for one batched USGS call
    dates = [r["run_time"][:10] for r in recent_runs if r.get("run_time")]
    start = min(dates)
    end = (datetime.strptime(max(dates), "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    observed = fetch_observed_daily(start, end)

    records = []
    for r in recent_runs:
        day = (r.get("run_time") or "")[:10]
        predicted_alert = r.get("current_alert", "GREEN")
        predicted_flood = predicted_alert in _PREDICTED_FLOOD
        obs = observed.get(day)
        category, verdict = _verdict(predicted_flood, obs)
        records.append({
            "date": day,
            "predicted_alert": predicted_alert,
            "predicted_p50_in": r.get("p50_max_24hr"),
            "predicted_p90_in": r.get("p90_max_24hr"),
            "observed_mean_cfs": round(obs, 1) if obs is not None else None,
            "category": category,
            "verdict": verdict,
        })

    summary = _summarize(records)
    return {
        "records": records,
        "summary": summary,
        "self_correction": _self_correction(summary),
        "observed_source": PROXY_GAUGE,
        "proxy_note": _PROXY_NOTE,
        "observed_event_threshold_cfs": OBSERVED_EVENT_CFS,
    }


_PROXY_NOTE = (
    "Reality is measured at the nearest LIVE gauge (Santa Cruz River near "
    "Nogales, ~13 mi downstream) because the pilot creek gauge has no real-"
    "time telemetry. A spike there means a regional event occurred, not that "
    "one specific bridge flooded."
)


def _empty_summary() -> dict:
    return {"n_verified": 0, "hits": 0, "misses": 0, "false_alarms": 0,
            "correct_calm": 0, "hit_rate_pct": None, "false_alarm_rate_pct": None}


def _summarize(records: list[dict]) -> dict:
    hits = sum(1 for r in records if r["category"] == "hit")
    misses = sum(1 for r in records if r["category"] == "miss")
    false_alarms = sum(1 for r in records if r["category"] == "false_alarm")
    correct_calm = sum(1 for r in records if r["category"] == "correct_calm")
    n_verified = hits + misses + false_alarms + correct_calm
    events = hits + misses  # times reality actually flooded
    predicted_events = hits + false_alarms
    return {
        "n_verified": n_verified,
        "hits": hits, "misses": misses,
        "false_alarms": false_alarms, "correct_calm": correct_calm,
        # of real events, how many we caught
        "hit_rate_pct": round(100 * hits / events, 0) if events else None,
        # of our flood calls, how many were wrong
        "false_alarm_rate_pct": round(100 * false_alarms / predicted_events, 0) if predicted_events else None,
    }


def _self_correction(summary: dict) -> dict:
    """Turn the track record into a plain over/under tendency + a nudge."""
    fa = summary["false_alarms"]
    miss = summary["misses"]
    if summary["n_verified"] < 3:
        return {"tendency": "learning", "note": "Not enough verified events yet — the track record builds as more days are observed.", "suggested_threshold_delta_in": 0.0}
    if fa > miss:
        return {
            "tendency": "over-forecasting",
            "note": f"Called {fa} floods that didn't materialize vs {miss} it missed — running HIGH. Future forecasts should raise the rain threshold slightly to cut false alarms.",
            "suggested_threshold_delta_in": round(0.1 * (fa - miss), 2),
        }
    if miss > fa:
        return {
            "tendency": "under-forecasting",
            "note": f"Missed {miss} real events vs {fa} false alarms — running LOW. Future forecasts should lower the rain threshold to catch more events.",
            "suggested_threshold_delta_in": round(-0.1 * (miss - fa), 2),
        }
    return {"tendency": "balanced", "note": "False alarms and misses are balanced — no systematic bias to correct.", "suggested_threshold_delta_in": 0.0}
