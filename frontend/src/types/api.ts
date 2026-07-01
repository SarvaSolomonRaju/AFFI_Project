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

export interface MapConfig {
  bbox: { north: number; south: number; east: number; west: number };
  center: { lat: number; lon: number };
  reference_markers: { lat: number; lon: number; label: string }[];
  available_layers: string[];
  available_rasters: string[];
  raster_bounds: Record<string, RasterBounds>;
}
