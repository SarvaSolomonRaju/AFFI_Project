// Mirrors the response shapes returned by src/api/server.py.
// Keeping these in sync with the Python side is manual — if you add a
// field in FastAPI, add it here too, or TypeScript won't know it exists.

export type AlertLevel = "GREEN" | "ADVISORY" | "WATCH" | "WARNING";

export interface HealthResponse {
  status: string;
  version: string;
  uptime_seconds: number;
  last_forecast_utc: string | null;
  watershed: string;
}

export interface CurrentAlert {
  current_alert: AlertLevel;
  max_7day_alert: AlertLevel;
  generated_utc: string;
  watershed: Record<string, unknown>;
  data_source: string;
}

export interface ForecastDay {
  day: number;
  date: string;
  p10_24hr: number;
  p50_24hr: number;
  p90_24hr: number;
  alert_level: AlertLevel;
  return_period: {
    nearest_return_period: string;
    severity_class: string;
  };
}

export interface ForecastDaysResponse {
  generated_utc: string;
  forecast_days: ForecastDay[];
}

export interface RasterBounds {
  west: number;
  south: number;
  east: number;
  north: number;
}

export interface SimulationScenario {
  Q_cms: number;
  max_depth_m: number;
  wet_area_km2: number;
  roads_at_risk: number;
  infra_at_risk: number;
  alert_level: AlertLevel | string;
  severity: string;
  probability: string;
  population_exposed: number | null;
  population_life_safety: number | null;
  raster_url: string;
}

export interface SimulationScenariosResponse {
  return_periods_yr: number[];
  scenarios: Record<string, SimulationScenario>;
}

export interface ActionItem {
  name: string;
  max_depth_m: number;
}

export type BuildingCategory =
  | "School"
  | "Public/Civic"
  | "Residential"
  | "Commercial/Industrial"
  | "Agricultural/Outbuilding"
  | "Unclassified";

export interface BuildingActionItem extends ActionItem {
  category: BuildingCategory;
}

export interface ActionPlan {
  reference_scenario: string;
  roads_to_barricade: { total_count: number; top: ActionItem[] };
  buildings_to_evacuate: { total_count: number; top: BuildingActionItem[] };
  schools_in_flood_zone: ActionItem[];
  legal_note: string;
}

export interface FloodFootprintScenario {
  max_depth_m: number;
  wet_area_km2: number;
  total_volume_m3: number;
}

export interface PopulationAtRisk {
  exposed_total: number | null;
  life_safety_p50: number | null;
  life_safety_p90: number | null;
  source: string;
}

export type MapSelectionRegime = "dry" | "below_smallest" | "clipped_above" | "interior";

export interface MapSelection {
  rainfall_in: number;
  discharge_cms: number;
  regime: MapSelectionRegime;
  smallest_return_period_yr: number | null;
  leopold_scale: number | null;
  bracket: {
    low: { return_period_yr: number | null; q_cms: number };
    high: { return_period_yr: number | null; q_cms: number };
    interp_weight: number;
    exact_match: boolean;
  };
  method: string;
}

export interface DecisionCockpit {
  time_to_peak_hours: { p10: number; p50: number; p90: number; method: string };
  life_safety: { prob_gt_0_5m_max_pct: number; wet_pixels_above_0_5m: number };
  uncertainty_m: { max: number; mean: number };
  population: PopulationAtRisk | null;
  discharge_cms: { p10: number; p50: number; p90: number } | null;
  // {return_period_yr: Q_cms} straight from the flood-library manifest —
  // the "flood begins here" horizontal lines on the hydrograph.
  flood_thresholds_cms: Record<string, number> | null;
  map_selection: MapSelection | null;
  flood_footprint: {
    best: FloodFootprintScenario;
    likely: FloodFootprintScenario;
    worst: FloodFootprintScenario;
  };
}

export interface SevenDayEntry {
  day: number;
  date: string;
  alert_level: AlertLevel;
  likely: {
    max_depth_m: number;
    wet_area_km2: number;
    scenario_class: string;
    caption: string;
    thumbnail_url: string;
  };
  worst: {
    max_depth_m: number;
    wet_area_km2: number;
  };
}

export interface SevenDayDetailResponse {
  generated_utc: string;
  days: SevenDayEntry[];
}

export interface HistoricalEvent {
  name: string;
  date: string;
  season: string;
  rainfall_24hr_in: number;
  peak_q_cms: number;
  peak_stage_m: number;
  approx_return_period_yr: number;
  source: string;
  notes: string;
}

export interface HistoricalEventsCatalog {
  watershed: string;
  usgs_gauge: string;
  location: string;
  notes: string;
  events: HistoricalEvent[];
}

export interface HistoricalComparison {
  today_discharge_cms: number;
  closest_event: HistoricalEvent;
  delta_pct_vs_closest_event: number | null;
  catalog_size: number;
  catalog_source: string;
}

export interface Bulletin {
  alert_level: AlertLevel;
  text: string;
}

// Simulation mode state — computed from rainfall input + scenario library
export interface SimState {
  rainfall_in: number;
  return_period_yr: number;
  return_period_best: number;   // adjacent lower scenario (or same if at min)
  return_period_worst: number;  // adjacent higher scenario (or same if at max)
  Q_cms: number;
  max_depth_m: number;
  wet_area_km2: number;
  roads_at_risk: number;
  infra_at_risk: number;
  alert_level: AlertLevel;
  severity: string;
  raster_url: string;
  raster_url_best: string;
  raster_url_worst: string;
  raster_url_thumb: string;
  raster_url_best_thumb: string;
  raster_url_worst_thumb: string;
  time_to_peak_p10: number;
  time_to_peak_p50: number;
  time_to_peak_p90: number;
  life_safety_pct: number;
  population_exposed: number | null;
  population_life_safety: number | null;
}

export interface ModelMetrics {
  task1_metrics: {
    nse: number;
    f1: number;
    auc_roc: number;
    auc_pr: number;
  };
  task2_inference_config: {
    temperature: number;
    method: string;
    threshold: number;
    magnitude_model: string;
    test_nse: number;
    test_pbias: number;
    f1_score: number;
    auc_roc: number;
    auc_pr: number;
    n_lags: number;
    fixes_applied: string[];
    bias_correction: { event_scale: number; applied: boolean };
    xgb_params: Record<string, unknown>;
  };
}

export interface LiveGaugeReading {
  value: number;
  datetime: string;
  provisional: boolean;
}

export interface LiveGaugeResponse {
  pilot_gauge: { id: string; name: string; lat: number; lon: number };
  pilot_gauge_has_telemetry: boolean;
  nearest_live_gauge: { id: string; name: string; lat: number; lon: number };
  distance_note: string;
  readings: {
    discharge_cfs?: LiveGaugeReading;
    gage_height_ft?: LiveGaugeReading;
  };
}

export interface Contact {
  name: string;
  category: string;
  category_label: string;
  address: string | null;
  phone: string | null;
}

export interface ContactRosterResponse {
  contacts: Contact[];
}

export interface RegionalSensor {
  id: string;
  name: string;
  lat: number;
  lon: number;
  distance_mi: number;
  datetime: string | null;
  is_flowing: boolean;
  readings: {
    discharge_cfs?: number;
    gage_height_ft?: number;
    precip_in?: number;
  };
}

export interface RegionalSensorsResponse {
  available: boolean;
  error?: string;
  source: string;
  count?: number;
  any_flowing?: boolean;
  sensors: RegionalSensor[];
}

export interface OfficialAlert {
  event: string;
  severity: string | null;
  urgency: string | null;
  certainty: string | null;
  headline: string | null;
  area: string | null;
  effective: string | null;
  expires: string | null;
  sender: string | null;
  is_flood: boolean;
}

export interface OfficialAlertsResponse {
  available: boolean;
  error?: string;
  source: string;
  point?: string;
  count?: number;
  flood_alert_active?: boolean;
  alerts: OfficialAlert[];
}

export interface VerificationRecord {
  date: string;
  predicted_alert: string;
  predicted_p50_in: number | null;
  predicted_p90_in: number | null;
  observed_mean_cfs: number | null;
  category: "hit" | "miss" | "false_alarm" | "correct_calm" | "pending";
  verdict: string;
}

export interface ForecastVerificationResponse {
  records: VerificationRecord[];
  summary: {
    n_verified: number;
    hits: number;
    misses: number;
    false_alarms: number;
    correct_calm: number;
    hit_rate_pct: number | null;
    false_alarm_rate_pct: number | null;
  };
  self_correction: {
    tendency: string;
    note: string;
    suggested_threshold_delta_in?: number;
  };
  observed_source: { id: string; name: string };
  proxy_note: string;
  observed_event_threshold_cfs: number;
}

export interface ElevationResult {
  lat: number;
  lon: number;
  elevation_m: number | null;
  flood_depth_m: number | null;
  return_period_yr: number | null;
  source: string;
}

export interface MapConfig {
  bbox: { north: number; south: number; east: number; west: number };
  center: { lat: number; lon: number };
  reference_markers: { lat: number; lon: number; label: string }[];
  available_layers: string[];
  available_rasters: string[];
  raster_bounds: Record<string, RasterBounds>;
}
