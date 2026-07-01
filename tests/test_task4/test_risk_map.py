"""Tests for probability-of-inundation + scenario classification."""
import numpy as np
import pytest

from src.probabilistic import probability_of_inundation, classify_scenario


def test_poi_range():
    a = np.zeros((10, 10))
    b = np.ones((10, 10)) * 0.5
    c = np.ones((10, 10)) * 2.0
    poi = probability_of_inundation([a, b, c])
    assert poi.min() >= 0 and poi.max() <= 1


def test_poi_all_wet_is_one():
    wet = np.ones((4, 4))
    poi = probability_of_inundation([wet, wet, wet])
    assert np.allclose(poi, 1.0)


def test_poi_all_dry_is_zero():
    dry = np.zeros((4, 4))
    poi = probability_of_inundation([dry, dry, dry])
    assert np.allclose(poi, 0.0)


def test_poi_weighted_mid():
    # 0.25/0.5/0.25 default weighting; only middle map wet -> 0.5 everywhere
    dry = np.zeros((4, 4))
    wet = np.ones((4, 4))
    poi = probability_of_inundation([dry, wet, dry])
    assert np.allclose(poi, 0.5)


def test_classification_bands():
    # Q=0, no depth -> None
    cl = classify_scenario(0.0, 0.0, 0.0)
    assert cl["severity"] == "None"
    # Moderate-ish
    cl = classify_scenario(15.0, 0.8, 0.2)
    assert cl["severity"] in ("Moderate", "Major")
    # Very large
    cl = classify_scenario(500.0, 5.0, 1.0)
    assert cl["severity"] == "Severe"
