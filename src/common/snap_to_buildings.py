"""Snap the hand-placed infrastructure pins onto real building footprints.

The 16 critical-facility markers (school/fire/hospital/...) in
data/local_assets/infrastructure.geojson are hardcoded approximate lat/lon
(scripts/15_build_infrastructure.py), so they float near — but not on — the
actual buildings, which reads as "the tag isn't pointing at the right
building." The 1,345 building footprints in buildings_huc12.geojson are real
OSM geometry. This snaps each facility point to the centroid of the nearest
building footprint within a small radius, so every pin lands on a real
structure. If nothing is close enough (the curated point is genuinely far
from any mapped building), it's left where it is rather than snapped to
something clearly wrong.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache

from common.paths import DATA_DIR

_BUILDINGS = DATA_DIR / "local_assets" / "buildings_huc12.geojson"

# Max distance a pin may be moved to reach a building. ~120 m covers the
# curated points' typical offset without letting a pin jump across town to a
# building that isn't the intended facility.
SNAP_RADIUS_M = 120.0
_M_PER_DEG_LAT = 111_320.0


def _polygon_centroid(coords: list) -> tuple[float, float] | None:
    """Mean of a polygon's outer-ring vertices — good enough to sit a pin
    on the footprint; exact area-centroid is overkill for a marker."""
    ring = coords[0] if coords and isinstance(coords[0][0], (list, tuple)) else coords
    if not ring:
        return None
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)


@lru_cache(maxsize=1)
def _building_centroids() -> tuple[tuple[float, float], ...]:
    if not _BUILDINGS.exists():
        return ()
    data = json.loads(_BUILDINGS.read_text())
    out: list[tuple[float, float]] = []
    for f in data.get("features", []):
        g = f.get("geometry", {})
        t, c = g.get("type"), g.get("coordinates")
        if t == "Polygon":
            cen = _polygon_centroid(c)
        elif t == "MultiPolygon":
            cen = _polygon_centroid(c[0]) if c else None
        else:
            cen = None
        if cen:
            out.append(cen)
    return tuple(out)


def _meters_between(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians((lat1 + lat2) / 2))
    dx = (lon2 - lon1) * m_per_deg_lon
    dy = (lat2 - lat1) * _M_PER_DEG_LAT
    return math.hypot(dx, dy)


def snap_infrastructure(fc: dict, radius_m: float = SNAP_RADIUS_M) -> dict:
    """Return a copy of the infrastructure FeatureCollection with each Point
    snapped to the nearest building centroid within radius_m. Adds a
    `snapped` bool + `snap_distance_m` to each snapped feature's properties.
    """
    centroids = _building_centroids()
    if not centroids:
        return fc

    for feat in fc.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") != "Point":
            continue
        lon, lat = geom["coordinates"]
        best = None
        best_d = radius_m
        for clon, clat in centroids:
            d = _meters_between(lon, lat, clon, clat)
            if d < best_d:
                best_d, best = d, (clon, clat)
        props = feat.setdefault("properties", {})
        if best is not None:
            geom["coordinates"] = [best[0], best[1]]
            props["snapped"] = True
            props["snap_distance_m"] = round(best_d, 1)
        else:
            props["snapped"] = False
    return fc
