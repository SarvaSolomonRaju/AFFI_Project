"""Reference flood maps — one labeled, contextual map per return period.

The raw depth GeoTIFF download is just a colored grid: no streets, no
buildings, no names, no context. This turns it into a real map anyone can
read: named streets, real building footprints, named critical facilities
always labeled, the creek, a legend, a scale bar, and a north arrow. Modeled
on FEMA's own FIRM-panel convention (white ground, blue water, gray roads)
since that's the most familiar cartographic language to a flood manager.

IMPORTANT, verified directly against the data before choosing how to color
buildings: in this pilot's library, the flood EXTENT is built once from a
fixed FEMA AE-zone polygon and only the DEPTH is scaled per return period
(Leopold b=0.4 — see data/flood_library_real/manifest.json). Checked across
all 1345 buildings: 505 are inside the flood footprint at the 5-yr event
and 530 at the 200-yr event — almost the same SET of buildings at every
size. What actually changes is depth (mean 0.32m at 5-yr -> 0.51m at
200-yr, max 8.0m -> 12.7m). A binary red/gray map would make every return
period look identical and read as broken. Buildings and roads are instead
colored by a depth ramp (pale -> dark red) on a FIXED scale shared across
all six maps, so a 5-yr map genuinely looks lighter than a 200-yr map, and
the subtitle says plainly why the affected area looks similar while the
color deepens.

Flood status per building/road/facility comes from `depth_by_rp`
(scripts/16_tag_return_periods.py) — already computed, no raster resampling
needed here. The blue water fill is the REAL reprojected depth raster
(outputs/sim/depth_T{rp}yr.png, src/probabilistic/scenarios.py) drawn
under the vector layers, so the water shown is the actual model output,
not an approximation.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.patches import Polygon as MplPolygon
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image

from common.paths import DATA_DIR, OUTPUTS_DIR
from common.building_categories import categorize_building

LOCAL = DATA_DIR / "local_assets"
SIM_DIR = OUTPUTS_DIR / "sim"
OUT_DIR = OUTPUTS_DIR / "reference_maps"

DEPTH_THRESHOLD_M = 0.05  # matches routes_map.py's _DEPTH_THRESHOLD_M

CATEGORY_COLOR = {
    "School": "#9b59b6",
    "Public/Civic": "#3498db",
    "Residential": "#90a4ae",
    "Commercial/Industrial": "#f39c12",
    "Agricultural/Outbuilding": "#8d6e63",
    "Unclassified": "#b0bec8",
}
ROAD_GRAY = "#546575"
CREEK_BLUE = "#1f6f9e"

# Depth color ramp — FIXED across all six return-period maps so a 5-yr map
# is genuinely pale and a 200-yr map is genuinely dark, not an arbitrary
# per-map rescale that would make every map look the same severity.
#
# Ceiling is 3.5 m, NOT the library's full depth range: checked the actual
# building depth distribution first — 95% of flooded buildings are under
# 1.53 m at even the 100-yr event, with a small number (~1%) of extreme
# values up to 12.7 m for buildings sitting right at the creek-channel edge
# (a BFE/DEM edge artifact, not a realistic building depth). A 0-13m scale
# built for those outliers crushed the entire meaningful 0-1.5m range into
# one indistinguishable pale shade -- exactly the "can't see any difference"
# failure this ramp exists to fix. 3.5 m already exceeds "over an adult's
# head" (the life-safety framing used elsewhere in this dashboard); anything
# beyond it clips to the same full dark red rather than distorting the
# rest of the scale.
_DEPTH_CMAP = mcolors.LinearSegmentedColormap.from_list(
    "flood_depth", ["#fbdcd6", "#f0a898", "#df6f5c", "#c0392b", "#7a1f18"])
_DEPTH_MAX_M = 3.5
_DEPTH_NORM = mcolors.Normalize(vmin=0.0, vmax=_DEPTH_MAX_M, clip=True)


def _depth_color(depth_m: float) -> str:
    return mcolors.to_hex(_DEPTH_CMAP(_DEPTH_NORM(depth_m)))


def _m_to_ft(m: float) -> float:
    return m * 3.28084

INFRA_MARKER = {
    "shelter": ("s", "#2e7d32"), "hospital": ("P", "#c0392b"),
    "fire_station": ("^", "#d35400"), "police": ("^", "#1a5276"),
    "water_supply": ("o", "#0e6ba8"), "wastewater": ("o", "#5d6d7e"),
    "power": ("*", "#b7950b"), "public_works": ("D", "#616a6b"),
    "government": ("h", "#283593"), "post_office": ("p", "#616a6b"),
    "mine": ("X", "#6d4c41"),
}

_M_PER_DEG_LAT = 111_320.0
_TOWN_LAT = 31.5407  # Patagonia pour point, for the deg->m scale-bar conversion
_TOWN_LON = -110.7521
_TOWN_RADIUS_M = 950.0  # frames the actual developed grid; see module docstring below


def _load(name: str) -> dict:
    p = LOCAL / name
    return json.loads(p.read_text()) if p.exists() else {"features": []}


def _bounds() -> dict:
    return json.loads((OUTPUTS_DIR / "_map_layer_bounds.json").read_text())["fema-100yr"]


def _town_bbox(pad_frac: float = 0.12) -> tuple[float, float, float, float]:
    """Fixed crop around the actual developed town grid, not a density guess
    over the full building set. Tried percentile-trimming the building
    coordinates first — it doesn't work here: only 57% of buildings (772 of
    1345) sit within 900m of the town center; the rest are genuinely
    scattered ranch/agricultural structures across the HUC-12, spread over
    several km, so ANY statistic computed from the full set (percentile,
    median+percentile-radius) gets pulled wide by them and crushes the real
    downtown grid into a small illegible corner. A flood REFERENCE map for
    the town has to mean the town — fixed center + radius, verified against
    the actual building density, not derived from a spread that includes
    the rural outliers by construction.
    """
    m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians(_TOWN_LAT))
    r_lon = _TOWN_RADIUS_M / m_per_deg_lon
    r_lat = _TOWN_RADIUS_M / _M_PER_DEG_LAT
    r_lon *= 1 + pad_frac
    r_lat *= 1 + pad_frac
    return _TOWN_LON - r_lon, _TOWN_LON + r_lon, _TOWN_LAT - r_lat, _TOWN_LAT + r_lat


def render_reference_map(return_period: int, out_path: Path) -> Path:
    rp_key = str(return_period)
    roads = _load("roads_huc12.geojson")
    buildings = _load("buildings_huc12.geojson")
    infra = _load("infrastructure.geojson")
    creek_path = DATA_DIR / "fema_fis" / "WaterLn_huc12.geojson"
    creek = json.loads(creek_path.read_text()) if creek_path.exists() else {"features": []}

    bbox_w, bbox_e, bbox_s, bbox_n = _town_bbox()
    m_per_deg_lon = _M_PER_DEG_LAT * math.cos(math.radians(_TOWN_LAT))

    fig, ax = plt.subplots(figsize=(15, 14), dpi=180)
    ax.set_facecolor("#fbfaf6")
    # Axis limits fixed BEFORE anything is drawn so ax.transData is stable —
    # the label-collision check below needs real screen-pixel distances.
    ax.set_xlim(bbox_w, bbox_e)
    ax.set_ylim(bbox_s, bbox_n)
    ax.set_aspect(1 / math.cos(math.radians(_TOWN_LAT)))

    # Greedy label placer: skips a label if it would land within min_px of an
    # already-placed one. Without this, a small town's worth of named
    # buildings + facilities packed into one frame turns into stacked,
    # unreadable text — the exact "not useful, can't read anything" failure
    # a first pass at this map had.
    placed_px: list[tuple[float, float]] = []

    def place_label(x: float, y: float, text: str, min_px: float, **kwargs) -> bool:
        if not (bbox_w <= x <= bbox_e and bbox_s <= y <= bbox_n):
            return False
        px, py = ax.transData.transform((x, y))
        for ox, oy in placed_px:
            if math.hypot(px - ox, py - oy) < min_px:
                return False
        placed_px.append((px, py))
        ax.annotate(text, xy=(x, y), zorder=7,
                    path_effects=[pe.withStroke(linewidth=2, foreground="white")], **kwargs)
        return True

    # Flood water — the real reprojected depth raster for this scenario,
    # drawn under every vector layer so what's shown is actual model output.
    raster_path = SIM_DIR / f"depth_T{return_period:03d}yr.png"
    if raster_path.exists():
        b = _bounds()
        img = np.asarray(Image.open(raster_path))
        ax.imshow(img, extent=[b["west"], b["east"], b["south"], b["north"]], zorder=1, interpolation="bilinear")

    # Roads — colored by actual depth at THIS return period (see module
    # docstring: extent barely changes across return periods here, depth
    # does, so depth is what the color must carry).
    for f in roads["features"]:
        coords = f["geometry"]["coordinates"]
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        depth = (f["properties"].get("depth_by_rp") or {}).get(rp_key, 0.0)
        flooded = depth > DEPTH_THRESHOLD_M
        ax.plot(xs, ys, color=_depth_color(depth) if flooded else ROAD_GRAY,
                linewidth=2.6 if flooded else 1.1, zorder=3, solid_capstyle="round",
                alpha=0.95 if flooded else 0.8)

    # Creek centerline
    for f in creek["features"]:
        geom = f["geometry"]
        coords = geom["coordinates"]
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        ax.plot(xs, ys, color=CREEK_BLUE, linewidth=1.6, zorder=2, alpha=0.9)

    # Buildings — real OSM footprints. Colored by category when dry; colored
    # by ACTUAL DEPTH at this return period when flooded (see module
    # docstring — this is what makes a 5-yr map look different from a
    # 200-yr map, since the affected building SET is nearly identical).
    for f in buildings["features"]:
        depth = (f["properties"].get("depth_by_rp") or {}).get(rp_key, 0.0)
        flooded = depth > DEPTH_THRESHOLD_M
        cat = categorize_building(f["properties"].get("building"))
        color = _depth_color(depth) if flooded else CATEGORY_COLOR.get(cat, CATEGORY_COLOR["Unclassified"])
        ring = f["geometry"]["coordinates"][0]
        poly = MplPolygon(ring, closed=True, facecolor=color,
                           edgecolor="#5a1712" if flooded else "none",
                           linewidth=0.6 if flooded else 0,
                           alpha=0.94 if flooded else 0.78, zorder=4)
        ax.add_patch(poly)

    # Critical infrastructure placed FIRST in the label queue — only 16 of
    # these, always labeled by name WITH depth in feet when flooded, so the
    # specific number a manager needs is right on the map, not just a color.
    for f in infra["features"]:
        depth = (f["properties"].get("depth_by_rp") or {}).get(rp_key, 0.0)
        flooded = depth > DEPTH_THRESHOLD_M
        cat = f["properties"].get("category", "")
        marker, base_color = INFRA_MARKER.get(cat, ("o", "#616a6b"))
        lon, lat = f["geometry"]["coordinates"]
        if not (bbox_w <= lon <= bbox_e and bbox_s <= lat <= bbox_n):
            continue
        ax.scatter([lon], [lat], marker=marker, s=110, color=_depth_color(depth) if flooded else base_color,
                   edgecolor="white", linewidth=1.2, zorder=8)
        name = f["properties"].get("name", "")
        label = f"{name}  ({_m_to_ft(depth):.1f} ft)" if flooded else name
        px, py = ax.transData.transform((lon, lat))
        placed_px.append((px, py))  # marker itself reserves space regardless of label success
        ax.annotate(label, xy=(lon, lat), xytext=(6, 6), textcoords="offset points",
                    fontsize=7.2, fontweight="bold", color="#1a1a1a", zorder=9,
                    path_effects=[pe.withStroke(linewidth=2.4, foreground="white")])

    # Named buildings — labeled only where there's room; closest-to-center
    # (i.e., most likely to matter) get first pick since dict order follows
    # the source file, so sort by distance from the town center first.
    town_cx, town_cy = (bbox_w + bbox_e) / 2, (bbox_s + bbox_n) / 2
    named = []
    for f in buildings["features"]:
        name = f["properties"].get("name")
        if not isinstance(name, str) or name.lower() in ("nan", "none", ""):
            continue
        ring = f["geometry"]["coordinates"][0]
        cx = sum(c[0] for c in ring) / len(ring)
        cy = sum(c[1] for c in ring) / len(ring)
        named.append((math.hypot(cx - town_cx, cy - town_cy), cx, cy, name))
    named.sort(key=lambda t: t[0])
    for _, cx, cy, name in named:
        place_label(cx, cy, name, min_px=32, fontsize=6.4, ha="center", va="center", color="#1a1a1a")

    # Named major roads labeled once each, lowest priority (most space,
    # least specific to one structure) — this is what makes the map read as
    # an actual place instead of an abstract shape.
    seen_names: set[str] = set()
    for f in roads["features"]:
        name = f["properties"].get("name")
        hw = f["properties"].get("highway")
        if not isinstance(name, str) or name.lower() in ("nan", "none", "") or name in seen_names:
            continue
        if hw not in ("primary", "secondary", "tertiary"):
            continue
        coords = f["geometry"]["coordinates"]
        mid = coords[len(coords) // 2]
        seen_names.add(name)
        place_label(mid[0], mid[1], name, min_px=60, fontsize=7, color="#2c3e50", ha="center", style="italic")

    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#2c3e50")
        spine.set_linewidth(1.2)

    fig.suptitle(f"Upper Sonoita Creek — {return_period}-Year Flood Reference Map",
                 fontsize=16, fontweight="bold", y=0.965)
    ax.set_title(
        f"Patagonia, AZ  ·  the same general area is at risk at every event size in this method — "
        f"darker red = deeper water at the {return_period}-yr event\n"
        f"Source: FEMA NFHL/BFE + USGS 3DEP + OpenStreetMap",
        fontsize=9.3, color="#43535f", pad=10)

    legend_handles = [
        Line2D([0], [0], marker="s", color="w", markerfacecolor=_depth_color(0.3), markersize=11, label="Shallow flood water"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=_depth_color(6.0), markersize=11, label="Deep flood water"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=CATEGORY_COLOR["Residential"], markersize=11, label="Building — not flooded"),
        Line2D([0], [0], color=ROAD_GRAY, linewidth=1.1, label="Road — open"),
        Line2D([0], [0], color=CREEK_BLUE, linewidth=1.6, label="Sonoita Creek"),
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=8, framealpha=0.94,
              facecolor="white", edgecolor="#c3c2b7", title="Darker = deeper", title_fontsize=8)

    # Depth colorbar — the real legend for the ramp above (a couple of fixed
    # swatches can't convey a continuous scale on their own).
    cax = fig.add_axes([0.70, 0.085, 0.16, 0.018])
    cb = fig.colorbar(cm.ScalarMappable(norm=_DEPTH_NORM, cmap=_DEPTH_CMAP), cax=cax, orientation="horizontal")
    cb.set_label("Flood depth (m) at this event", fontsize=7.5, color="#2c3e50")
    cb.ax.tick_params(labelsize=6.5, color="#2c3e50", labelcolor="#2c3e50")

    # Scale bar — real meters, from the local deg->m conversion at this latitude.
    bar_m = 500 if (bbox_e - bbox_w) * m_per_deg_lon < 4000 else 1000
    bar_deg = bar_m / m_per_deg_lon
    bx0 = bbox_e - (bbox_e - bbox_w) * 0.22
    by0 = bbox_s + (bbox_n - bbox_s) * 0.04
    ax.plot([bx0, bx0 + bar_deg], [by0, by0], color="#1a1a1a", linewidth=3, zorder=9, solid_capstyle="butt")
    ax.annotate(f"{bar_m} m", xy=(bx0 + bar_deg / 2, by0), xytext=(0, 5), textcoords="offset points",
                ha="center", fontsize=8, fontweight="bold")

    # North arrow
    nx = bbox_w + (bbox_e - bbox_w) * 0.05
    ny0 = bbox_s + (bbox_n - bbox_s) * 0.10
    ny1 = ny0 + (bbox_n - bbox_s) * 0.07
    ax.annotate("", xy=(nx, ny1), xytext=(nx, ny0),
                arrowprops=dict(arrowstyle="-|>", color="#1a1a1a", linewidth=2))
    ax.annotate("N", xy=(nx, ny1), xytext=(0, 3), textcoords="offset points",
                ha="center", fontsize=9, fontweight="bold")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return out_path


def build_all_reference_maps(return_periods=(5, 10, 25, 50, 100, 200)) -> dict[int, Path]:
    return {rp: render_reference_map(rp, OUT_DIR / f"flood_reference_map_{rp}yr.png") for rp in return_periods}
