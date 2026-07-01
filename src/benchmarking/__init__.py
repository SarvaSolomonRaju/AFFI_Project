"""Task 5 - Benchmarking and validation against return periods and historical events."""
from .return_periods import (
    nws_atlas14_sonoita,
    discharge_to_return_period,
    rainfall_to_return_period,
)
from .historical_events import load_events, replay_event
from .validation import pipeline_validation, score_report

__all__ = [
    "nws_atlas14_sonoita",
    "discharge_to_return_period",
    "rainfall_to_return_period",
    "load_events",
    "replay_event",
    "pipeline_validation",
    "score_report",
]
