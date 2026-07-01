"""Flood-map library: pre-computed depth maps indexed by discharge.

Implements the advisor's plan: at runtime, identify which pre-computed
flood map matches the current rainfall situation. Uses linear interpolation
between the two nearest stored discharge values.

Pattern mirrors NOAA OWP FIM and FEMA flood library systems.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class LookupResult:
    """Result of looking up a flood map for a given discharge."""
    depth_map: np.ndarray            # (H, W) interpolated depth in meters
    q_requested_cms: float
    q_low_cms: float
    q_high_cms: float
    interp_weight: float             # 0 => q_low map, 1 => q_high map
    clipped: bool                    # True if q was outside library range


class FloodMapLibrary:
    """Pre-computed depth-map library indexed by discharge (cms).

    Backing file is the .npz produced by Task 3
    (outputs/task3/spatial_predictions.npz) with keys:
        discharges_cms : (N,) float32
        depth_maps     : (N, H, W) float32 meters
        grid_size      : int (H==W)
        resolution_m   : float (cell size)
    """

    def __init__(self, discharges_cms: np.ndarray, depth_maps: np.ndarray,
                 resolution_m: float):
        order = np.argsort(discharges_cms)
        self.discharges_cms = np.asarray(discharges_cms)[order].astype(np.float32)
        self.depth_maps = np.asarray(depth_maps)[order].astype(np.float32)
        self.resolution_m = float(resolution_m)
        self.grid_size = int(self.depth_maps.shape[1])
        self.cell_area_m2 = self.resolution_m ** 2

    @classmethod
    def load(cls, npz_path: str | Path) -> "FloodMapLibrary":
        d = np.load(npz_path)
        return cls(
            discharges_cms=d["discharges_cms"],
            depth_maps=d["depth_maps"],
            resolution_m=float(d["resolution_m"]),
        )

    @property
    def n_maps(self) -> int:
        return int(self.depth_maps.shape[0])

    @property
    def q_min_cms(self) -> float:
        return float(self.discharges_cms.min())

    @property
    def q_max_cms(self) -> float:
        return float(self.discharges_cms.max())

    def lookup(self, q_cms: float) -> LookupResult:
        """Return depth map matching discharge q_cms (linear interpolation)."""
        q = float(q_cms)
        qs = self.discharges_cms
        clipped = False
        if q <= qs[0]:
            # Below library minimum: scale depth by Leopold (depth ~ Q^0.4)
            # so that very small Q returns nearly-dry conditions.
            if q <= 0:
                scale = 0.0
            else:
                scale = float((q / qs[0]) ** 0.4)
            return LookupResult(
                depth_map=(self.depth_maps[0] * scale).astype(np.float32),
                q_requested_cms=q, q_low_cms=float(qs[0]),
                q_high_cms=float(qs[0]), interp_weight=0.0,
                clipped=bool(q < qs[0]),
            )
        if q >= qs[-1]:
            clipped = bool(q > qs[-1])
            return LookupResult(
                depth_map=self.depth_maps[-1].copy(),
                q_requested_cms=q, q_low_cms=float(qs[-1]),
                q_high_cms=float(qs[-1]), interp_weight=1.0,
                clipped=clipped,
            )
        hi = int(np.searchsorted(qs, q, side="right"))
        lo = hi - 1
        q_lo, q_hi = float(qs[lo]), float(qs[hi])
        w = (q - q_lo) / (q_hi - q_lo) if q_hi > q_lo else 0.0
        depth = (1.0 - w) * self.depth_maps[lo] + w * self.depth_maps[hi]
        return LookupResult(
            depth_map=depth.astype(np.float32),
            q_requested_cms=q, q_low_cms=q_lo, q_high_cms=q_hi,
            interp_weight=float(w), clipped=False,
        )

    def wet_area_m2(self, depth_map: np.ndarray, threshold_m: float = 0.01) -> float:
        return float((depth_map >= threshold_m).sum()) * self.cell_area_m2

    def summary_stats(self, depth_map: np.ndarray,
                      threshold_m: float = 0.01) -> dict:
        wet = depth_map >= threshold_m
        n_wet = int(wet.sum())
        wet_area_km2 = n_wet * self.cell_area_m2 / 1.0e6
        return {
            "max_depth_m": float(depth_map.max()),
            "mean_depth_wet_m": float(depth_map[wet].mean()) if n_wet > 0 else 0.0,
            "wet_pixels": n_wet,
            "wet_area_m2": n_wet * self.cell_area_m2,
            "wet_area_km2": wet_area_km2,
            "total_volume_m3": float(depth_map.sum()) * self.cell_area_m2,
        }

    def index_summary(self) -> dict:
        return {
            "n_maps": self.n_maps,
            "q_min_cms": self.q_min_cms,
            "q_max_cms": self.q_max_cms,
            "grid_size": self.grid_size,
            "resolution_m": self.resolution_m,
            "discharges_cms": self.discharges_cms.tolist(),
        }


# ---------------------------------------------------------------------------
# Real-data loader: build a FloodMapLibrary from the Plan-B GeoTIFF library
# under data/flood_library_real/ (FEMA NFHL + FEMA BFE + USGS 3DEP + USGS LP-III)
# ---------------------------------------------------------------------------
def load_real_library(real_dir: str | Path = "data/flood_library_real") -> "FloodMapLibrary":
    """Load the real flood-map library built from FEMA + USGS open data.

    Returns a FloodMapLibrary indexed by discharge Q (cms), with depth maps
    sourced from real FEMA-effective inundation extents (NFHL AE/X), real
    FEMA Base Flood Elevations, and the real USGS 3DEP 10-m DEM for HUC-12
    Sonoita Creek (150503010204).
    """
    import rasterio
    real_dir = Path(real_dir)
    manifest = json.loads((real_dir / "manifest.json").read_text())
    rp = manifest["return_periods"]
    files = manifest["files"]
    Qs, maps = [], []
    res_m = None
    for T, info in sorted(rp.items(), key=lambda kv: float(kv[1]["Q_cms"])):
        Q = float(info["Q_cms"])
        with rasterio.open(real_dir / files[T]) as r:
            depth = r.read(1).astype(np.float32)
            depth = np.nan_to_num(depth, nan=0.0, posinf=0.0, neginf=0.0)
            if res_m is None:
                res_m = float(abs(r.transform.a))
        Qs.append(Q); maps.append(depth)
    Qs = np.asarray(Qs, dtype=np.float32)
    maps = np.stack(maps, axis=0).astype(np.float32)
    lib = FloodMapLibrary(discharges_cms=Qs, depth_maps=maps, resolution_m=res_m or 10.0)
    lib.provenance = {
        "source": manifest.get("source", "FEMA NFHL + USGS 3DEP + USGS LP-III"),
        "method": manifest.get("method", ""),
        "huc12": manifest.get("huc12"),
        "gauge": manifest.get("gauge"),
        "n_maps": int(len(Qs)),
        "real_data": True,
    }
    return lib
