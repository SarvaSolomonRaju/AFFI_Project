"""Task 4 - Probabilistic flood-map library lookup and ensemble propagation."""
from .flood_library import FloodMapLibrary
from .ensemble import rainfall_to_discharge, propagate_ensemble
from .risk_map import probability_of_inundation, classify_scenario

__all__ = [
    "FloodMapLibrary",
    "rainfall_to_discharge",
    "propagate_ensemble",
    "probability_of_inundation",
    "classify_scenario",
]
