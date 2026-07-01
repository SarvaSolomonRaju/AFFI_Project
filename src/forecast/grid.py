"""
grid.py — Rainfall Grid Point Generator
=========================================
WHAT THIS DOES:
    Creates measurement points across your watershed.
    Instead of measuring rainfall at ONE spot, we measure at
    5 spots and combine them (weighted average).

WHY MULTIPLE POINTS?
    Monsoon storms in Arizona are VERY localized.
    A thunderstorm can dump 2 inches on the north side of your
    watershed while the south side gets nothing.

    If you only measured at the center, you'd miss that storm.
    5 points with weights gives a much better estimate of
    "total rainfall over the entire watershed."

WHAT ARE WEIGHTS?
    Not all points contribute equally.
    The CENTER point (near the outlet/pour point) gets 30% weight
    because water from the center reaches the outlet fastest.
    Edge points get less weight (15-20%).

    Think of it like grading:
    - Final exam (center) = 30% of your grade
    - Midterm (north/south) = 20% each
    - Homework (east/west) = 15% each
    Total = 100%

LIMITATION (for your research paper):
    These weights are ESTIMATED, not computed.
    The proper method is "Thiessen polygons" (also called
    Voronoi diagrams) which calculates weights based on
    the actual area each gauge represents.
    Mention this as a "future improvement" in your paper.
"""

from typing import List, Dict
from common.logging_setup import get_logger

logger = get_logger(__name__)


def build_grid_points(bbox: Dict[str, float],
                      center_weight: float = 0.30,
                      cardinal_weight: float = 0.20,
                      diagonal_weight: float = 0.15) -> List[Dict]:
    """
    Generate weighted grid points from a bounding box.

    Parameters
    ----------
    bbox : dict
        Must have keys: north, south, east, west (all floats)
    center_weight : float
        Weight for the center point (default 0.30 = 30%)
    cardinal_weight : float
        Weight for north and south points (default 0.20 = 20% each)
    diagonal_weight : float
        Weight for east and west points (default 0.15 = 15% each)

    Returns
    -------
    list of dict
        Each dict has: id, lat, lon, weight, desc

    HOW THE MATH WORKS:
        lat_mid = (31.85 + 31.47) / 2 = 31.66  (center latitude)
        lon_mid = (-110.50 + -110.90) / 2 = -110.70  (center longitude)

        P1 = center (31.66, -110.70) — weight 0.30
        P2 = north  (31.85, -110.70) — weight 0.20
        P3 = south  (31.47, -110.70) — weight 0.20
        P4 = east   (31.66, -110.50) — weight 0.15
        P5 = west   (31.66, -110.90) — weight 0.15

        Total weight = 0.30 + 0.20 + 0.20 + 0.15 + 0.15 = 1.00 ✓
    """
    lat_mid = (bbox["north"] + bbox["south"]) / 2
    lon_mid = (bbox["east"] + bbox["west"]) / 2

    # Verify weights sum to 1.0
    total_weight = center_weight + 2 * cardinal_weight + 2 * diagonal_weight
    if abs(total_weight - 1.0) > 0.01:
        logger.warning("Grid weights sum to %.3f (should be 1.0) — normalizing", 
                       total_weight)
        center_weight /= total_weight
        cardinal_weight /= total_weight
        diagonal_weight /= total_weight

    points = [
        {
            "id": "P1", 
            "lat": round(lat_mid, 6), 
            "lon": round(lon_mid, 6),
            "weight": center_weight, 
            "desc": "Watershed Center (outlet area)"
        },
        {
            "id": "P2", 
            "lat": round(bbox["north"], 6), 
            "lon": round(lon_mid, 6),
            "weight": cardinal_weight, 
            "desc": "Upper North"
        },
        {
            "id": "P3", 
            "lat": round(bbox["south"], 6), 
            "lon": round(lon_mid, 6),
            "weight": cardinal_weight, 
            "desc": "Lower South"
        },
        {
            "id": "P4", 
            "lat": round(lat_mid, 6), 
            "lon": round(bbox["east"], 6),
            "weight": diagonal_weight, 
            "desc": "East Side"
        },
        {
            "id": "P5", 
            "lat": round(lat_mid, 6), 
            "lon": round(bbox["west"], 6),
            "weight": diagonal_weight, 
            "desc": "West Side"
        },
    ]

    logger.info("Generated %d grid points for bbox "
                "(N=%.2f, S=%.2f, E=%.2f, W=%.2f)",
                len(points), bbox["north"], bbox["south"],
                bbox["east"], bbox["west"])

    for pt in points:
        logger.debug("  %s: (%.4f, %.4f) weight=%.2f — %s",
                     pt["id"], pt["lat"], pt["lon"], 
                     pt["weight"], pt["desc"])

    return points
