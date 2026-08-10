"""Explain how the displayed flood map was selected from the library.

This is pure provenance -- it computes nothing new, it just describes the
lookup that src/probabilistic/flood_library.py already performs (rainfall ->
discharge -> nearest pre-computed depth map, interpolated between the two
bracketing return-period maps). The dashboard was silently showing the
result of that lookup with no way to see the reasoning; this turns the
LookupResult into a labeled, human-readable chain so a manager can see
"today's rainfall -> predicted discharge -> matched to the N-yr library map."

The flood library is indexed by discharge, and each stored discharge is
exactly a return-period Q from data/flood_library_real/manifest.json, so a
discharge value maps back to a return-period label unambiguously.
"""
from __future__ import annotations

import json
from pathlib import Path

from common.paths import DATA_DIR

_MANIFEST = DATA_DIR / "flood_library_real" / "manifest.json"


def _q_to_return_period() -> list[tuple[float, int]]:
    """[(Q_cms, return_period_yr), ...] sorted by Q, from the library manifest."""
    if not _MANIFEST.exists():
        return []
    manifest = json.loads(_MANIFEST.read_text())
    pairs = [(float(v["Q_cms"]), int(T)) for T, v in manifest.get("return_periods", {}).items()]
    return sorted(pairs, key=lambda p: p[0])


def _nearest_return_period(q_cms: float, table: list[tuple[float, int]]) -> int | None:
    if not table:
        return None
    return min(table, key=lambda p: abs(p[0] - q_cms))[1]


def describe_selection(look, rainfall_in: float, discharge_cms: float) -> dict:
    """Turn a flood_library.LookupResult into a provenance dict.

    `look` is the LookupResult for the P50 (likely) scenario -- q_low_cms,
    q_high_cms, interp_weight, clipped.
    """
    table = _q_to_return_period()
    smallest_q, smallest_rp = (table[0][0], table[0][1]) if table else (None, None)

    # Regime the discharge falls in — honest about what the library actually
    # returns, which is NOT simply "dry vs flood":
    #   dry            : q <= 0, genuinely no flooding, no map shown.
    #   below_smallest : 0 < q < smallest stored Q. The library does NOT
    #                    return dry here — it extrapolates DOWN from the
    #                    smallest (e.g. 2-yr) map via Leopold depth scaling
    #                    (depth ~ Q^0.4), so real, reduced depth is shown.
    #                    (See flood_library.py lookup(), q <= qs[0] branch.)
    #   clipped_above  : q above the largest stored map, capped there.
    #   interior       : between two stored maps (interpolated or exact).
    if discharge_cms <= 0:
        regime = "dry"
        leopold_scale = 0.0
    elif smallest_q is not None and discharge_cms < smallest_q:
        regime = "below_smallest"
        leopold_scale = round(float((discharge_cms / smallest_q) ** 0.4), 3)
    elif look.clipped:
        regime = "clipped_above"
        leopold_scale = None
    else:
        regime = "interior"
        leopold_scale = None

    rp_low = _nearest_return_period(look.q_low_cms, table)
    rp_high = _nearest_return_period(look.q_high_cms, table)
    w = float(look.interp_weight)
    # A single stored map is shown (no blend) when the two brackets are the
    # same map, OR the weight sits fully on one end -- e.g. a discharge that
    # lands exactly on the 100-yr library Q gives weight 0 (all of the low
    # map), which is still an exact match, not a 100yr<->200yr interpolation.
    exact = (rp_low == rp_high) or w <= 0.001 or w >= 0.999

    return {
        "rainfall_in": round(float(rainfall_in), 3),
        "discharge_cms": round(float(discharge_cms), 1),
        "regime": regime,
        "smallest_return_period_yr": smallest_rp,
        "leopold_scale": leopold_scale,
        "bracket": {
            "low":  {"return_period_yr": rp_low,  "q_cms": round(float(look.q_low_cms), 1)},
            "high": {"return_period_yr": rp_high, "q_cms": round(float(look.q_high_cms), 1)},
            "interp_weight": round(float(look.interp_weight), 3),
            "exact_match": bool(exact),
        },
        "method": (
            "SCS Curve-Number converts forecast rainfall to peak discharge, "
            "then the discharge-indexed flood library returns the nearest "
            "pre-computed depth map (linear interpolation between the two "
            "bracketing return-period maps). Library: FEMA BFE + USGS 3DEP DEM."
        ),
    }
