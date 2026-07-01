from __future__ import annotations
import sys
from pathlib import Path

import pytest
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from hydraulics.terrain import (
    generate_synthetic_dem,
    compute_flood_depth,
    GRID_SIZE,
    CHANNEL_WIDTH_M,
    BANKFULL_WIDTH_M,
    FLOODPLAIN_WIDTH_M,
    BASE_ELEVATION,
    RESOLUTION_M,
)


class TestGenerateSyntheticDEM:
    @pytest.fixture(scope="class")
    def terrain(self):
        return generate_synthetic_dem(grid_size=128, resolution_m=10.0, seed=42)

    def test_dem_shape(self, terrain):
        assert terrain["dem"].shape == (128, 128)
        assert terrain["dem_norm"].shape == (128, 128)
        assert terrain["slope"].shape == (128, 128)
        assert terrain["channel_distance"].shape == (128, 128)

    def test_dem_dtype(self, terrain):
        assert terrain["dem"].dtype == np.float32
        assert terrain["dem_norm"].dtype == np.float32

    def test_channel_is_lowest(self, terrain):
        center = terrain["center_col"]
        dem_norm = terrain["dem_norm"]
        for row in range(0, dem_norm.shape[0], 10):
            assert dem_norm[row, center] <= dem_norm[row, 0], \
                f"Channel should be lowest point at row {row}"

    def test_elevation_range(self, terrain):
        dem = terrain["dem"]
        assert dem.min() > 1000.0
        assert dem.max() < 1400.0

    def test_geometry_keys(self, terrain):
        geom = terrain["geometry"]
        assert geom["channel_width_m"] == CHANNEL_WIDTH_M
        assert geom["bankfull_width_m"] == BANKFULL_WIDTH_M
        assert geom["floodplain_width_m"] == FLOODPLAIN_WIDTH_M

    def test_thalweg_elevation(self, terrain):
        thal = terrain["thalweg_elevation"]
        assert thal.shape == (128,)
        assert thal[0] > thal[-1], "Thalweg should decrease downstream"

    def test_dem_norm_channel_near_zero(self, terrain):
        center = terrain["center_col"]
        dem_norm = terrain["dem_norm"]
        channel_norms = dem_norm[:, center]
        assert np.abs(channel_norms).max() < 2.0, "DEM_norm at channel should be near zero"


class TestComputeFloodDepth:
    @pytest.fixture(scope="class")
    def terrain(self):
        return generate_synthetic_dem(grid_size=128, resolution_m=10.0, seed=42)

    def test_zero_discharge(self, terrain):
        depth = compute_flood_depth(terrain, 0.0)
        assert depth.shape == (128, 128)
        assert np.allclose(depth, 0.0)

    def test_small_discharge_in_channel(self, terrain):
        depth = compute_flood_depth(terrain, 1.0)
        assert depth.max() > 0.0
        assert depth.max() < 3.0

    def test_large_discharge_floods(self, terrain):
        depth = compute_flood_depth(terrain, 200.0)
        wet_cells = (depth > 0.01).sum()
        total_cells = depth.size
        wet_fraction = wet_cells / total_cells
        assert wet_fraction > 0.05, "Large discharge should flood significant area"

    def test_depth_increases_with_discharge(self, terrain):
        d1 = compute_flood_depth(terrain, 10.0)
        d2 = compute_flood_depth(terrain, 100.0)
        assert d2.max() > d1.max()

    def test_output_dtype(self, terrain):
        depth = compute_flood_depth(terrain, 5.0)
        assert depth.dtype == np.float32

    def test_no_negative_depth(self, terrain):
        depth = compute_flood_depth(terrain, 50.0)
        assert (depth >= 0).all()
