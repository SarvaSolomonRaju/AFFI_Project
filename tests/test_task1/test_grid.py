"""
test_grid.py — Tests for Grid Point Generation
=================================================
WHAT ARE TESTS?
    Tests are code that checks if your OTHER code works correctly.

    Instead of running the whole pipeline and eyeballing the output,
    tests automatically verify specific behaviors:

    "Does build_grid_points() return exactly 5 points?"
    "Do the weights sum to 1.0?"
    "Is the center point actually in the center?"

    If any test fails, you know EXACTLY what broke and WHERE.

WHY WRITE TESTS?
    1. Catch bugs BEFORE they reach production
    2. Safely refactor code (change internals, tests verify behavior)
    3. Documentation — tests show HOW functions should be used
    4. Required for research papers (reproducibility)
    5. Required for PhD-level work

HOW TO RUN:
    cd FloodAI
    pytest tests/test_grid.py -v

    Output:
    test_grid.py::test_returns_5_points PASSED
    test_grid.py::test_weights_sum_to_one PASSED
    ...
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from src.forecast.grid import build_grid_points


# Sample bounding box (Upper Sonoita Creek)
SAMPLE_BBOX = {
    "north": 31.85,
    "south": 31.47,
    "east": -110.50,
    "west": -110.90
}


def test_returns_5_points():
    """Grid should return exactly 5 points."""
    points = build_grid_points(SAMPLE_BBOX)
    assert len(points) == 5, f"Expected 5 points, got {len(points)}"


def test_weights_sum_to_one():
    """All weights must sum to 1.0 (within floating point tolerance)."""
    points = build_grid_points(SAMPLE_BBOX)
    total = sum(pt["weight"] for pt in points)
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"


def test_center_point_is_centered():
    """P1 (center) should be at the midpoint of the bounding box."""
    points = build_grid_points(SAMPLE_BBOX)
    center = points[0]

    expected_lat = (31.85 + 31.47) / 2  # 31.66
    expected_lon = (-110.50 + -110.90) / 2  # -110.70

    assert abs(center["lat"] - expected_lat) < 0.01
    assert abs(center["lon"] - expected_lon) < 0.01


def test_center_has_highest_weight():
    """Center point should have the highest weight."""
    points = build_grid_points(SAMPLE_BBOX)
    center_weight = points[0]["weight"]
    other_weights = [pt["weight"] for pt in points[1:]]

    assert all(center_weight >= w for w in other_weights), \
        "Center point should have highest weight"


def test_all_points_within_bbox():
    """All points must be within the bounding box."""
    points = build_grid_points(SAMPLE_BBOX)
    for pt in points:
        assert SAMPLE_BBOX["south"] <= pt["lat"] <= SAMPLE_BBOX["north"], \
            f"{pt['id']} lat {pt['lat']} outside bbox"
        assert SAMPLE_BBOX["west"] <= pt["lon"] <= SAMPLE_BBOX["east"], \
            f"{pt['id']} lon {pt['lon']} outside bbox"


def test_custom_weights():
    """Custom weights should be applied correctly."""
    points = build_grid_points(SAMPLE_BBOX, 
                                center_weight=0.50,
                                cardinal_weight=0.15,
                                diagonal_weight=0.10)
    assert points[0]["weight"] == pytest.approx(0.50, abs=0.01)


def test_weight_normalization():
    """Weights that don't sum to 1.0 should be normalized."""
    # These sum to 0.5, should be normalized to 1.0
    points = build_grid_points(SAMPLE_BBOX,
                                center_weight=0.15,
                                cardinal_weight=0.10,
                                diagonal_weight=0.05)
    total = sum(pt["weight"] for pt in points)
    assert abs(total - 1.0) < 0.01, f"Normalized weights should sum to 1.0, got {total}"


def test_each_point_has_required_keys():
    """Every point must have id, lat, lon, weight, desc."""
    points = build_grid_points(SAMPLE_BBOX)
    required_keys = {"id", "lat", "lon", "weight", "desc"}
    for pt in points:
        assert required_keys.issubset(pt.keys()), \
            f"Point {pt.get('id', '?')} missing keys: {required_keys - set(pt.keys())}"
