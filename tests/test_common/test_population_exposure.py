"""
Regression test for the OOM bug fixed 2026-08-10 in population_exposure.py.

_people_per_pixel_on_grid() used to `src.read(1)` the ENTIRE population
raster (CONUS-scale in production, ~2.2GB / 6.8GB peak RSS) just to serve
one small watershed grid. It now reads only a small windowed region around
the destination grid. This test builds a synthetic "national" raster much
larger than the destination grid and asserts the source read is windowed
to a small fraction of it, not the whole file.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import rasterio
from rasterio.transform import from_origin
from affine import Affine

from src.common import population_exposure as pe


def _write_synthetic_pop_raster(path, width=2000, height=2000, res_deg=0.01):
    """A raster much larger than any real watershed grid, uniform population density.

    Covers roughly lon -115..-95, lat 40..20 -- wide enough to contain the
    UTM12N test point used below (EPSG:32612 easting=500000/northing=3500000
    projects to ~lon -111, lat 31.6, in southern Arizona).
    """
    transform = from_origin(-115.0, 40.0, res_deg, res_deg)  # west, north, xres, yres
    data = np.full((height, width), 5.0, dtype="float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=height, width=width, count=1,
        dtype="float32", crs="EPSG:4326", transform=transform, nodata=-99999.0,
    ) as dst:
        dst.write(data, 1)


def test_windowed_read_is_bounded(tmp_path, monkeypatch):
    pop_tif = tmp_path / "synthetic_pop.tif"
    _write_synthetic_pop_raster(pop_tif)
    monkeypatch.setattr(pe, "POP_TIF", pop_tif)
    pe._people_per_pixel_on_grid.cache_clear()

    read_shapes = []
    real_read = rasterio.io.DatasetReader.read

    def spy_read(self, *args, **kwargs):
        result = real_read(self, *args, **kwargs)
        read_shapes.append(result.shape)
        return result

    monkeypatch.setattr(rasterio.io.DatasetReader, "read", spy_read)

    # Small destination grid (10x10 @ 10m, in UTM meters) near the raster's
    # corner -- covers a tiny fraction of the synthetic "national" extent.
    dst_transform = Affine(10.0, 0, 500_000, 0, -10.0, 3_500_000)
    result = pe._people_per_pixel_on_grid(dst_transform, (10, 10))

    assert result is not None
    assert len(read_shapes) == 1
    h, w = read_shapes[0]
    # Full synthetic raster is 1000x2000 = 2,000,000 px. A correctly
    # windowed read for a 10x10 @ 10m grid should be a handful of source
    # pixels, not the whole file.
    assert h * w < 2000, f"read {h}x{w} px -- looks like the full raster was read, not a window"
