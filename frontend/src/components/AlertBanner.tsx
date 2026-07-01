import { useLiveData } from "../hooks/useLiveData";
import type { CurrentAlert } from "../types/api";

// Maps an alert level to the CSS class defined in theme.css.
function alertClass(level: string): string {
  return `alert-banner alert-${level.toLowerCase()}`;
}

interface AlertBannerProps {
  refreshSignal?: number;
}

export function AlertBanner({ refreshSignal }: AlertBannerProps) {
  const { data: alert, error, lastUpdated } = useLiveData<CurrentAlert>(
    "/api/v1/alert/current",
    60_000,
    refreshSignal,
  );

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
        {lastUpdated && <> · dashboard refreshed {lastUpdated.toLocaleTimeString()}</>}
      </div>
    </div>
  );
}
