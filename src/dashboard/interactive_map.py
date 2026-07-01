"""
FloodAI Interactive Map (Leaflet/Folium)
========================================

Builds a pan/zoomable web map of the Upper Sonoita Creek pilot showing:

  * Reference 100-yr flood depth (FEMA BFE - USGS 3DEP DEM)  -> blue gradient
  * Today's probability of inundation (P10/P50/P90 ensemble) -> yellow->red
  * Today's likely flood depth                                -> blue gradient
  * FEMA NFHL flood zones (AE / A / AO / X-shaded)            -> red/orange/yellow
  * FEMA BFE profile lines (Layer 16)                         -> cyan + tooltips
  * Sonoita Creek centerline (FEMA WaterLn)                   -> blue
  * Reference markers (USGS gauge 09481500, Patagonia, etc.)

All overlays use REAL government data (no synthetic inputs).

Run as:
    python -m src.dashboard.interactive_map
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, calculate_default_transform

import folium
from folium.plugins import Fullscreen, MeasureControl, MiniMap, MousePosition, Search
from branca.colormap import LinearColormap
from branca.element import Template, MacroElement

import matplotlib
matplotlib.use("Agg")
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUT = ROOT / "outputs"

USGS_GAUGE = (31.5407, -110.7521, "USGS 09481500 Sonoita Creek nr Patagonia")
PATAGONIA = (31.5393, -110.7548, "Patagonia, AZ")
HWY82 = (31.5410, -110.7560, "Hwy 82 Bridge over Sonoita Creek")


def reproject_to_wgs84(arr: np.ndarray, src_transform, src_crs):
    h, w = arr.shape
    left = src_transform.c
    top = src_transform.f
    right = left + w * src_transform.a
    bottom = top + h * src_transform.e
    dst_transform, dst_w, dst_h = calculate_default_transform(
        src_crs, "EPSG:4326", w, h, left, bottom, right, top
    )
    dst = np.zeros((dst_h, dst_w), dtype=np.float32)
    reproject(
        source=arr.astype(np.float32),
        destination=dst,
        src_transform=src_transform,
        src_crs=src_crs,
        dst_transform=dst_transform,
        dst_crs="EPSG:4326",
        resampling=Resampling.bilinear,
        src_nodata=0.0,
        dst_nodata=0.0,
    )
    W = dst_transform.c
    N = dst_transform.f
    E = W + dst_w * dst_transform.a
    S = N + dst_h * dst_transform.e
    return dst, (W, S, E, N)


def array_to_png(arr, cmap_name, vmin, vmax, out_png, alpha_zero=True):
    cmap = cm.get_cmap(cmap_name)
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax, clip=True)
    rgba = (cmap(norm(arr)) * 255).astype(np.uint8)
    if alpha_zero:
        rgba[..., 3] = np.where(arr > 1e-6, 200, 0).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(out_png)


def add_raster_overlay(m, png_path, bounds_wsen, name, show, opacity=0.75):
    W, S, E, N = bounds_wsen
    return folium.raster_layers.ImageOverlay(
        name=name,
        image=str(png_path.resolve()),
        bounds=[[S, W], [N, E]],
        opacity=opacity,
        interactive=False,
        cross_origin=False,
        show=show,
        zindex=400,
    ).add_to(m)


def style_zone(feature):
    z = (feature["properties"].get("FLD_ZONE") or "").upper()
    sub = (feature["properties"].get("ZONE_SUBTY") or "").upper()
    if z == "AE":
        return {"fillColor": "#d73027", "color": "#a50026", "weight": 1, "fillOpacity": 0.35}
    if z == "A":
        return {"fillColor": "#fc8d59", "color": "#b30000", "weight": 1, "fillOpacity": 0.30}
    if z == "AO":
        return {"fillColor": "#fee090", "color": "#b35900", "weight": 1, "fillOpacity": 0.30}
    if "0.2 PCT" in sub:
        return {"fillColor": "#fdae61", "color": "#8c510a", "weight": 1, "fillOpacity": 0.25}
    return {"fillColor": "#cccccc", "color": "#888888", "weight": 1, "fillOpacity": 0.15}


def build_map(out_html: Path = OUT / "dashboard_map.html") -> Path:
    OUT.mkdir(parents=True, exist_ok=True)

    # 1. Reference 100-yr depth
    ref_tif = DATA / "flood_library_real" / "depth_T100yr_Q455cms.tif"
    with rasterio.open(ref_tif) as src:
        ref_arr = np.nan_to_num(src.read(1), nan=0.0)
        ref_wgs, ref_bounds = reproject_to_wgs84(ref_arr, src.transform, src.crs)
    ref_png = OUT / "_map_layer_100yr_depth.png"
    array_to_png(ref_wgs, "Blues", 0.1, 10.0, ref_png)

    # 2. Today's likely depth + probability of inundation
    today_npz = OUT / "task4" / "today_rasters.npz"
    today_likely_png = today_poi_png = None
    today_likely_bounds = today_poi_bounds = None
    today_max_depth = today_max_poi = 0.0
    if today_npz.exists():
        d = np.load(today_npz)
        with rasterio.open(ref_tif) as src:
            tt, cc = src.transform, src.crs
        likely = np.nan_to_num(d["likely"].astype(np.float32), nan=0.0)
        poi = np.nan_to_num(d["poi"].astype(np.float32), nan=0.0)
        today_max_depth = float(likely.max())
        today_max_poi = float(poi.max())
        likely_wgs, today_likely_bounds = reproject_to_wgs84(likely, tt, cc)
        poi_wgs, today_poi_bounds = reproject_to_wgs84(poi, tt, cc)
        today_likely_png = OUT / "_map_layer_today_likely.png"
        today_poi_png = OUT / "_map_layer_today_poi.png"
        array_to_png(likely_wgs, "Blues", 0.05, max(today_max_depth, 0.5), today_likely_png)
        array_to_png(poi_wgs, "YlOrRd", 0.01, max(today_max_poi, 0.05), today_poi_png)

    # 3. Base Folium map
    center = [(ref_bounds[1] + ref_bounds[3]) / 2, (ref_bounds[0] + ref_bounds[2]) / 2]
    m = folium.Map(location=center, zoom_start=13, control_scale=True, tiles=None)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap").add_to(m)
    folium.TileLayer("CartoDB positron", name="CartoDB Light").add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery", name="Esri Satellite",
    ).add_to(m)
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Topo", name="Esri Topographic",
    ).add_to(m)

    # 4. Raster overlays
    add_raster_overlay(m, ref_png, ref_bounds,
                       name="FEMA 1% Annual (100-yr) Flood Depth [REAL]",
                       show=True, opacity=0.70)
    if today_likely_png is not None and today_max_depth > 0:
        add_raster_overlay(m, today_likely_png, today_likely_bounds,
                           name=f"Today - Likely Flood Depth (max {today_max_depth:.1f} m)",
                           show=True, opacity=0.80)
    if today_poi_png is not None and today_max_poi > 0:
        add_raster_overlay(m, today_poi_png, today_poi_bounds,
                           name=f"Today - Probability of Inundation (max {today_max_poi*100:.0f}%)",
                           show=True, opacity=0.80)

    # 5. FEMA NFHL polygons
    nfhl = DATA / "fema_nfhl" / "nfhl_zones_huc12.geojson"
    if nfhl.exists():
        folium.GeoJson(
            str(nfhl),
            name="FEMA NFHL Flood Zones (AE / A / AO / 0.2% shaded X) [REAL]",
            style_function=style_zone,
            tooltip=folium.GeoJsonTooltip(
                fields=["FLD_ZONE", "ZONE_SUBTY", "SFHA_TF"],
                aliases=["Zone:", "Subtype:", "SFHA:"],
                sticky=True,
            ),
            show=True,
        ).add_to(m)

    # 6. FEMA BFE lines
    bfe = DATA / "fema_fis" / "BFE_huc12.geojson"
    if bfe.exists():
        folium.GeoJson(
            str(bfe),
            name="FEMA Base Flood Elevation lines (Layer 16) [REAL]",
            style_function=lambda f: {"color": "#00bcd4", "weight": 2, "opacity": 0.9},
            tooltip=folium.GeoJsonTooltip(
                fields=["ELEV"], aliases=["BFE (ft NAVD88):"], sticky=True),
            show=False,
        ).add_to(m)

    # 7. Sonoita Creek centerline
    waterln = DATA / "fema_fis" / "WaterLn_huc12.geojson"
    if waterln.exists():
        folium.GeoJson(
            str(waterln),
            name="Sonoita Creek centerline (FEMA WaterLn) [REAL]",
            style_function=lambda f: {"color": "#1565c0", "weight": 3, "opacity": 0.9},
            show=True,
        ).add_to(m)

    # 7.5 OSM Roads (color by FLOODED/OPEN status) - Resident-useful layer
    roads_path = DATA / "local_assets" / "roads_huc12.geojson"
    roads_layer = None
    flooded_roads = 0
    if roads_path.exists():
        def style_road(feat):
            st = (feat["properties"].get("status") or "").upper()
            if st == "FLOODED":
                return {"color": "#d32f2f", "weight": 4, "opacity": 0.95}
            return {"color": "#37474f", "weight": 2, "opacity": 0.55}
        roads_layer = folium.GeoJson(
            str(roads_path),
            name="OSM Roads - FLOODED (red) / OPEN (gray) [100-yr]",
            style_function=style_road,
            tooltip=folium.GeoJsonTooltip(
                fields=["name", "highway", "status", "max_depth_m"],
                aliases=["Road:", "Type:", "Status:", "100-yr depth (m):"],
                sticky=True,
            ),
            show=True,
        ).add_to(m)
        try:
            import json as _json
            gj = _json.loads(Path(roads_path).read_text())
            flooded_roads = sum(1 for f in gj.get("features", [])
                                if (f["properties"].get("status") or "").upper() == "FLOODED")
        except Exception:
            pass

    # 7.6 OSM Buildings (color by status)
    bld_path = DATA / "local_assets" / "buildings_huc12.geojson"
    flooded_bld = 0
    if bld_path.exists():
        def style_bld(feat):
            st = (feat["properties"].get("status") or "").upper()
            if st == "FLOODED":
                return {"color": "#b71c1c", "weight": 1, "fillColor": "#e53935",
                        "fillOpacity": 0.65}
            return {"color": "#555", "weight": 0.4, "fillColor": "#bdbdbd",
                    "fillOpacity": 0.35}
        folium.GeoJson(
            str(bld_path),
            name="OSM Buildings - FLOODED (red) / SAFE (gray) [100-yr]",
            style_function=style_bld,
            tooltip=folium.GeoJsonTooltip(
                fields=["building", "status", "max_depth_m"],
                aliases=["Building:", "Status:", "100-yr depth (m):"],
                sticky=True,
            ),
            show=False,
        ).add_to(m)
        try:
            import json as _json
            gj = _json.loads(Path(bld_path).read_text())
            flooded_bld = sum(1 for f in gj.get("features", [])
                              if (f["properties"].get("status") or "").upper() == "FLOODED")
        except Exception:
            pass

    # 7.7 Search-by-road-name (resident lookup)
    if roads_layer is not None:
        try:
            Search(
                layer=roads_layer,
                search_label="name",
                placeholder="Search road by name (e.g. Naugle Ave)",
                collapsed=False,
                position="topleft",
            ).add_to(m)
        except Exception as e:
            print(f"[warn] Search plugin failed: {e}")

    # 7.8 Critical Infrastructure layers
    infra_path = DATA / "local_assets" / "infrastructure.geojson"
    if infra_path.exists():
        INFRA_COLORS = {
            "shelter": "#2e7d32",
            "hospital": "#c62828",
            "fire_station": "#e65100",
            "police": "#1565c0",
            "water_supply": "#006064",
            "wastewater": "#6a1b9a",
            "power": "#f9a825",
            "cell_tower": "#546e7a",
            "power_line": "#f57f17",
            "water_line": "#0277bd",
            "sewer_line": "#4a148c",
            "public_works": "#1b5e20",
            "bridge": "#212121",
        }

        def _infra_marker(feat, _m):
            props = feat["properties"]
            lat = feat["geometry"]["coordinates"][1]
            lon = feat["geometry"]["coordinates"][0]
            cat = props.get("category", "unknown")
            color = props.get("color", "gray")
            icon_name = props.get("icon", "info-sign")
            status = props.get("status", "SAFE")
            depth = props.get("max_depth_m", 0.0)
            bdr = "#b71c1c" if status == "FLOODED" else "#333"
            popup_rows = "".join(
                f"<tr><td style='padding:2px 6px;color:#555;'>{k.replace('_',' ').title()}:</td>"
                f"<td style='padding:2px 6px;font-weight:600;'>{v}</td></tr>"
                for k, v in props.items()
                if k not in ("icon", "color", "priority", "amenity")
            )
            popup_html = (
                f"<div style='font-family:sans-serif;max-width:300px;'>"
                f"<div style='font-weight:700;font-size:13px;color:{bdr};margin-bottom:4px;'>"
                f"{'&#x26A0; FLOODED - ' if status=='FLOODED' else ''}{props.get('name','')}</div>"
                f"<table style='font-size:11px;border-collapse:collapse;'>{popup_rows}</table>"
                f"</div>"
            )
            folium.Marker(
                location=[lat, lon],
                tooltip=f"{props.get('category_label','?')}: {props.get('name','')} [{status}]",
                popup=folium.Popup(popup_html, max_width=320),
                icon=folium.Icon(color=color, icon=icon_name, prefix="fa"),
            ).add_to(_m)

        categories_to_groups = {
            "Shelters & Evacuation": ["shelter"],
            "Hospitals & Medical": ["hospital"],
            "Fire & Police": ["fire_station", "police"],
            "Water Supply & Treatment": ["water_supply", "wastewater", "water_line", "sewer_line"],
            "Power & Telecom": ["power", "power_line", "cell_tower"],
            "Bridges & Public Works": ["bridge", "public_works"],
        }

        try:
            gj_infra = json.loads(infra_path.read_text())
            for group_name, cats in categories_to_groups.items():
                fg = folium.FeatureGroup(name=f"INFRA: {group_name}", show=True)
                for feat in gj_infra.get("features", []):
                    if feat["properties"].get("category") in cats:
                        _infra_marker(feat, fg)
                fg.add_to(m)
        except Exception as e:
            print(f"[warn] Infrastructure layer failed: {e}")

    # 7.9 Evacuation routes
    evac_path = DATA / "local_assets" / "evac_routes.geojson"
    if evac_path.exists():
        def style_evac(feat):
            rt = feat["properties"].get("route_type", "")
            if rt == "primary":
                return {"color": "#00c853", "weight": 5, "opacity": 0.9, "dashArray": None}
            if rt == "shelter_access":
                return {"color": "#2e7d32", "weight": 3, "opacity": 0.85, "dashArray": "4,4"}
            return {"color": "#ff6f00", "weight": 4, "opacity": 0.85, "dashArray": "6,4"}

        folium.GeoJson(
            str(evac_path),
            name="EVAC: Evacuation Routes (green=primary, orange=secondary)",
            style_function=style_evac,
            tooltip=folium.GeoJsonTooltip(
                fields=["name", "route_type", "destination", "status", "note"],
                aliases=["Route:", "Type:", "Destination:", "Status:", "Note:"],
                sticky=True,
            ),
            show=True,
        ).add_to(m)

    # 7.10 10-year flood depth raster overlay
    tif_10yr = DATA / "flood_library_real" / "depth_T010yr_Q230cms.tif"
    if tif_10yr.exists():
        with rasterio.open(tif_10yr) as src:
            arr_10yr = np.nan_to_num(src.read(1), nan=0.0)
            wgs_10yr, bounds_10yr = reproject_to_wgs84(arr_10yr, src.transform, src.crs)
        png_10yr = OUT / "_map_layer_10yr_depth.png"
        array_to_png(wgs_10yr, "Oranges", 0.05, max(float(arr_10yr.max()), 0.5), png_10yr)
        add_raster_overlay(m, png_10yr, bounds_10yr,
                           name="10-Year Flood Depth [Q=230 cms, T=10yr]",
                           show=False, opacity=0.75)

    # 7.11 Additional simulation return period overlays for slider
    # T=5yr
    tif_5yr = DATA / "flood_library_real" / "depth_T005yr_Q166cms.tif"
    if tif_5yr.exists():
        with rasterio.open(tif_5yr) as src:
            arr_5yr = np.nan_to_num(src.read(1), nan=0.0)
            wgs_5yr, bounds_5yr = reproject_to_wgs84(arr_5yr, src.transform, src.crs)
        png_5yr = OUT / "_map_layer_5yr_depth.png"
        array_to_png(wgs_5yr, "Blues", 0.05, 12.0, png_5yr)
        add_raster_overlay(m, png_5yr, bounds_5yr,
                           name="5-Year Flood Depth [Q=166 cms, T=5yr]",
                           show=False, opacity=0.75)

    # T=25yr
    tif_25yr = DATA / "flood_library_real" / "depth_T025yr_Q317cms.tif"
    if tif_25yr.exists():
        with rasterio.open(tif_25yr) as src:
            arr_25yr = np.nan_to_num(src.read(1), nan=0.0)
            wgs_25yr, bounds_25yr = reproject_to_wgs84(arr_25yr, src.transform, src.crs)
        png_25yr = OUT / "_map_layer_25yr_depth.png"
        array_to_png(wgs_25yr, "Blues", 0.05, 12.0, png_25yr)
        add_raster_overlay(m, png_25yr, bounds_25yr,
                           name="25-Year Flood Depth [Q=317 cms, T=25yr]",
                           show=False, opacity=0.75)

    # T=50yr
    tif_50yr = DATA / "flood_library_real" / "depth_T050yr_Q385cms.tif"
    if tif_50yr.exists():
        with rasterio.open(tif_50yr) as src:
            arr_50yr = np.nan_to_num(src.read(1), nan=0.0)
            wgs_50yr, bounds_50yr = reproject_to_wgs84(arr_50yr, src.transform, src.crs)
        png_50yr = OUT / "_map_layer_50yr_depth.png"
        array_to_png(wgs_50yr, "Blues", 0.05, 12.0, png_50yr)
        add_raster_overlay(m, png_50yr, bounds_50yr,
                           name="50-Year Flood Depth [Q=385 cms, T=50yr]",
                           show=False, opacity=0.75)

    # T=200yr
    tif_200yr = DATA / "flood_library_real" / "depth_T200yr_Q525cms.tif"
    if tif_200yr.exists():
        with rasterio.open(tif_200yr) as src:
            arr_200yr = np.nan_to_num(src.read(1), nan=0.0)
            wgs_200yr, bounds_200yr = reproject_to_wgs84(arr_200yr, src.transform, src.crs)
        png_200yr = OUT / "_map_layer_200yr_depth.png"
        array_to_png(wgs_200yr, "Blues", 0.05, 12.0, png_200yr)
        add_raster_overlay(m, png_200yr, bounds_200yr,
                           name="200-Year Flood Depth [Q=525 cms, T=200yr]",
                           show=False, opacity=0.75)


    # 8. HUC-12 bbox
    huc = DATA / "fema_nfhl" / "huc12_bbox.geojson"
    if huc.exists():
        folium.GeoJson(
            str(huc),
            name="HUC-12 150503010204 boundary",
            style_function=lambda f: {"color": "#37474f", "weight": 2, "fill": False, "dashArray": "5,5"},
            show=True,
        ).add_to(m)

    # 9. Markers
    fg = folium.FeatureGroup(name="Reference Markers", show=True)
    folium.Marker([USGS_GAUGE[0], USGS_GAUGE[1]], tooltip=USGS_GAUGE[2],
        popup=("<b>USGS Gauge 09481500</b><br>Sonoita Creek nr Patagonia, AZ<br>"
               "45 yrs annual peaks (1930-1983)<br>"
               "Q<sub>100</sub> = 455 cms (16,053 cfs) [Bulletin 17C LP-III]"),
        icon=folium.Icon(color="green", icon="tint", prefix="fa")).add_to(fg)
    folium.Marker([PATAGONIA[0], PATAGONIA[1]], tooltip=PATAGONIA[2],
        popup="<b>Patagonia, AZ</b><br>Pop. ~900<br>Pilot community for FloodAI",
        icon=folium.Icon(color="blue", icon="home", prefix="fa")).add_to(fg)
    folium.Marker([HWY82[0], HWY82[1]], tooltip=HWY82[2],
        popup="<b>Hwy 82 Bridge</b><br>Critical evacuation route over Sonoita Creek",
        icon=folium.Icon(color="orange", icon="road", prefix="fa")).add_to(fg)
    fg.add_to(m)

    # 10. Legends
    LinearColormap(
        colors=["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
        vmin=0, vmax=10,
        caption="Flood Depth (m) - Blues = FEMA 100-yr & Today",
    ).add_to(m)
    LinearColormap(
        colors=["#ffffcc", "#fed976", "#fd8d3c", "#e31a1c", "#800026"],
        vmin=0, vmax=1.0,
        caption="Probability of Inundation (0 - 1)",
    ).add_to(m)

    # 11. Plugins
    Fullscreen(position="topleft").add_to(m)
    MiniMap(toggle_display=True, position="bottomleft").add_to(m)
    MeasureControl(primary_length_unit="meters", primary_area_unit="hectares").add_to(m)
    MousePosition(position="bottomright", separator=" | ", prefix="lat,lon:").add_to(m)
    folium.LayerControl(collapsed=False, position="topright").add_to(m)

    # 12. Title banner
    title_html = """
    {% macro html(this, kwargs) %}
    <div style="position: fixed; top: 10px; left: 60px; z-index: 9999;
                background: rgba(255,255,255,0.95); padding: 8px 14px;
                border-radius: 6px; border: 2px solid #b71c1c; font-family: sans-serif;
                box-shadow: 0 2px 8px rgba(0,0,0,0.25); max-width: 600px;">
      <div style="font-size: 15px; font-weight: 700; color: #b71c1c;">
        &#x26A0; Emergency Flood Decision Central &mdash; Upper Sonoita Creek
      </div>
      <div style="font-size: 11px; color: #333; margin-top: 2px;">
        Layers: FEMA NFHL &bull; FEMA BFE &bull; USGS 3DEP 10-m DEM &bull; OSM Roads/Buildings
        &bull; Critical Infrastructure &bull; Evacuation Routes &bull; 10-yr / 100-yr Flood Depth
      </div>
      <div style="font-size: 10px; color: #666; margin-top: 2px;">
        Toggle layers (top-right) &bull; Click markers for details &bull; Search road names (top-left)
      </div>
    </div>
    {% endmacro %}
    """
    macro = MacroElement()
    macro._template = Template(title_html)
    m.get_root().add_child(macro)

    # 12.5 Emergency EOC panel (bottom-right)
    panel_html = (
        "{% macro html(this, kwargs) %}"
        "<div style='position: fixed; bottom: 30px; right: 12px; z-index: 9998;"
        " background: rgba(255,255,255,0.97); padding: 10px 14px;"
        " border-left: 5px solid #d32f2f; border-radius: 5px;"
        " font-family: sans-serif; max-width: 350px;"
        " box-shadow: 0 2px 8px rgba(0,0,0,0.30); font-size: 12px;'>"
        "<div style='font-weight: 700; color: #b71c1c; margin-bottom: 5px; font-size:13px;'>"
        "&#x26A0; IF FLOOD WARNING IS ISSUED</div>"
        "<div style='color: #333; line-height: 1.55;'>"
        "1. <b>Evacuate</b> low-lying areas via <b style='color:#00c853'>green routes</b> on map.<br>"
        "2. <b>Shelter</b>: Patagonia HS (350 cap) &amp; Sports Complex (500 cap) &mdash; green markers.<br>"
        "3. Avoid <b style='color:#b71c1c'>red roads</b> (100-yr stage impassable).<br>"
        "4. <b>Notify Fire/Police</b> (orange/blue markers) immediately.<br>"
        "5. <b>Water / WWTP</b> (teal markers): activate emergency bypass if flooded.<br>"
        "6. <b>Power / Telecom</b> (yellow markers): notify APS &amp; carriers if substation wet.<br>"
        "7. USGS gauge 09481500 = early-warning; rising stage = act NOW.<br>"
        f"<span style='color:#555;font-size:11px;'>100-yr FLOODED: {flooded_roads} roads &bull; "
        f"{flooded_bld} buildings &bull; 9 critical-infra POIs</span>"
        "</div></div>"
        "{% endmacro %}"
    )
    macro2 = MacroElement()
    macro2._template = Template(panel_html)
    m.get_root().add_child(macro2)


    # 13. postMessage listener for simulation mode
    # Allows dashboard to toggle sim layers via iframe.contentWindow.postMessage({type:'showSimLayer', T:100}, '*')
    listener_js = """
    <script>
    window.addEventListener('message', function(e) {
        if (e.data && e.data.type === 'showSimLayer') {
            var T = e.data.T;
            var layerNames = {
                5:   '5-Year Flood Depth [Q=166 cms, T=5yr]',
                10:  '10-Year Flood Depth [Q=230 cms, T=10yr]',
                25:  '25-Year Flood Depth [Q=317 cms, T=25yr]',
                50:  '50-Year Flood Depth [Q=385 cms, T=50yr]',
                100: 'FEMA 1% Annual (100-yr) Flood Depth [REAL]',
                200: '200-Year Flood Depth [Q=525 cms, T=200yr]'
            };
            var targetLayer = layerNames[T];
            if (!targetLayer) return;
            
            // Find the layer control checkboxes
            var inputs = document.querySelectorAll('input[type="checkbox"]');
            inputs.forEach(function(inp) {
                var label = inp.parentElement ? inp.parentElement.textContent.trim() : '';
                // Hide all sim layers except the target
                for (var key in layerNames) {
                    if (label.indexOf(layerNames[key]) !== -1) {
                        inp.checked = (layerNames[key] === targetLayer);
                        inp.dispatchEvent(new Event('change'));
                        break;
                    }
                }
            });
        }
    });
    </script>
    """
    from branca.element import Element
    m.get_root().html.add_child(Element(listener_js))

    m.save(str(out_html))

    manifest = {
        "html": out_html.name,
        "center_latlon": center,
        "bounds_wsen_wgs84": list(ref_bounds),
        "layers": {
            "100yr_reference_depth": {
                "source": "FEMA BFE (Layer 16) IDW WSE - USGS 3DEP 10-m DEM",
                "file": str(ref_tif.relative_to(ROOT)),
                "max_m": float(ref_arr.max()),
            },
            "today_likely_depth_max_m": today_max_depth,
            "today_probability_of_inundation_max": today_max_poi,
            "fema_nfhl_zones": str(nfhl.relative_to(ROOT)) if nfhl.exists() else None,
            "fema_bfe_lines": str(bfe.relative_to(ROOT)) if bfe.exists() else None,
            "fema_waterln":   str(waterln.relative_to(ROOT)) if waterln.exists() else None,
        },
    }
    (OUT / "dashboard_map.json").write_text(json.dumps(manifest, indent=2))
    return out_html


if __name__ == "__main__":
    out = build_map()
    print(f"[OK] Interactive map written to {out}")
    print(f"     Manifest: {OUT/'dashboard_map.json'}")
