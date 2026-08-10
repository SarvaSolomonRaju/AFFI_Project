import { useEffect, useMemo, useRef, useState } from "react";
import { Map, Source, Layer, Marker, Popup } from "react-map-gl/maplibre";
import type { StyleSpecification, ExpressionSpecification, MapLayerMouseEvent, Map as MaplibreMap } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { apiGet, apiRasterUrl } from "../api/client";
import type { MapConfig, HistoricalEventsCatalog, SimState, ElevationResult } from "../types/api";
import { cmsToCfs, fmtFeet } from "../utils/units";
import { gammaHydro } from "../utils/simulation";

// A map library is different from a normal component: it draws
// straight onto a <canvas>, not into regular HTML, so React can't
// just re-render a <div> when data changes the way it does for a
// table. react-map-gl bridges that gap — you still write <Source>/
// <Layer> as JSX, and it translates that into MapLibre's own calls
// underneath. You get the React mental model back.

// No API key needed for any of these — plain public raster tile servers.
// Google Maps' layer switcher (streets/satellite/hybrid/terrain) is the model
// here; these are the closest free, no-key equivalents. Verified directly
// against the live tile servers: Esri World Imagery is real 0.3-0.5m/px over
// the continental US (confirmed down to individual-rooftop clarity at z19
// over Patagonia, AZ specifically) — genuinely Google-Maps-comparable
// resolution, not a downgrade. `maxzoom: 19` on every raster source matches
// each provider's actual native max — without it, MapLibre keeps requesting
// tiles past what the server has (mostly 404s / blank), which reads as
// "blurry when I zoom in"; this makes it cleanly upscale the last real tile
// instead. A true Google-Photos-quality *vector* basemap (rich POI icons —
// the "coffee cup" ask — categorized street labels) needs a vector-tile
// provider like MapTiler or Stadia Maps, which require a free API key we
// don't have; flagged as a real follow-up rather than faked with raster
// tiles that structurally can't do it.
const ESRI_MAXZOOM = 19;
const BASEMAPS: Record<string, { label: string; style: StyleSpecification }> = {
  streets: {
    // Was raw OpenStreetMap standard tiles — busier styling, different
    // color/label choices than most users expect from "the road map view."
    // CARTO Voyager is a free, no-API-key raster basemap deliberately
    // designed to read like Google/Apple Maps' default view (light
    // background, muted road hierarchy, visible place labels, light-blue
    // water) — the closest real match without a paid Google Maps key.
    // Verified reachable directly (curl, 200) before wiring in.
    label: "Streets",
    style: {
      version: 8,
      sources: {
        voyager: {
          type: "raster",
          tiles: [
            "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
            "https://b.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
            "https://c.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
            "https://d.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
          ],
          tileSize: 256,
          maxzoom: ESRI_MAXZOOM,
          attribution: "&copy; CARTO &copy; OpenStreetMap contributors",
        },
      },
      layers: [{ id: "voyager", type: "raster", source: "voyager" }],
    },
  },
  satellite: {
    label: "Satellite",
    style: {
      version: 8,
      sources: {
        esri_sat: {
          type: "raster",
          tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
          tileSize: 256,
          maxzoom: ESRI_MAXZOOM,
          attribution: "Esri, Maxar, Earthstar Geographics",
        },
      },
      layers: [{ id: "esri_sat", type: "raster", source: "esri_sat" }],
    },
  },
  hybrid: {
    label: "Hybrid",
    style: {
      version: 8,
      sources: {
        esri_sat: {
          type: "raster",
          tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
          tileSize: 256,
          maxzoom: ESRI_MAXZOOM,
          attribution: "Esri, Maxar, Earthstar Geographics",
        },
        // Transparent PNG overlay — road/place labels drawn over the imagery,
        // the same "satellite + labels" combination Google Maps calls Hybrid.
        esri_labels: {
          type: "raster",
          tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}"],
          tileSize: 256,
          maxzoom: ESRI_MAXZOOM,
          attribution: "Esri",
        },
      },
      layers: [
        { id: "esri_sat", type: "raster", source: "esri_sat" },
        { id: "esri_labels", type: "raster", source: "esri_labels" },
      ],
    },
  },
  topo: {
    label: "Terrain",
    style: {
      version: 8,
      sources: {
        esri_topo: {
          type: "raster",
          tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"],
          tileSize: 256,
          maxzoom: ESRI_MAXZOOM,
          attribution: "Esri",
        },
      },
      layers: [{ id: "esri_topo", type: "raster", source: "esri_topo" }],
    },
  },
};

// Same colors as style_zone() in src/dashboard/interactive_map.py —
// a MapLibre "match" expression is just an if/elif chain written as
// a JSON array instead of Python.
const NFHL_FILL_COLOR: ExpressionSpecification = [
  "match",
  ["get", "FLD_ZONE"],
  "AE", "#d73027",
  "A", "#fc8d59",
  "AO", "#fee090",
  "#cccccc",
];

// Graduated severity ramp — replaces the old binary FLOODED/dry paint,
// which colored a road with 2 inches of standing water the exact same
// solid red as one under several feet of water. Matches the same NWS
// "Turn Around Don't Drown" bands DepthScaleReference.tsx already cites
// (src/probabilistic/today_feature_status.py's severity_tier), so a road
// tagged "moderate" here means the same thing as "moderate" there.
const SEVERITY_COLOR: Record<string, string> = {
  none: "#37474f",
  minor: "#f4c542",
  moderate: "#e67e22",
  severe: "#c0392b",
};
const SEVERITY_LABEL: Record<string, string> = {
  none: "Dry / no significant water",
  minor: "Minor — ankle-to-shin, passable with care",
  moderate: "Moderate — floats a car away",
  severe: "Severe — carries away most vehicles",
};
const roadSeverityColor: ExpressionSpecification = [
  "match", ["get", "severity"],
  "severe", SEVERITY_COLOR.severe,
  "moderate", SEVERITY_COLOR.moderate,
  "minor", SEVERITY_COLOR.minor,
  "none", SEVERITY_COLOR.none,
  // Fallback for older cached data with no severity field yet — behave
  // like before (binary FLOODED red / dark gray) rather than break.
  ["match", ["get", "status"], "FLOODED", SEVERITY_COLOR.moderate, SEVERITY_COLOR.none],
];
const roadSeverityWidth: ExpressionSpecification = [
  "match", ["get", "severity"],
  "severe", 4,
  "moderate", 3,
  "minor", 2,
  "none", 1.5,
  ["match", ["get", "status"], "FLOODED", 3, 1.5],
];

// Every return period the flood library actually has a pre-computed
// depth raster + per-feature depth_by_rp for (scripts/16_tag_return_periods.py,
// src/probabilistic/scenarios.py DEFAULT_RETURN_PERIODS) — the map's own
// explorer strip can only ever offer scenarios that really exist.
const RETURN_PERIODS = [5, 10, 25, 50, 100, 200] as const;

// building/infrastructure `category` -> distinct color, so "which kind of
// building is this" reads at a glance instead of everything being the same
// gray-or-red. Matches src/common/building_categories.py's category names
// for the buildings layer; infrastructure.geojson's own `category` field
// (school/hospital/police/fire_station/shelter/...) for the infra layer.
const CATEGORY_COLOR: Record<string, string> = {
  School: "#9b59b6",
  "Public/Civic": "#3498db",
  Residential: "#78909c",
  "Commercial/Industrial": "#f39c12",
  "Agricultural/Outbuilding": "#8d6e63",
  Unclassified: "#78909c",
};

const INFRA_ICON: Record<string, string> = {
  shelter: "🏠",
  school: "🏫",
  hospital: "🏥",
  fire_station: "🚒",
  police: "🚓",
  water_supply: "💧",
  wastewater: "🚰",
  power: "⚡",
  power_line: "⚡",
  cell_tower: "📡",
  public_works: "🏗️",
  bridge: "🌉",
  government: "🏛️",
  post_office: "📮",
  mine: "⛏️",
};

function infraIcon(category: string | undefined): string {
  return INFRA_ICON[category ?? ""] ?? "📍";
}

interface ClickedFeatureInfo {
  lng: number;
  lat: number;
  kind: "building" | "infrastructure" | "evac-route" | "road";
  name: string;
  category: string;
  status: string;
  maxDepthM: number;
  severity?: string;
  poiPct?: number | null;
  note?: string;
}

interface FloodMapProps {
  // When set (by the simulation slider), shows that scenario's raster
  // instead of today's real forecast — same map, different data source.
  overlayUrl?: string;
  // True while showing a what-if scenario instead of today's real
  // forecast — drives the on-map warning badge so it's never mistaken
  // for live data.
  isSimulation?: boolean;
  // The return period App.tsx currently considers "active" — in sim mode,
  // whatever the rainfall slider implies; in live mode, null unless the user
  // has clicked one of this map's own explorer buttons. This is now the
  // SAME state Action Plan, Bulletin, Decision Cockpit etc. all read, lifted
  // up to App.tsx — previously this map kept its own separate copy, so
  // clicking "5yr" here changed the map but nothing else on the dashboard,
  // which is the bug being fixed.
  activeRP: number | null;
  // Called when the user clicks a return-period button (or the reset
  // button, with null) on this map's explorer strip.
  onSelectReturnPeriod: (rp: number | null) => void;
  // The active scenario's full stats (Q_cms, time-to-peak) — needed to drive
  // the time-animation control below. null/undefined when no scenario is
  // active (pure live mode, not exploring); the animation control only
  // renders when this is present.
  simState?: SimState | null;
  // Bumped by App.tsx's "Refresh now" button / the 60s poll — without this,
  // roads/buildings/infrastructure only ever refetched when the explored
  // return period changed, so LIVE mode's flood status could go stale for
  // the rest of the session after the first load.
  refreshSignal?: number;
}

export function FloodMap({ overlayUrl, isSimulation, activeRP, onSelectReturnPeriod, simState, refreshSignal }: FloodMapProps) {
  const [config, setConfig] = useState<MapConfig | null>(null);
  const [nfhlZones, setNfhlZones] = useState<GeoJSON.FeatureCollection | null>(null);
  const [roads, setRoads] = useState<GeoJSON.FeatureCollection | null>(null);
  const [buildings, setBuildings] = useState<GeoJSON.FeatureCollection | null>(null);
  const [infrastructure, setInfrastructure] = useState<GeoJSON.FeatureCollection | null>(null);
  const [creekLines, setCreekLines] = useState<GeoJSON.FeatureCollection | null>(null);
  const [evacRoutes, setEvacRoutes] = useState<GeoJSON.FeatureCollection | null>(null);
  const [historicalEvents, setHistoricalEvents] = useState<HistoricalEventsCatalog | null>(null);
  const [popup, setPopup] = useState<ClickedFeatureInfo | null>(null);
  const [basemapKey, setBasemapKey] = useState<keyof typeof BASEMAPS>("streets");

  // The Layers checklist and Legend used to render fully expanded at all
  // times — at higher zoom, where the map itself takes up most of the
  // screen, those two panels (the tallest/widest of the floating controls)
  // ate a large fraction of the visible map. Collapsed by default now, one
  // tap/click away — the return-period explorer stays open since it's the
  // control actually used constantly, not just occasionally.
  const [layersOpen, setLayersOpen] = useState(false);
  const [legendOpen, setLegendOpen] = useState(false);
  const [explorerOpen, setExplorerOpen] = useState(true);

  // Zoomed-out + pitch=45 is what made facility pins look like they were
  // "pointing at the wrong building": a fixed 3D tilt wastes most of the
  // screen on empty horizon once zoomed out, and the whole town's worth of
  // fixed-pixel-size <Marker> icons (not a zoom-aware clustered layer)
  // compresses into the same few screen pixels and visually piles up.
  // Tracking zoom here drives two fixes below: flattening the tilt out at
  // low zoom (like Google/Apple Maps do automatically), and fading the
  // facility markers out before they'd start overlapping.
  const [zoom, setZoom] = useState(13.7);
  const PITCH_FLATTEN_MIN_ZOOM = 12;
  const PITCH_FLATTEN_MAX_ZOOM = 14;
  const MARKER_FADE_ZOOM = 12.5;

  // Google/Apple Maps' default road-map view is flat (pitch=0) — 3D tilt is
  // an opt-in the user reaches for deliberately, not the default. Matching
  // that: 2D is the starting view here too; 3D building extrusions are a
  // toggle, not a fixed tilt forced on every load.
  const [is3D, setIs3D] = useState(false);
  const mapInstanceRef = useRef<MaplibreMap | null>(null);

  function handleMapLoad(e: { target: MaplibreMap }) {
    mapInstanceRef.current = e.target;
  }

  function toggle3D() {
    const next = !is3D;
    setIs3D(next);
    const map = mapInstanceRef.current;
    if (!map) return;
    if (!next) {
      map.easeTo({ pitch: 0, duration: 300 });
      return;
    }
    const t = Math.max(0, Math.min(1, (map.getZoom() - PITCH_FLATTEN_MIN_ZOOM) / (PITCH_FLATTEN_MAX_ZOOM - PITCH_FLATTEN_MIN_ZOOM)));
    map.easeTo({ pitch: t * 45, duration: 300 });
  }

  // Just tracks zoom for the marker-opacity fade below — no pitch changes
  // here. Calling setPitch() on every 'zoom' event (which fires once per
  // animation frame during an in-progress wheel/pinch zoom) fights
  // MapLibre's own easing loop for that gesture and was capping how far a
  // scroll-wheel zoom-out could actually travel. Pitch is only adjusted
  // once the gesture settles, in handleZoomEnd below.
  function handleZoomTrack(e: { target: MaplibreMap }) {
    setZoom(e.target.getZoom());
  }

  function handleZoomEnd(e: { target: MaplibreMap }) {
    // User explicitly chose 2D — stay flat regardless of zoom, don't fight
    // that choice with the auto-tilt-on-zoom-in behavior below.
    if (!is3D) return;
    const z = e.target.getZoom();
    const t = Math.max(0, Math.min(1, (z - PITCH_FLATTEN_MIN_ZOOM) / (PITCH_FLATTEN_MAX_ZOOM - PITCH_FLATTEN_MIN_ZOOM)));
    const targetPitch = t * 45;
    if (Math.abs(e.target.getPitch() - targetPitch) > 0.5) {
      e.target.easeTo({ pitch: targetPitch, duration: 300 });
    }
  }

  const markerOpacity = Math.max(0, Math.min(1, (zoom - (MARKER_FADE_ZOOM - 1)) / 1));

  // Optional data-layer toggles — a "Layers" panel is standard on Google/
  // ArcGIS-style maps, distinct from the basemap switcher above: this
  // controls which real-world reference data draws on top, not which
  // imagery it draws on top of.
  const [showDrainage, setShowDrainage] = useState(true);
  const [showEvacRoutes, setShowEvacRoutes] = useState(true);
  const [showHistorical, setShowHistorical] = useState(true);
  // FEMA NFHL regulatory floodplain — this IS the official flood-plain map
  // (the same one Santa Cruz County's own floodplain administration uses;
  // data/fema_fis is a real FEMA NFHL extract, not a mockup). ON by default
  // so "where's the official map" has an answer without hunting through a
  // layers checkbox; labeled with its own on-map badge below (not just the
  // legend) precisely so it's never mistaken for today's live forecast —
  // this is a permanent regulatory boundary, not a live prediction.
  const [showNfhlZones, setShowNfhlZones] = useState(true);
  const [showHistoryPopup, setShowHistoryPopup] = useState(false);
  // Off by default — it's a colored heatmap tile that competes visually with
  // the flood raster, so only show it when someone actually wants it.
  const [showPopulation, setShowPopulation] = useState(false);
  // Flood-probability heatmap (Pearson-Tukey weighted across best/likely/
  // worst, src/probabilistic/risk_map.py) — the same idea as Google Flood
  // Hub's "Inundation Probability" layer (darker = higher chance of any
  // water), refreshed every forecast cycle now (see map_overlay.py). Off by
  // default so it doesn't visually compete with the main depth overlay.
  const [showPoiLayer, setShowPoiLayer] = useState(false);

  // Elevation tool — click anywhere (not just a building) to query the real
  // USGS 3DEP DEM at that exact point, plus flood depth for whatever return
  // period the map is currently showing.
  const [elevationToolActive, setElevationToolActive] = useState(false);
  const [elevationResult, setElevationResult] = useState<ElevationResult | null>(null);
  const [elevationLoading, setElevationLoading] = useState(false);

  // Time animation — there's no per-timestep flood-extent raster (that would
  // need a full hydraulic re-simulation at every hour, which this pilot
  // doesn't have); what we DO have is the same gamma unit hydrograph driving
  // the Simulated Hydrograph chart (Q_cms, time_to_peak). Animating the
  // overlay's opacity against that curve is an honest "how this storm rises
  // and recedes" visualization — real physics, just not a re-simulated
  // spatial extent at every hour. Labeled clearly in the UI as such.
  const [animPlaying, setAnimPlaying] = useState(false);
  const [animHour, setAnimHour] = useState(0);
  const animFrameRef = useRef<number | null>(null);
  const animLastTsRef = useRef<number | null>(null);
  const HOURS_PER_SECOND = 2.4; // 24-hr storm completes its loop in 10 real seconds

  useEffect(() => {
    if (!animPlaying) {
      animLastTsRef.current = null;
      return;
    }
    function tick(ts: number) {
      if (animLastTsRef.current === null) animLastTsRef.current = ts;
      const dtSec = (ts - animLastTsRef.current) / 1000;
      animLastTsRef.current = ts;
      setAnimHour((h) => (h + dtSec * HOURS_PER_SECOND) % 24);
      animFrameRef.current = requestAnimationFrame(tick);
    }
    animFrameRef.current = requestAnimationFrame(tick);
    return () => {
      if (animFrameRef.current !== null) cancelAnimationFrame(animFrameRef.current);
    };
  }, [animPlaying]);

  // Stop any running animation and reset when the active scenario changes
  // out from under it (different RP, mode switch) — a stale animation tied
  // to the previous scenario's hydrograph would be actively misleading.
  useEffect(() => {
    setAnimPlaying(false);
    setAnimHour(0);
  }, [simState?.return_period_yr, simState?.Q_cms]);

  const animQCms = useMemo(() => {
    if (!simState) return null;
    return gammaHydro(simState.Q_cms, Math.max(0.01, simState.time_to_peak_p50), [animHour])[0];
  }, [simState, animHour]);
  const animIntensity = simState && animQCms !== null && simState.Q_cms > 0
    ? Math.min(1, animQCms / simState.Q_cms)
    : 1;

  // Effective return period for display/elevation-tool purposes: the shared
  // active RP when one is selected, otherwise 100 as a stand-in label. NOT
  // used for the roads/buildings/infrastructure fetch below — those ask for
  // today's real forecast status when nothing is being explored (see
  // isLiveDefault) rather than silently defaulting to the 100-yr reference,
  // which is the bug this fixes: buildings reading "FLOODED" against a
  // hypothetical 100-yr event even on a day with zero real rain forecast.
  const effectiveRP = activeRP ?? 100;
  const isExploring = !isSimulation && activeRP !== null;
  const isLiveDefault = !isSimulation && activeRP === null;
  const isPhotoBasemap = basemapKey === "satellite" || basemapKey === "hybrid";

  useEffect(() => {
    apiGet<MapConfig>("/api/v1/map/config").then(setConfig);
    apiGet<GeoJSON.FeatureCollection>("/api/v1/map/layers/nfhl-zones").then(setNfhlZones);
    // Drainage network, evacuation routes, and the historical-event catalog
    // are all static reference data — real datasets that existed on disk
    // (data/fema_fis/WaterLn_huc12.geojson, data/local_assets/evac_routes.geojson,
    // data/historical_events/sonoita_events.json) but were never rendered on
    // this map before.
    apiGet<GeoJSON.FeatureCollection>("/api/v1/map/layers/creek-centerline").then(setCreekLines);
    apiGet<GeoJSON.FeatureCollection>("/api/v1/map/layers/evac-routes").then(setEvacRoutes);
    apiGet<HistoricalEventsCatalog>("/api/v1/historical-events").then(setHistoricalEvents).catch(() => {});
  }, []);

  // Sim mode with the rainfall slider below flood onset: there is no
  // scenario (simState null), so by definition nothing is flooded — force
  // every feature's status client-side rather than fetching some return
  // period's data (which was the same "shows flooding that isn't there"
  // bug as the raster overlay above, just for the building/road pins).
  const noScenarioActive = isSimulation && activeRP === null;

  function markAllSafe(fc: GeoJSON.FeatureCollection, notFloodedLabel: string): GeoJSON.FeatureCollection {
    return {
      ...fc,
      features: fc.features.map((f) => ({
        ...f,
        properties: { ...f.properties, status: notFloodedLabel, max_depth_m: 0 },
      })),
    };
  }

  useEffect(() => {
    // Omitting return_period entirely (not passing 100) is what asks the
    // backend for today's real forecast status instead of the 100-yr
    // reference — see routes_map.py's apply_today_status branch, which only
    // activates when the param is absent.
    const rpParam = isLiveDefault ? "" : `?return_period=${effectiveRP}`;
    function load() {
      apiGet<GeoJSON.FeatureCollection>(`/api/v1/map/layers/roads${rpParam}`)
        .then((fc) => setRoads(noScenarioActive ? markAllSafe(fc, "OPEN") : fc));
      apiGet<GeoJSON.FeatureCollection>(`/api/v1/map/layers/buildings${rpParam}`)
        .then((fc) => setBuildings(noScenarioActive ? markAllSafe(fc, "OPEN") : fc));
      apiGet<GeoJSON.FeatureCollection>(`/api/v1/map/layers/infrastructure${rpParam}`)
        .then((fc) => setInfrastructure(noScenarioActive ? markAllSafe(fc, "SAFE") : fc));
    }
    load();
    // Only keep polling in true live mode — an explored/simulated scenario
    // is static reference data, it doesn't change on its own.
    if (!isLiveDefault) return;
    const id = setInterval(load, 60_000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [effectiveRP, isLiveDefault, noScenarioActive, refreshSignal]);

  const infraFeatures = useMemo(
    () => (infrastructure?.features ?? []) as GeoJSON.Feature<GeoJSON.Point>[],
    [infrastructure],
  );

  // Named buildings from OSM (only ~47 of 1345 carry a real name) — surfaced
  // as text labels so the map reads like a real street map instead of a sea
  // of "Unnamed building". Labels are shown only once zoomed in enough to be
  // legible (see BUILDING_LABEL_ZOOM below) so they don't pile up town-wide.
  const namedBuildings = useMemo(() => {
    const feats = buildings?.features ?? [];
    const out: { name: string; lng: number; lat: number }[] = [];
    for (const f of feats) {
      const name = f.properties?.name;
      if (typeof name !== "string" || !name || name.toLowerCase() === "nan" || name.toLowerCase() === "none") continue;
      const g = f.geometry as GeoJSON.Polygon | GeoJSON.MultiPolygon;
      const ring = g.type === "Polygon" ? g.coordinates[0] : g.type === "MultiPolygon" ? g.coordinates[0]?.[0] : null;
      if (!ring || ring.length === 0) continue;
      let sx = 0, sy = 0;
      for (const p of ring) { sx += p[0]; sy += p[1]; }
      out.push({ name, lng: sx / ring.length, lat: sy / ring.length });
    }
    return out;
  }, [buildings]);
  const BUILDING_LABEL_ZOOM = 15.5;
  const showBuildingLabels = zoom >= BUILDING_LABEL_ZOOM;

  if (!config) return <p>Loading map…</p>;

  // All flood-library rasters (today's forecast and every simulation
  // scenario) are built on the same 10m grid, so they share one set of
  // bounds — "fema-100yr" is just the one we know always exists.
  const b = config.raster_bounds["fema-100yr"];
  const rasterUrl = activeRP !== null
    ? apiRasterUrl(`/api/v1/simulation/raster/${activeRP}`)
    : isSimulation
      // Sim mode with the rainfall slider below the flood-onset threshold:
      // there IS no scenario (simState is null), so there is nothing to
      // overlay. Falling through to today's live raster here was the bug —
      // it made "0 inches of rain" on the slider silently show whatever
      // today's real forecast happened to be, including a real flood, which
      // reads as "the map shows flooding even though I set rainfall to zero."
      ? null
      : (overlayUrl ?? apiRasterUrl("/api/v1/map/raster/today-likely"));

  function handleMapClick(e: MapLayerMouseEvent) {
    if (elevationToolActive) {
      setElevationLoading(true);
      setElevationResult(null);
      const { lng, lat } = e.lngLat;
      apiGet<ElevationResult>(`/api/v1/map/elevation?lat=${lat}&lon=${lng}&return_period=${effectiveRP}`)
        .then(setElevationResult)
        .catch(() => setElevationResult(null))
        .finally(() => setElevationLoading(false));
      return;
    }
    const feature = e.features?.[0];
    if (!feature) { setPopup(null); return; }
    const p = feature.properties ?? {};
    // infrastructure markers handle their own onClick directly (see Marker
    // below), never through here — this only ever fires for the layer ids
    // listed in interactiveLayerIds.
    if (feature.layer?.id === "evac-routes-line") {
      setPopup({
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        kind: "evac-route",
        name: p.name ?? "Evacuation route",
        category: p.route_type ? `${p.route_type} route -> ${p.destination ?? "?"}` : "Evacuation route",
        status: p.status ?? "UNKNOWN",
        maxDepthM: 0,
        note: p.note,
      });
      return;
    }
    if (feature.layer?.id === "roads-line") {
      setPopup({
        lng: e.lngLat.lng,
        lat: e.lngLat.lat,
        kind: "road",
        name: p.name && p.name !== "nan" ? p.name : "(unnamed road)",
        category: typeof p.highway === "string" ? p.highway.replace(/_/g, " ") : "Road",
        status: p.status ?? "UNKNOWN",
        maxDepthM: typeof p.max_depth_m === "number" ? p.max_depth_m : parseFloat(p.max_depth_m) || 0,
        severity: p.severity,
        poiPct: typeof p.poi_pct === "number" ? p.poi_pct : null,
      });
      return;
    }
    setPopup({
      lng: e.lngLat.lng,
      lat: e.lngLat.lat,
      kind: "building",
      name: p.name && p.name !== "nan" ? p.name : "(unnamed building)",
      category: p.category ?? "Unclassified",
      status: p.status ?? "UNKNOWN",
      maxDepthM: typeof p.max_depth_m === "number" ? p.max_depth_m : parseFloat(p.max_depth_m) || 0,
      severity: p.severity,
      poiPct: typeof p.poi_pct === "number" ? p.poi_pct : null,
    });
  }

  return (
    <div style={{ height: 560, marginTop: 20, borderRadius: 8, overflow: "hidden", position: "relative" }}>
      {isSimulation && !isExploring && (
        <div style={{
          position: "absolute", top: 12, left: 12, zIndex: 10,
          background: "var(--accent-orange)", color: "black", fontWeight: 700,
          padding: "6px 12px", borderRadius: 6, fontSize: "0.85rem",
        }}>
          WHAT-IF SIMULATION — not live data
        </div>
      )}
      {isExploring && (
        <div style={{
          position: "absolute", top: 12, left: 12, zIndex: 10,
          background: "#4ea8de", color: "black", fontWeight: 700,
          padding: "6px 12px", borderRadius: 6, fontSize: "0.85rem",
        }}>
          EXPLORING {activeRP}-YEAR SCENARIO — Action Plan, Bulletin &amp; every panel below match this
        </div>
      )}
      {showNfhlZones && !isExploring && !isSimulation && (
        <div style={{
          position: "absolute", top: 12, left: 12, zIndex: 10,
          background: "rgba(20,26,34,0.92)", color: "white", fontWeight: 600,
          padding: "6px 12px", borderRadius: 6, fontSize: "0.78rem",
          display: "flex", alignItems: "center", gap: 6,
        }}>
          <span style={{ width: 9, height: 9, borderRadius: 2, background: "#d73027", display: "inline-block" }} />
          Official FEMA flood zone shown — a fixed legal boundary, not today's forecast
        </div>
      )}

      {/* Time animation — plays the storm's rise/fall against the gamma
          hydrograph by scaling the flood overlay's opacity over a 24-hr
          loop. This is NOT a re-simulated evolving flood extent (that needs
          a depth raster per timestep, which this pilot doesn't have) — the
          footprint shown is always the scenario's peak extent; only the
          intensity/opacity animates. Labeled honestly as such. Only shown
          when a scenario is active (sim mode, or live-mode exploring),
          since that's the only time there's a real hydrograph to animate. */}
      {simState && (
        <div style={{
          position: "absolute", bottom: 12, left: "50%", transform: "translateX(-50%)", zIndex: 10,
          background: "rgba(20,26,34,0.92)", borderRadius: 8, padding: "8px 14px",
          display: "flex", alignItems: "center", gap: 10, minWidth: 340,
        }}>
          <button
            onClick={() => setAnimPlaying((p) => !p)}
            style={{
              width: 28, height: 28, borderRadius: "50%", border: "none", cursor: "pointer",
              background: "#4ea8de", color: "black", fontWeight: 700, fontSize: "0.8rem",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}
            title={animPlaying ? "Pause" : "Play storm timeline"}
          >
            {animPlaying ? "❚❚" : "▶"}
          </button>
          <input
            type="range"
            min={0}
            max={24}
            step={0.1}
            value={animHour}
            onChange={(e) => { setAnimPlaying(false); setAnimHour(parseFloat(e.target.value)); }}
            style={{ flex: 1, cursor: "pointer", accentColor: "#4ea8de" }}
          />
          <div style={{ color: "white", fontSize: "0.72rem", minWidth: 150, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
            <div style={{ fontWeight: 700 }}>
              Hour {animHour.toFixed(1)} of 24 ·{" "}
              <span style={{ color: simState && animHour < simState.time_to_peak_p50 * 0.9 ? "#f39c12" : simState && animHour < simState.time_to_peak_p50 * 1.2 ? "#e74c3c" : "#4ea8de" }}>
                {simState && animHour < simState.time_to_peak_p50 * 0.9 ? "rising ↑" : simState && animHour < simState.time_to_peak_p50 * 1.2 ? "PEAK" : "receding ↓"}
              </span>
            </div>
            <div style={{ color: "#aab4c0" }}>
              {animQCms !== null ? `~${Math.round(cmsToCfs(animQCms)).toLocaleString()} cfs flowing now` : ""}
            </div>
          </div>
        </div>
      )}

      {/* Return-period explorer — always available, live or sim mode, so
          "what would a 5/10/25/50/100/200-yr event flood" can be answered
          on the same map without switching modes. */}
      <div style={{
        position: "absolute", top: 12, right: 12, zIndex: 10,
        background: "rgba(20,26,34,0.9)", borderRadius: 8, padding: explorerOpen ? "8px 10px" : "6px 10px",
        display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end",
      }}>
        <button
          onClick={() => setExplorerOpen((v) => !v)}
          style={{
            background: "none", border: "none", cursor: "pointer", padding: 0,
            fontSize: "0.68rem", color: "#aab4c0", fontWeight: 700, letterSpacing: "0.06em",
            display: "flex", alignItems: "center", gap: 4,
          }}
        >
          EXPLORE RETURN PERIOD {explorerOpen ? "▾" : "▸"}
        </button>
        {explorerOpen && (
          <>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", justifyContent: "flex-end" }}>
              {/* In sim mode the rainfall slider is the only source of truth —
                  there's nothing separate to "reset" to, so this button only
                  makes sense in live mode, where it clears the map's explore
                  override and returns the whole dashboard to real forecast data. */}
              {!isSimulation && (
                <button
                  onClick={() => onSelectReturnPeriod(null)}
                  style={{
                    padding: "4px 8px", borderRadius: 4, fontSize: "0.72rem", cursor: "pointer",
                    border: "1px solid #4ea8de",
                    background: activeRP === null ? "#4ea8de" : "transparent",
                    color: activeRP === null ? "black" : "#4ea8de",
                    fontWeight: 700,
                  }}
                >
                  LIVE
                </button>
              )}
              {RETURN_PERIODS.map((rp) => (
                <button
                  key={rp}
                  onClick={() => onSelectReturnPeriod(rp)}
                  style={{
                    padding: "4px 8px", borderRadius: 4, fontSize: "0.72rem", cursor: "pointer",
                    border: "1px solid var(--border)",
                    background: activeRP === rp ? "#e67e22" : "transparent",
                    color: activeRP === rp ? "black" : "white",
                    fontWeight: activeRP === rp ? 700 : 400,
                  }}
                >
                  {rp}yr
                </button>
              ))}
            </div>
            <div style={{ fontSize: "0.68rem", color: "#e0e0e0" }}>
              {!isSimulation && activeRP === null ? (
                <>Showing: <strong>today's live forecast</strong></>
              ) : (
                <>Showing: <strong>{effectiveRP}-year</strong> flood extent</>
              )}
              {isSimulation && <> — tracks the rainfall slider</>}
            </div>
          </>
        )}
      </div>

      <Map
        mapStyle={BASEMAPS[basemapKey].style}
        initialViewState={{
          longitude: config.center.lon,
          latitude: config.center.lat,
          // The creek channel is only ~1-2% of the full watershed frame —
          // real geography, not a display bug — so at zoom 12 the flood
          // raster overlay reads as a near-invisible thin line. 13.7 frames
          // tight on the town + creek corridor where the flood extent and
          // buildings are both large enough on screen to actually read.
          zoom: 13.7,
          pitch: 0, // flat by default, like Google/Apple Maps — 3D is the toggle below, not the default
        }}
        // Esri World Imagery's native tiles top out at z19 for rural AZ; the
        // raster sources cap `maxzoom` at 19 (see BASEMAPS) so past that
        // MapLibre cleanly OVERZOOMS the last real tile instead of requesting
        // non-existent z20+ tiles (404 → blank). Letting the camera go to 20
        // gives a smooth "one more step in" for reading individual rooftops
        // without the blurriness of requesting tiles the server doesn't have.
        maxZoom={20}
        interactiveLayerIds={["buildings-3d-safe", "buildings-3d-flooded", "evac-routes-line", "roads-line"]}
        onClick={handleMapClick}
        onLoad={handleMapLoad}
        onZoom={handleZoomTrack}
        onZoomEnd={handleZoomEnd}
        cursor={elevationToolActive ? "crosshair" : "grab"}
      >
        {config.reference_markers.map((m) => (
          <Marker key={m.label} longitude={m.lon} latitude={m.lat} anchor="bottom">
            <div title={m.label} style={{ fontSize: 20 }}>📍</div>
          </Marker>
        ))}

        {/* NFHL zone fill goes UNDERNEATH the scenario raster (layers painted
            in source order — later = on top). Static reference zone first;
            the actual depth-colored overlay for whichever scenario is
            selected needs to sit on top of it or its blue gets muddied by
            the zone's orange/red fill, which is what was happening before. */}
        {showNfhlZones && nfhlZones && (
          <Source id="nfhl-zones" type="geojson" data={nfhlZones}>
            <Layer
              id="nfhl-zones-fill"
              type="fill"
              paint={{ "fill-color": NFHL_FILL_COLOR, "fill-opacity": 0.35 }}
            />
          </Source>
        )}

        {b && rasterUrl && (
          <Source
            id="overlay-raster"
            type="image"
            url={rasterUrl}
            coordinates={[
              [b.west, b.north],
              [b.east, b.north],
              [b.east, b.south],
              [b.west, b.south],
            ]}
          >
            <Layer id="overlay-layer" type="raster" paint={{
              // Baseline floor of 0.15 so the extent is never fully invisible
              // between animation frames — only ever scaled down while
              // simState (and therefore a real hydrograph) is active.
              "raster-opacity": simState ? 0.15 + 0.7 * animIntensity : 0.85,
            }} />
          </Source>
        )}

        {/* Population density — WorldPop 2020, 1km resolution, clipped to
            this HUC-12 (scripts/17_build_population_layer.py). Real gridded
            population counts (free, no API key — data.worldpop.org), not a
            fabricated overlay. Off by default since it visually competes
            with the flood raster. */}
        {showPopulation && config.raster_bounds["population"] && (
          <Source
            id="population-raster"
            type="image"
            url={apiRasterUrl("/api/v1/map/raster/population")}
            coordinates={(() => {
              const pb = config.raster_bounds["population"];
              return [[pb.west, pb.north], [pb.east, pb.north], [pb.east, pb.south], [pb.west, pb.south]];
            })()}
          >
            <Layer id="population-layer" type="raster" paint={{ "raster-opacity": 0.6 }} />
          </Source>
        )}

        {/* Flood-probability heatmap — Google-Flood-Hub-style "Inundation
            Probability" layer, real ensemble-weighted probability (not the
            depth raster). Sits above the depth overlay when both are on;
            drop depth opacity mentally reads fine since they're different
            hues (blue depth vs. yellow-red probability). */}
        {showPoiLayer && config.raster_bounds["today-poi"] && (
          <Source
            id="poi-raster"
            type="image"
            url={apiRasterUrl("/api/v1/map/raster/today-poi")}
            coordinates={(() => {
              const pb = config.raster_bounds["today-poi"];
              return [[pb.west, pb.north], [pb.east, pb.north], [pb.east, pb.south], [pb.west, pb.south]];
            })()}
          >
            <Layer id="poi-layer" type="raster" paint={{ "raster-opacity": 0.75 }} />
          </Source>
        )}

        {/* Drainage network — FEMA FIS creek/wash centerlines
            (data/fema_fis/WaterLn_huc12.geojson). This is the channel the
            flood library's depth grids are actually built around; showing
            it gives a manager the "why does water go here" context the
            depth overlay alone doesn't. */}
        {showDrainage && creekLines && (
          <Source id="creek-lines" type="geojson" data={creekLines}>
            <Layer
              id="creek-lines-line"
              type="line"
              paint={{ "line-color": "#2196f3", "line-width": 2, "line-opacity": 0.85 }}
              layout={{ "line-cap": "round" }}
            />
          </Source>
        )}

        {roads && (
          <Source id="roads" type="geojson" data={roads}>
            <Layer
              id="roads-line"
              type="line"
              paint={{
                "line-color": roadSeverityColor,
                "line-width": roadSeverityWidth,
              }}
            />
          </Source>
        )}

        {/* Evacuation routes — data/local_assets/evac_routes.geojson (3 named
            routes with destinations, built by scripts/15_build_infrastructure.py)
            existed on disk but was never registered as a servable map layer
            until now. Distinct dashed gold line so it reads as "the route,"
            not just another road. */}
        {showEvacRoutes && evacRoutes && (
          <Source id="evac-routes" type="geojson" data={evacRoutes}>
            <Layer
              id="evac-routes-line"
              type="line"
              paint={{ "line-color": "#ffd600", "line-width": 4, "line-opacity": 0.9, "line-dasharray": [2, 1.5] }}
              layout={{ "line-cap": "round" }}
            />
          </Source>
        )}

        {buildings && (
          <Source id="buildings" type="geojson" data={buildings}>
            {/* fill-extrusion is what gives buildings height/3D. We don't
                have real building-height data, so every building gets a
                fixed height — except schools, which get extra height so
                they read as landmarks regardless of flood status. Color is
                by category first (School purple, Public/Civic blue,
                Residential slate, Commercial orange, Agricultural brown) so
                "what kind of building is this" reads at a glance.
                MapLibre does NOT allow a data/`get` expression for
                fill-extrusion-opacity (constant or zoom-only only) — using
                one throws at addLayer() and silently drops the whole layer,
                which is why buildings were never rendering. Split into two
                layers filtered by status instead, each with its own
                constant opacity, to get the same "flooded pops more" effect
                without hitting that restriction.

                On the satellite/hybrid basemaps the footprints underneath
                are REAL rooftop photography (verified: individual houses,
                cars, trees resolve at z19) — a solid opaque colored box on
                top of that just reads as "generic gray block," hiding the
                actual imagery the satellite/hybrid mode exists to show.
                Dropping opacity and height way down there (and adding a
                thin category-colored outline below, always on) keeps the
                flood/category signal legible while letting the real photo
                show through, instead of painting over it. */}
            <Layer
              id="buildings-3d-safe"
              type="fill-extrusion"
              filter={["!=", ["get", "status"], "FLOODED"]}
              paint={{
                "fill-extrusion-color": [
                  "match",
                  ["get", "category"],
                  "School", CATEGORY_COLOR.School,
                  "Public/Civic", CATEGORY_COLOR["Public/Civic"],
                  "Residential", CATEGORY_COLOR.Residential,
                  "Commercial/Industrial", CATEGORY_COLOR["Commercial/Industrial"],
                  "Agricultural/Outbuilding", CATEGORY_COLOR["Agricultural/Outbuilding"],
                  CATEGORY_COLOR.Unclassified,
                ],
                "fill-extrusion-height": isPhotoBasemap ? ["match", ["get", "category"], "School", 6, 2] : ["match", ["get", "category"], "School", 18, 8],
                "fill-extrusion-opacity": isPhotoBasemap ? 0.12 : 0.55,
              }}
            />
            <Layer
              id="buildings-3d-flooded"
              type="fill-extrusion"
              filter={["==", ["get", "status"], "FLOODED"]}
              paint={{
                "fill-extrusion-color": [
                  "match",
                  ["get", "category"],
                  "School", CATEGORY_COLOR.School,
                  "Public/Civic", CATEGORY_COLOR["Public/Civic"],
                  "Residential", CATEGORY_COLOR.Residential,
                  "Commercial/Industrial", CATEGORY_COLOR["Commercial/Industrial"],
                  "Agricultural/Outbuilding", CATEGORY_COLOR["Agricultural/Outbuilding"],
                  CATEGORY_COLOR.Unclassified,
                ],
                "fill-extrusion-height": isPhotoBasemap ? ["match", ["get", "category"], "School", 6, 2] : ["match", ["get", "category"], "School", 18, 8],
                "fill-extrusion-opacity": isPhotoBasemap ? 0.4 : 0.95,
              }}
            />
            {/* Crisp footprint outline, always on — carries the category/
                flood-status color even where the fill is nearly transparent
                over satellite imagery. */}
            <Layer
              id="buildings-outline"
              type="line"
              paint={{
                "line-color": [
                  "match", ["get", "severity"],
                  "severe", SEVERITY_COLOR.severe,
                  "moderate", SEVERITY_COLOR.moderate,
                  "minor", SEVERITY_COLOR.minor,
                  ["match", ["get", "category"],
                    "School", CATEGORY_COLOR.School,
                    "Public/Civic", CATEGORY_COLOR["Public/Civic"],
                    "Residential", CATEGORY_COLOR.Residential,
                    "Commercial/Industrial", CATEGORY_COLOR["Commercial/Industrial"],
                    "Agricultural/Outbuilding", CATEGORY_COLOR["Agricultural/Outbuilding"],
                    CATEGORY_COLOR.Unclassified,
                  ],
                ],
                "line-width": 1.3,
                "line-opacity": 0.9,
              }}
            />
          </Source>
        )}

        {/* Critical infrastructure — schools/hospitals/fire/police/water/power.
            Rendered as emoji Markers (not a vector layer) since there are only
            16 of them and each needs its own click-popup + a colored ring for
            flood status that a fill-extrusion layer can't give a point. */}
        {markerOpacity > 0 && infraFeatures.map((f, i) => {
          const p = f.properties ?? {};
          const [lng, lat] = f.geometry.coordinates;
          const flooded = p.status === "FLOODED";
          return (
            <Marker
              key={`infra-${i}`}
              longitude={lng}
              latitude={lat}
              anchor="bottom"
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                setPopup({
                  lng, lat, kind: "infrastructure",
                  name: p.name ?? "Unnamed facility",
                  category: p.category_label ?? p.category ?? "Infrastructure",
                  status: p.status ?? "UNKNOWN",
                  maxDepthM: typeof p.max_depth_m === "number" ? p.max_depth_m : 0,
                  severity: p.severity,
                  poiPct: typeof p.poi_pct === "number" ? p.poi_pct : null,
                });
              }}
            >
              {/* A plain circle badge with anchor="center" (the old code) has
                  no visual "tip" — nothing to tell you exactly which point on
                  the ground it refers to, and at pitch=45 with tall building
                  extrusions nearby, that ambiguity reads as "the label isn't
                  pointing at the right building." A pin — circle + a tapered
                  stem ending in a point — with anchor="bottom" puts that exact
                  point on the exact coordinate, the same convention Google/
                  Apple Maps use for 3D pins on extruded buildings. */}
              <div
                style={{
                  display: "flex", flexDirection: "column", alignItems: "center", cursor: "pointer",
                  opacity: markerOpacity, pointerEvents: markerOpacity < 0.3 ? "none" : "auto",
                  transition: "opacity 0.15s linear",
                }}
                title={p.name}
              >
                <div
                  style={{
                    position: "relative",
                    fontSize: 16,
                    background: flooded ? "rgba(211,47,47,0.92)" : "rgba(39,174,96,0.92)",
                    borderRadius: "50%", width: 26, height: 26,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    border: "2px solid white", boxShadow: "0 1px 4px rgba(0,0,0,0.5)",
                  }}
                >
                  {infraIcon(p.category)}
                  {/* Status carried by shape, not just red/green hue, so it
                      reads for colorblind users too — a small badge, not a
                      full color swap, so the facility icon stays legible. */}
                  <span style={{
                    position: "absolute", bottom: -3, right: -3, width: 13, height: 13, borderRadius: "50%",
                    background: flooded ? "#7a0000" : "#0d4d1e", border: "1.5px solid white",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 8, fontWeight: 900, color: "white", lineHeight: 1,
                  }}>
                    {flooded ? "✕" : "✓"}
                  </span>
                </div>
                <div
                  style={{
                    width: 0, height: 0, marginTop: -2,
                    borderLeft: "5px solid transparent",
                    borderRight: "5px solid transparent",
                    borderTop: `8px solid ${flooded ? "rgba(211,47,47,0.92)" : "rgba(39,174,96,0.92)"}`,
                    filter: "drop-shadow(0 1px 1px rgba(0,0,0,0.4))",
                  }}
                />
              </div>
            </Marker>
          );
        })}

        {/* Named-building labels (real OSM names) — only at close zoom so
            they don't overlap. Non-interactive text, positioned at each
            named footprint's centroid. */}
        {showBuildingLabels && namedBuildings.map((nb) => (
          <Marker key={`lbl-${nb.name}-${nb.lng.toFixed(5)}`} longitude={nb.lng} latitude={nb.lat} anchor="center">
            <div style={{
              fontSize: "0.66rem", fontWeight: 600, color: "#fff",
              textShadow: "0 0 3px rgba(0,0,0,0.95), 0 0 3px rgba(0,0,0,0.95)",
              whiteSpace: "nowrap", pointerEvents: "none", userSelect: "none",
              transform: "translateY(-14px)",
            }}>
              {nb.name}
            </div>
          </Marker>
        ))}

        {popup && (
          <Popup
            longitude={popup.lng}
            latitude={popup.lat}
            closeButton
            closeOnClick={false}
            onClose={() => setPopup(null)}
            anchor="bottom"
          >
            <div style={{ minWidth: 180, color: "#111", fontSize: "0.82rem" }}>
              <div style={{ fontWeight: 700, marginBottom: 2 }}>{popup.name}</div>
              <div style={{ color: "#555", marginBottom: 4 }}>{popup.category}</div>
              {popup.kind === "evac-route" ? (
                <>
                  {popup.note && <div style={{ color: "#333", fontSize: "0.78rem", marginBottom: 4 }}>{popup.note}</div>}
                  <div style={{
                    display: "inline-block", padding: "2px 8px", borderRadius: 4,
                    fontWeight: 700, fontSize: "0.75rem",
                    background: "#8b6d00", color: "white",
                  }}>
                    STATUS: {popup.status}
                  </div>
                </>
              ) : (
                <>
                  <div style={{
                    display: "inline-block", padding: "2px 8px", borderRadius: 4,
                    fontWeight: 700, fontSize: "0.75rem", marginBottom: 4,
                    background: SEVERITY_COLOR[popup.severity ?? ""] ?? (popup.status === "FLOODED" ? "#e67e22" : "#27ae60"),
                    color: "white",
                  }}>
                    {popup.status === "FLOODED"
                      ? (SEVERITY_LABEL[popup.severity ?? ""] ?? `Water expected — ${fmtFeet(popup.maxDepthM, 2)}`)
                      : isLiveDefault ? "Dry — no flooding expected" : "Dry at this scenario"}
                  </div>
                  {popup.status === "FLOODED" && (
                    <div style={{ color: "#333", fontSize: "0.75rem", marginBottom: 4 }}>
                      Depth ~{fmtFeet(popup.maxDepthM, 2)}
                    </div>
                  )}
                  {typeof popup.poiPct === "number" && (
                    <div style={{ color: "#333", fontSize: "0.75rem", marginBottom: 4 }}>
                      <strong>{popup.poiPct}%</strong> model confidence this spot gets some water today
                    </div>
                  )}
                  <div style={{ color: "#777", fontSize: "0.72rem" }}>
                    {isLiveDefault ? "based on today's live forecast — an estimate, not a certainty" : `at the ${effectiveRP}-year reference event`}
                  </div>
                </>
              )}
            </div>
          </Popup>
        )}

        {/* Historical flood events — data/historical_events/sonoita_events.json
            has no per-event coordinates (it's a gauge-record catalog, not a
            GIS dataset), so this is one marker at the USGS gauge point with
            every documented event in its popup, rather than fabricating
            per-event locations that don't exist in the source data. */}
        {showHistorical && historicalEvents && (
          <Marker
            longitude={config.reference_markers[0]?.lon ?? -110.7521}
            latitude={config.reference_markers[0]?.lat ?? 31.5407}
            anchor="bottom"
            onClick={(e) => {
              e.originalEvent.stopPropagation();
              setShowHistoryPopup((v) => !v);
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", cursor: "pointer" }} title="Historical flood events">
              <div style={{
                fontSize: 15, background: "rgba(142,68,173,0.92)", borderRadius: "50%",
                width: 24, height: 24, display: "flex", alignItems: "center", justifyContent: "center",
                border: "2px solid white", boxShadow: "0 1px 4px rgba(0,0,0,0.5)",
              }}>
                📜
              </div>
              <div style={{
                width: 0, height: 0, marginTop: -2,
                borderLeft: "5px solid transparent", borderRight: "5px solid transparent",
                borderTop: "8px solid rgba(142,68,173,0.92)",
                filter: "drop-shadow(0 1px 1px rgba(0,0,0,0.4))",
              }} />
            </div>
          </Marker>
        )}

        {showHistoryPopup && historicalEvents && (
          <Popup
            longitude={config.reference_markers[0]?.lon ?? -110.7521}
            latitude={config.reference_markers[0]?.lat ?? 31.5407}
            closeButton
            closeOnClick={false}
            onClose={() => setShowHistoryPopup(false)}
            anchor="bottom"
            maxWidth="280px"
          >
            <div style={{ color: "#111", fontSize: "0.8rem" }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Documented flood history</div>
              <div style={{ color: "#666", fontSize: "0.72rem", marginBottom: 6 }}>
                USGS gauge {historicalEvents.usgs_gauge} — {historicalEvents.events.length} events on record
              </div>
              {historicalEvents.events.map((ev) => (
                <div key={ev.name} style={{ marginBottom: 6, paddingBottom: 6, borderBottom: "1px solid #eee" }}>
                  <div style={{ fontWeight: 700 }}>{ev.name}</div>
                  <div style={{ color: "#555" }}>{ev.date} — ~{ev.approx_return_period_yr}yr event</div>
                  <div style={{ color: "#777", fontSize: "0.72rem" }}>
                    {ev.rainfall_24hr_in}" rain, peak {ev.peak_q_cms} cms
                  </div>
                </div>
              ))}
            </div>
          </Popup>
        )}

        {elevationToolActive && elevationResult && (
          <Popup
            longitude={elevationResult.lon}
            latitude={elevationResult.lat}
            closeButton
            closeOnClick={false}
            onClose={() => setElevationResult(null)}
            anchor="bottom"
          >
            <div style={{ color: "#111", fontSize: "0.82rem", minWidth: 170 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>📏 Elevation</div>
              {elevationResult.elevation_m !== null ? (
                <>
                  <div>{fmtFeet(elevationResult.elevation_m, 0)} ({elevationResult.elevation_m.toFixed(1)} m)</div>
                  {elevationResult.flood_depth_m !== null && (
                    <div style={{ marginTop: 4, color: elevationResult.flood_depth_m > 0 ? "#c0392b" : "#27ae60", fontWeight: 700 }}>
                      {elevationResult.flood_depth_m > 0
                        ? `Flood depth: ${fmtFeet(elevationResult.flood_depth_m, 2)} at ${elevationResult.return_period_yr}yr`
                        : `Dry at ${elevationResult.return_period_yr}yr event`}
                    </div>
                  )}
                  <div style={{ color: "#888", fontSize: "0.68rem", marginTop: 4 }}>USGS 3DEP 10m DEM</div>
                </>
              ) : (
                <div style={{ color: "#888" }}>No elevation data at this point.</div>
              )}
            </div>
          </Popup>
        )}
      </Map>

      {elevationToolActive && elevationLoading && (
        <div style={{
          position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", zIndex: 15,
          background: "rgba(20,26,34,0.9)", color: "white", padding: "6px 14px", borderRadius: 6, fontSize: "0.8rem",
        }}>
          Reading elevation…
        </div>
      )}

      {/* Basemap layer switcher — Google Maps' streets/satellite/terrain
          toggle, using the free ArcGIS/OSM tile servers already referenced
          in /api/v1/map/config's base_tiles list (which was defined but
          never actually wired into the map before this). */}
      <div style={{
        position: "absolute", top: 64, right: 12, zIndex: 10,
        background: "rgba(20,26,34,0.9)", borderRadius: 8, padding: "6px 8px",
        display: "flex", gap: 4,
      }}>
        {(Object.keys(BASEMAPS) as (keyof typeof BASEMAPS)[]).map((key) => (
          <button
            key={key}
            onClick={() => setBasemapKey(key)}
            style={{
              padding: "4px 8px", borderRadius: 4, fontSize: "0.7rem", cursor: "pointer",
              border: "1px solid var(--border)",
              background: basemapKey === key ? "#4ea8de" : "transparent",
              color: basemapKey === key ? "black" : "white",
              fontWeight: basemapKey === key ? 700 : 400,
            }}
          >
            {BASEMAPS[key].label}
          </button>
        ))}
        <span style={{ width: 1, background: "var(--border)", margin: "0 2px" }} />
        {/* Google/Apple Maps convention: flat by default, 3D tilt is an
            explicit opt-in. Two-button pill (not a single toggle label) so
            it reads the same "click the state you want" way as the
            basemap buttons right next to it, instead of ambiguously
            showing whichever state is already active. */}
        <button
          onClick={() => { if (is3D) toggle3D(); }}
          title="Flat top-down view"
          style={{
            padding: "4px 8px", borderRadius: 4, fontSize: "0.7rem", cursor: "pointer",
            border: "1px solid var(--border)",
            background: !is3D ? "#4ea8de" : "transparent",
            color: !is3D ? "black" : "white",
            fontWeight: !is3D ? 700 : 400,
          }}
        >
          2D
        </button>
        <button
          onClick={() => { if (!is3D) toggle3D(); }}
          title="Tilted 3D view (extruded buildings)"
          style={{
            padding: "4px 8px", borderRadius: 4, fontSize: "0.7rem", cursor: "pointer",
            border: "1px solid var(--border)",
            background: is3D ? "#4ea8de" : "transparent",
            color: is3D ? "black" : "white",
            fontWeight: is3D ? 700 : 400,
          }}
        >
          3D
        </button>
      </div>

      {/* Data layers panel — distinct from the basemap switcher above: this
          toggles which reference datasets draw on top (Google/ArcGIS-style
          "Layers" panel), not which imagery underlies everything. */}
      <div style={{
        position: "absolute", top: 100, right: 12, zIndex: 10,
        background: "rgba(20,26,34,0.9)", borderRadius: 8, padding: layersOpen ? "8px 10px" : "6px 10px",
        display: "flex", flexDirection: "column", gap: 4, alignItems: "flex-start",
      }}>
        <button
          onClick={() => setLayersOpen((v) => !v)}
          style={{
            background: "none", border: "none", cursor: "pointer", padding: 0,
            fontSize: "0.68rem", color: "#aab4c0", fontWeight: 700, letterSpacing: "0.06em",
            display: "flex", alignItems: "center", gap: 4,
          }}
        >
          🗂️ LAYERS {layersOpen ? "▾" : "▸"}
        </button>
        {layersOpen && (
          <>
            {[
              { key: "femazone", label: "Official FEMA flood zone map (legal boundary, not today's forecast)", checked: showNfhlZones, set: setShowNfhlZones, swatch: "#d73027" },
              { key: "drainage", label: "Drainage network", checked: showDrainage, set: setShowDrainage, swatch: "#2196f3" },
              { key: "evac", label: "Evacuation routes", checked: showEvacRoutes, set: setShowEvacRoutes, swatch: "#ffd600" },
              { key: "history", label: "Historical events", checked: showHistorical, set: setShowHistorical, swatch: "#8e44ad" },
              { key: "population", label: "Population density", checked: showPopulation, set: setShowPopulation, swatch: "#e67e22" },
              { key: "poi", label: "Flood probability heatmap (chance of any water)", checked: showPoiLayer, set: setShowPoiLayer, swatch: "#d94801" },
            ].map(({ key, label, checked, set, swatch }) => (
              <label key={key} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: "0.72rem", color: "white", cursor: "pointer" }}>
                <input type="checkbox" checked={checked} onChange={(e) => set(e.target.checked)} style={{ accentColor: swatch, cursor: "pointer" }} />
                <span style={{ width: 8, height: 8, borderRadius: "50%", background: swatch, display: "inline-block" }} />
                {label}
              </label>
            ))}
            <button
              onClick={() => { setElevationToolActive((v) => !v); setElevationResult(null); }}
              style={{
                marginTop: 4, padding: "4px 8px", borderRadius: 4, fontSize: "0.7rem", cursor: "pointer",
                border: "1px solid var(--border)", width: "100%",
                background: elevationToolActive ? "#4ea8de" : "transparent",
                color: elevationToolActive ? "black" : "white",
                fontWeight: elevationToolActive ? 700 : 400,
              }}
            >
              📏 {elevationToolActive ? "Elevation tool ON" : "Elevation tool"}
            </button>
          </>
        )}
      </div>

      {/* Legend */}
      <div style={{
        position: "absolute", bottom: 12, left: 12, zIndex: 10,
        background: "rgba(20,26,34,0.9)", borderRadius: 8, padding: legendOpen ? "8px 10px" : "6px 10px",
        fontSize: "0.7rem", color: "white", maxWidth: 220,
      }}>
        <button
          onClick={() => setLegendOpen((v) => !v)}
          style={{
            background: "none", border: "none", cursor: "pointer", padding: 0,
            fontSize: "0.68rem", color: "#aab4c0", fontWeight: 700, letterSpacing: "0.06em",
            display: "flex", alignItems: "center", gap: 4, marginBottom: legendOpen ? 4 : 0,
          }}
        >
          🗺️ LEGEND {legendOpen ? "▾" : "▸"}
        </button>
        {legendOpen && (
        <>
        {/* Flood depth ramp — explains what the blue overlay actually means.
            Matches the Blues colormap the depth rasters are rendered with
            (src/probabilistic/scenarios.py): pale = shallow, dark = deep. */}
        <div style={{ fontWeight: 700, marginBottom: 4, letterSpacing: "0.05em", color: "#aab4c0" }}>
          FLOOD WATER DEPTH
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{
            width: 84, height: 10, borderRadius: 2, display: "inline-block",
            background: "linear-gradient(90deg, #deebf7, #9ecae1, #4292c6, #08519c)",
          }} />
          <span style={{ fontSize: "0.66rem" }}>shallow → deep</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", width: 84, fontSize: "0.6rem", color: "#aab4c0", marginBottom: 8 }}>
          <span>ankle</span><span>waist</span><span>&gt;head</span>
        </div>

        {showPoiLayer && (
          <>
            <div style={{ fontWeight: 700, marginBottom: 4, letterSpacing: "0.05em", color: "#aab4c0" }}>
              FLOOD PROBABILITY
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
              <span style={{
                width: 84, height: 10, borderRadius: 2, display: "inline-block",
                background: "linear-gradient(90deg, #ffffb2, #fd8d3c, #bd0026)",
              }} />
              <span style={{ fontSize: "0.66rem" }}>low → high chance</span>
            </div>
            <div style={{ fontSize: "0.62rem", opacity: 0.75, marginBottom: 8 }}>
              Model-estimated chance of any water today, not a certainty.
            </div>
          </>
        )}

        <div style={{ fontWeight: 700, marginBottom: 4, letterSpacing: "0.05em", color: "#aab4c0" }}>
          ROAD FLOOD SEVERITY
        </div>
        {(["severe", "moderate", "minor", "none"] as const).map((tier) => (
          <div key={tier} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <span style={{ width: 14, height: 3, background: SEVERITY_COLOR[tier], display: "inline-block", borderRadius: 2 }} />
            <span style={{ fontSize: "0.66rem" }}>{SEVERITY_LABEL[tier] ?? "Dry"}</span>
          </div>
        ))}
        <div style={{ fontSize: "0.62rem", opacity: 0.75, marginTop: 2, marginBottom: 8 }}>
          Click a road/building — the % shown is model confidence, not a certainty.
        </div>

        <div style={{ fontWeight: 700, marginBottom: 4, letterSpacing: "0.05em", color: "#aab4c0" }}>
          BUILDING CATEGORY
        </div>
        {Object.entries(CATEGORY_COLOR).filter(([k]) => k !== "Unclassified").map(([label, color]) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: color, display: "inline-block" }} />
            {label}
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "rgba(211,47,47,0.85)", display: "inline-block" }} />
          Critical facility — will flood
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: "50%", background: "rgba(39,174,96,0.85)", display: "inline-block" }} />
          Critical facility — safe
        </div>
        <div style={{ marginTop: 6, opacity: 0.7 }}>Click any building or facility icon for details.</div>
        </>
        )}
      </div>
    </div>
  );
}
