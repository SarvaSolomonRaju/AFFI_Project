import { useLiveData } from "../hooks/useLiveData";
import type { ForecastDaysResponse } from "../types/api";
import { StaleBadge } from "./StaleBadge";

// Small colored pill for the alert level — reuses the same class names
// as AlertBanner's alert-green/advisory/watch/warning, just smaller.
function AlertPill({ level }: { level: string }) {
  return (
    <span
      className={`alert-${level.toLowerCase()}`}
      style={{ padding: "2px 8px", borderRadius: 4, fontSize: "0.8rem", fontWeight: 600 }}
    >
      {level}
    </span>
  );
}

interface ForecastTableProps {
  refreshSignal?: number;
}

export function ForecastTable({ refreshSignal }: ForecastTableProps) {
  const { data, error, lastUpdated } = useLiveData<ForecastDaysResponse>(
    "/api/v1/forecast/days",
    60_000,
    refreshSignal,
  );
  const days = data?.forecast_days ?? null;

  if (error && !days) return <p>Could not load forecast: {error}</p>;
  if (!days) return <p>Loading 7-day forecast…</p>;

  return (
    <>
    {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
    <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 20 }}>
      <thead>
        <tr style={{ textAlign: "left", borderBottom: "1px solid var(--border)" }}>
          <th>Date</th>
          <th>P10 (in)</th>
          <th>P50 (in)</th>
          <th>P90 (in)</th>
          <th>Return period</th>
          <th>Alert</th>
        </tr>
      </thead>
      <tbody>
        {/* .map() turns each array item into a table row — React needs
            a unique "key" per row so it can tell rows apart when the
            data changes (same idea as a primary key in a database). */}
        {days.map((d) => (
          <tr key={d.day} style={{ borderBottom: "1px solid var(--border)" }}>
            <td>{d.date}</td>
            <td>{d.p10_24hr.toFixed(2)}</td>
            <td>{d.p50_24hr.toFixed(2)}</td>
            <td>{d.p90_24hr.toFixed(2)}</td>
            <td>{d.return_period.nearest_return_period}</td>
            <td><AlertPill level={d.alert_level} /></td>
          </tr>
        ))}
      </tbody>
    </table>
    </>
  );
}
