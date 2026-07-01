import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { HistoricalComparison as HistoricalComparisonData } from "../types/api";

export function HistoricalComparison() {
  const [data, setData] = useState<HistoricalComparisonData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<HistoricalComparisonData>("/api/v1/historical-comparison")
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  if (error) return <p>Could not load historical comparison: {error}</p>;
  if (!data) return <p>Loading historical comparison…</p>;

  const { closest_event: event, delta_pct_vs_closest_event: delta } = data;
  const noFlowToday = data.today_discharge_cms === 0;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>Closest historical match</h3>
      <p>
        {noFlowToday ? (
          <>No flow forecasted today — for reference, the smallest documented event is the{" "}</>
        ) : (
          <>Today's forecast discharge (<strong>{data.today_discharge_cms} cms</strong>) is closest to the{" "}</>
        )}
        <strong>{event.name}</strong> ({event.date}) — peak discharge{" "}
        <strong>{event.peak_q_cms} cms</strong>, approx. a {event.approx_return_period_yr}-year event
        {delta !== null && (
          <>
            {" "}(today is {delta >= 0 ? "+" : ""}{delta}% vs. that event)
          </>
        )}
        .
      </p>
      <p style={{ color: "var(--text-secondary)" }}>{event.notes}</p>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", borderTop: "1px solid var(--border)", paddingTop: 8 }}>
        Source: {event.source}. Catalog of {data.catalog_size} documented events — {data.catalog_source}
      </p>
    </div>
  );
}
