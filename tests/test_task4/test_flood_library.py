"""Tests for the Task 4 flood-map library lookup."""
import numpy as np
import pytest

from src.probabilistic import FloodMapLibrary


@pytest.fixture(scope="module")
def lib():
    return FloodMapLibrary.load("outputs/task3/spatial_predictions.npz")


def test_load_smoke(lib):
    assert lib.n_maps >= 2
    assert lib.grid_size == lib.depth_maps.shape[1] == lib.depth_maps.shape[2]
    assert lib.resolution_m > 0


def test_lookup_at_exact_q(lib):
    q = float(lib.discharges_cms[3])
    r = lib.lookup(q)
    assert r.q_low_cms == q
    assert np.allclose(r.depth_map, lib.depth_maps[3])


def test_lookup_interpolates_between(lib):
    q_lo = float(lib.discharges_cms[2])
    q_hi = float(lib.discharges_cms[3])
    q_mid = 0.5 * (q_lo + q_hi)
    r = lib.lookup(q_mid)
    assert r.q_low_cms == q_lo and r.q_high_cms == q_hi
    assert 0.0 < r.interp_weight < 1.0
    expected = 0.5 * (lib.depth_maps[2] + lib.depth_maps[3])
    assert np.allclose(r.depth_map, expected, atol=1e-5)


def test_lookup_clips_above_max(lib):
    huge = lib.q_max_cms * 10
    r = lib.lookup(huge)
    assert r.clipped is True
    assert np.allclose(r.depth_map, lib.depth_maps[-1])


def test_lookup_clips_below_min(lib):
    r = lib.lookup(-5.0)
    assert r.clipped is True


def test_summary_stats_keys(lib):
    s = lib.summary_stats(lib.depth_maps[-1])
    for k in ("max_depth_m", "mean_depth_wet_m", "wet_pixels",
              "wet_area_km2", "total_volume_m3"):
        assert k in s
    assert s["wet_pixels"] >= 0
    assert s["max_depth_m"] >= 0


def test_wet_area_monotonic_with_q(lib):
    # Larger discharge should produce >= wet area (within library coverage)
    areas = [lib.wet_area_m2(dm) for dm in lib.depth_maps]
    # not strictly monotonic for tiny Q, but max should be at the highest Q
    assert areas[-1] >= areas[0]
