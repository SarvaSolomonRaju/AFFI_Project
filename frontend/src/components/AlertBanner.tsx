import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { CurrentAlert } from "../types/api";

// Maps an alert level to the CSS class defined in theme.css.
function alertClass(level: string): string {
  return `alert-banner alert-${level.toLowerCase()}`;
}

export function AlertBanner() {
  // alert: what we got back from the API, once it arrives (starts as null)
  // error: set if the fetch failed (e.g. backend not running)
  const [alert, setAlert] = useState<CurrentAlert | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Runs once when the component first appears on screen ([] = "no
  // dependencies, don't re-run"). This is where the real network call
  // to your FastAPI backend happens.
  useEffect(() => {
    apiGet<CurrentAlert>("/api/v1/alert/current")
      .then(setAlert)
      .catch((err) => setError(String(err)));
  }, []);

  if (error) {
    return (
      <div className="alert-banner alert-warning">
        Could not reach the backend: {error}
        <br />
        Is it running? (<code>make serve-api</code>)
      </div>
    );
  }

  if (!alert) {
    return <div className="alert-banner">Loading current alert…</div>;
  }

  return (
    <div className={alertClass(alert.current_alert)}>
      Current alert: <strong>{alert.current_alert}</strong>
      <div style={{ fontSize: "0.85rem", fontWeight: 400, marginTop: 4 }}>
        7-day max: {alert.max_7day_alert} · generated {alert.generated_utc} ·
        source: {alert.data_source}
      </div>
    </div>
  );
}
