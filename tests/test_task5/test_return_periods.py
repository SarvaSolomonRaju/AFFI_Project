"""Tests for Atlas-14 + discharge return-period mappings."""
from src.benchmarking import (
    nws_atlas14_sonoita,
    discharge_to_return_period,
    rainfall_to_return_period,
)
from src.benchmarking.return_periods import return_period_table


def test_atlas14_dict_keys():
    d = nws_atlas14_sonoita()
    for k in ("1yr", "2yr", "10yr", "100yr", "500yr"):
        assert k in d
        assert d[k] > 0


def test_atlas14_monotonic():
    d = nws_atlas14_sonoita()
    rps = [1, 2, 5, 10, 25, 50, 100, 200, 500]
    vals = [d[f"{r}yr"] for r in rps]
    for a, b in zip(vals, vals[1:]):
        assert b > a


def test_rainfall_to_rp_small():
    r = rainfall_to_return_period(0.5)
    assert r["nearest_rp_yr"] == "< 1yr"


def test_rainfall_to_rp_in_range():
    r = rainfall_to_return_period(3.0)
    assert 5 <= r["rp_yr_estimate"] <= 25


def test_rainfall_to_rp_huge():
    r = rainfall_to_return_period(20.0)
    assert r["rp_yr_estimate"] >= 500


def test_discharge_to_rp_monotonic():
    qs = [0.1, 2.0, 8.0, 25.0, 70.0, 200.0]
    rps = [discharge_to_return_period(q)["rp_yr_estimate"] for q in qs]
    for a, b in zip(rps, rps[1:]):
        assert b >= a


def test_return_period_table_complete():
    t = return_period_table()
    assert len(t) == 9
    assert all("return_period_yr" in row and "atlas14_24hr_in" in row
               and "estimated_peak_q_cms" in row for row in t)
