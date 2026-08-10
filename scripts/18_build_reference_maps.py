#!/usr/bin/env python3
"""scripts/18_build_reference_maps.py

Builds the labeled, contextual flood reference map (streets named, real
building footprints, critical facilities called out) for every return
period in the library. See src/probabilistic/reference_maps.py for what
these are and why they exist — they're what a manager can actually read,
unlike the raw depth GeoTIFF alone.

These are static (built from the fixed FEMA/USGS return-period library, not
today's live forecast) — re-run only when the library or tagged local assets
change, not on every forecast cycle.

Run: python scripts/18_build_reference_maps.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from probabilistic.reference_maps import build_all_reference_maps


def main():
    paths = build_all_reference_maps()
    for rp, path in sorted(paths.items()):
        size_kb = path.stat().st_size / 1024
        print(f"  [OK] {rp:>3}-yr  ->  {path.relative_to(ROOT)}  ({size_kb:.0f} KB)")
    print(f"DONE. {len(paths)} reference maps written to {(ROOT / 'outputs' / 'reference_maps').relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
