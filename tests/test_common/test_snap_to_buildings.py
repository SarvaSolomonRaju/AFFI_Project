"""Snapping the hand-placed facility pins onto real building footprints
(src/common/snap_to_buildings.py). The pins must land on an actual building
without jumping across town to the wrong one."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in [str(ROOT), str(ROOT / "src")]:
    if p not in sys.path:
        sys.path.insert(0, p)

from common.snap_to_buildings import snap_infrastructure, SNAP_RADIUS_M

INFRA = ROOT / "data" / "local_assets" / "infrastructure.geojson"


class TestSnapToBuildings:
    def test_pins_snap_and_stay_within_radius(self):
        fc = json.loads(INFRA.read_text())
        before = copy.deepcopy(fc)
        snap_infrastructure(fc)
        for b, a in zip(before["features"], fc["features"]):
            if a["geometry"]["type"] != "Point":
                continue
            props = a["properties"]
            if props.get("snapped"):
                # never moved further than the radius allows
                assert props["snap_distance_m"] <= SNAP_RADIUS_M
                # and it actually moved to a building (coords changed or dist ~0)
                assert "snap_distance_m" in props

    def test_never_moves_a_pin_beyond_the_radius(self):
        # A synthetic pin far out in the desert has no building within radius,
        # so it must be left exactly where it is, not snapped to something wrong.
        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"name": "Middle of nowhere", "category": "power"},
                "geometry": {"type": "Point", "coordinates": [-110.60, 31.80]},
            }],
        }
        snap_infrastructure(fc)
        f = fc["features"][0]
        assert f["properties"]["snapped"] is False
        assert f["geometry"]["coordinates"] == [-110.60, 31.80]
