from __future__ import annotations
import logging
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

GRID_SIZE = 256
RESOLUTION_M = 10.0
CHANNEL_WIDTH_M = 50.0
BANKFULL_WIDTH_M = 100.0
FLOODPLAIN_WIDTH_M = 500.0
SLOPE = 0.008
MANNINGS_N_CHAN = 0.045
MANNINGS_N_FP = 0.080
BASE_ELEVATION = 1200.0


def generate_synthetic_dem(
    grid_size: int = GRID_SIZE,
    resolution_m: float = RESOLUTION_M,
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(seed)

    nrow, ncol = grid_size, grid_size
    center_col = ncol // 2

    y_coords = np.arange(nrow) * resolution_m
    x_coords = np.arange(ncol) * resolution_m

    xx, yy = np.meshgrid(x_coords, y_coords)

    channel_x = center_col * resolution_m
    dist_from_channel = np.abs(xx - channel_x)

    dem = np.full((nrow, ncol), BASE_ELEVATION, dtype=np.float64)

    long_slope = yy * SLOPE
    dem -= long_slope

    half_chan = CHANNEL_WIDTH_M / 2.0
    half_bf = BANKFULL_WIDTH_M / 2.0
    half_fp = FLOODPLAIN_WIDTH_M / 2.0

    chan_mask = dist_from_channel <= half_chan
    bf_mask = (dist_from_channel > half_chan) & (dist_from_channel <= half_bf)
    fp_mask = (dist_from_channel > half_bf) & (dist_from_channel <= half_fp)
    hill_mask = dist_from_channel > half_fp

    channel_depth = 1.5
    dem[chan_mask] -= channel_depth * (1.0 - (dist_from_channel[chan_mask] / half_chan) ** 2)

    bank_height = 0.3
    bf_frac = (dist_from_channel[bf_mask] - half_chan) / (half_bf - half_chan)
    dem[bf_mask] += bank_height * (1.0 - bf_frac)

    fp_slope_rate = 0.005
    fp_dist = dist_from_channel[fp_mask] - half_bf
    dem[fp_mask] += bank_height + fp_dist * fp_slope_rate

    hill_dist = dist_from_channel[hill_mask] - half_fp
    dem[hill_mask] += bank_height + (half_fp - half_bf) * fp_slope_rate + hill_dist * 0.02

    micro_noise = rng.normal(0, 0.05, size=(nrow, ncol))
    dem += micro_noise

    thalweg_elev = dem[np.arange(nrow), center_col]
    dem_norm = dem - thalweg_elev[:, np.newaxis]

    dy, dx = np.gradient(dem, resolution_m)
    slope_grid = np.sqrt(dx**2 + dy**2)

    channel_dist = dist_from_channel.copy()
    channel_dist_norm = channel_dist / channel_dist.max()

    terrain = {
        "dem": dem.astype(np.float32),
        "dem_norm": dem_norm.astype(np.float32),
        "slope": slope_grid.astype(np.float32),
        "channel_distance": channel_dist.astype(np.float32),
        "channel_distance_norm": channel_dist_norm.astype(np.float32),
        "thalweg_elevation": thalweg_elev.astype(np.float32),
        "grid_size": grid_size,
        "resolution_m": resolution_m,
        "center_col": center_col,
        "geometry": {
            "channel_width_m": CHANNEL_WIDTH_M,
            "bankfull_width_m": BANKFULL_WIDTH_M,
            "floodplain_width_m": FLOODPLAIN_WIDTH_M,
            "slope": SLOPE,
            "mannings_n_channel": MANNINGS_N_CHAN,
            "mannings_n_floodplain": MANNINGS_N_FP,
        },
    }

    log.info("Synthetic DEM generated: %dx%d @ %.0fm resolution", nrow, ncol, resolution_m)
    log.info("  Elevation range: [%.1f, %.1f] m", dem.min(), dem.max())
    log.info("  DEM_norm range: [%.2f, %.2f] m", dem_norm.min(), dem_norm.max())
    log.info("  Slope range: [%.4f, %.4f]", slope_grid.min(), slope_grid.max())

    return terrain


def compute_flood_depth(
    terrain: dict,
    discharge_cms: float,
) -> np.ndarray:
    dem_norm = terrain["dem_norm"]
    channel_dist = terrain["channel_distance"]
    nrow, ncol = dem_norm.shape
    center_col = terrain["center_col"]
    resolution = terrain["resolution_m"]

    half_chan = CHANNEL_WIDTH_M / 2.0

    if discharge_cms <= 0:
        return np.zeros((nrow, ncol), dtype=np.float32)

    rhs = discharge_cms * MANNINGS_N_CHAN / (CHANNEL_WIDTH_M * np.sqrt(SLOPE))
    channel_depth = np.power(rhs, 3.0 / 5.0)

    if channel_depth > 1.5:
        q_channel = (1.0 / MANNINGS_N_CHAN) * CHANNEL_WIDTH_M * (1.5 ** (5.0/3.0)) * np.sqrt(SLOPE)
        q_excess = discharge_cms - q_channel

        fp_width = min(FLOODPLAIN_WIDTH_M, BANKFULL_WIDTH_M + q_excess * 2.0)
        rhs_fp = q_excess * MANNINGS_N_FP / (fp_width * np.sqrt(SLOPE))
        fp_depth = np.power(max(rhs_fp, 1e-12), 3.0 / 5.0)

        wse_above_thalweg = 1.5 + fp_depth + 0.3
    else:
        wse_above_thalweg = channel_depth

    depth = np.maximum(0, wse_above_thalweg - dem_norm).astype(np.float32)

    return depth


def save_terrain(terrain: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output_path,
        dem=terrain["dem"],
        dem_norm=terrain["dem_norm"],
        slope=terrain["slope"],
        channel_distance=terrain["channel_distance"],
        channel_distance_norm=terrain["channel_distance_norm"],
        thalweg_elevation=terrain["thalweg_elevation"],
    )
    log.info("Terrain saved -> %s", output_path)
