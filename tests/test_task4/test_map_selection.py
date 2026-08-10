"""Provenance for how a flood map is chosen from the library
(src/probabilistic/map_selection.py). Pins the three regimes a manager
needs to trust: dry, interpolated-between-two-maps, and clipped-above."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from src.probabilistic.flood_library import load_real_library
from src.probabilistic.map_selection import describe_selection

lib = load_real_library()


class TestMapSelectionProvenance:
    def test_zero_discharge_is_dry(self):
        look = lib.lookup(0.0)
        sel = describe_selection(look, rainfall_in=0.0, discharge_cms=0.0)
        assert sel["regime"] == "dry"
        assert sel["leopold_scale"] == 0.0

    def test_below_smallest_is_not_dry_but_leopold_scaled(self):
        # 18.5 cms is below the 2-yr (83.6) library map — the lookup does NOT
        # return dry, it extrapolates the 2-yr map down by Leopold scaling,
        # so this must be honestly labeled as sub-2yr with real (reduced)
        # depth, never "dry / no flood".
        look = lib.lookup(18.5)
        sel = describe_selection(look, rainfall_in=3.93, discharge_cms=18.5)
        assert sel["regime"] == "below_smallest"
        assert sel["smallest_return_period_yr"] == 2
        assert 0.0 < sel["leopold_scale"] < 1.0
        # and the map it scales really does carry depth (not dry):
        assert float(look.depth_map.max()) > 0.5

    def test_mid_discharge_interpolates_between_two_return_periods(self):
        # 350 cms sits between the 25-yr (317) and 50-yr (385) library maps.
        look = lib.lookup(350.0)
        sel = describe_selection(look, rainfall_in=3.0, discharge_cms=350.0)
        assert sel["regime"] == "interior"
        b = sel["bracket"]
        assert b["low"]["return_period_yr"] == 25
        assert b["high"]["return_period_yr"] == 50
        assert b["exact_match"] is False
        assert 0.0 < b["interp_weight"] < 1.0

    def test_extreme_discharge_clips_to_largest_map(self):
        look = lib.lookup(99999.0)
        sel = describe_selection(look, rainfall_in=12.0, discharge_cms=99999.0)
        assert sel["regime"] == "clipped_above"

    def test_exact_return_period_discharge_is_an_exact_match(self):
        # 454.6 cms is exactly the 100-yr library discharge.
        look = lib.lookup(454.58)
        sel = describe_selection(look, rainfall_in=4.32, discharge_cms=454.58)
        assert sel["regime"] == "interior"
        assert sel["bracket"]["exact_match"] is True
        assert sel["bracket"]["low"]["return_period_yr"] == 100
