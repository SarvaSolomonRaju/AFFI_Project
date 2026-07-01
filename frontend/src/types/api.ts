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
