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

export interface ActionPlan {
  reference_scenario: string;
  roads_to_barricade: { total_count: number; top: ActionItem[] };
  buildings_to_evacuate: { total_count: number; top: ActionItem[] };
  legal_note: string;
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

export interface MapConfig {
  bbox: { north: number; south: number; east: number; west: number };
  center: { lat: number; lon: number };
  reference_markers: { lat: number; lon: number; label: string }[];
  available_layers: string[];
  available_rasters: string[];
  raster_bounds: Record<string, RasterBounds>;
}
