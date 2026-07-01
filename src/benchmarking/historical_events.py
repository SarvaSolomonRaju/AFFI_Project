"""Historical Sonoita Creek flood event catalog + replay."""
from __future__ import annotations
import json
from pathlib import Path
from typing import List

import numpy as np


def load_events(json_path: str | Path) -> List[dict]:
    """Load the historical events JSON file."""
    return json.loads(Path(json_path).read_text())["events"]


def replay_event(event: dict, library, ensemble_fn=None) -> dict:
    """Replay a known event through the flood library.

    Strategy: if event provides observed peak_q_cms, look it up directly.
    Otherwise, derive Q from rainfall via the provided ensemble_fn.
    """
    if "peak_q_cms" in event and event["peak_q_cms"] is not None:
        q = float(event["peak_q_cms"])
        source = "observed_peak_q"
    elif ensemble_fn is not None and "rainfall_24hr_in" in event:
        q = float(ensemble_fn(event["rainfall_24hr_in"]))
        source = "derived_from_rainfall"
    else:
        raise ValueError(f"Event {event.get('name')} has no Q and no ensemble_fn")

    look = library.lookup(q)
    stats = library.summary_stats(look.depth_map)
    # For comparison vs observed gauge stage: use median depth of wet cells
    # (more representative of channel stage than the single deepest pixel).
    import numpy as _np
    _wet = look.depth_map[look.depth_map > 0.05]
    median_depth = float(_np.median(_wet)) if _wet.size > 0 else 0.0
    p90_depth = float(_np.percentile(_wet, 90)) if _wet.size > 0 else 0.0
    return {
        "predicted_median_wet_depth_m": median_depth,
        "predicted_p90_wet_depth_m": p90_depth,
        "name": event.get("name"),
        "date": event.get("date"),
        "source_q": source,
        "q_used_cms": q,
        "q_in_library_range": not look.clipped,
        "predicted_max_depth_m": stats["max_depth_m"],
        "predicted_wet_area_km2": stats["wet_area_km2"],
        "observed_peak_stage_m": event.get("peak_stage_m"),
        "depth_residual_m":
            (median_depth - event["peak_stage_m"])
            if event.get("peak_stage_m") is not None else None,
        "notes": event.get("notes"),
    }
