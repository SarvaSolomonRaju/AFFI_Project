import { useLiveData } from "../hooks/useLiveData";
import type { LiveGaugeResponse } from "../types/api";
import { StaleBadge } from "./StaleBadge";

// The pilot watershed's own gauge (USGS 09481500, Sonoita Creek near
// Patagonia) has no real-time telemetry — confirmed directly against
// waterservices.usgs.gov (zero instantaneous-value series for any period).
// This panel shows the nearest gauge that DOES broadcast live (Santa Cruz
// River near Nogales, ~13 miles downstream, same river system) — always
// labeled as such, never presented as if it were the pilot creek's own
// reading. Real IoT/sensor data; honest about which gauge it's from.
export function LiveGaugePanel({ refreshSignal }: { refreshSignal?: number }) {
  const { data, error, lastUpdated } = useLiveData<LiveGaugeResponse>("/api/v1/live-gauge", 120_000, refreshSignal);

  if (error && !data) {
    return (
      <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
        <h3 style={{ marginTop: 0 }}>Live Sensor Data</h3>
        <p style={{ color: "var(--text-secondary)" }}>USGS live telemetry unavailable right now: {error}</p>
      </div>
    );
  }
  if (!data) return null;

  const { discharge_cfs, gage_height_ft } = data.readings;
  const readingAgeMin = discharge_cfs
    ? (Date.now() - new Date(discharge_cfs.datetime).getTime()) / 60000
    : gage_height_ft
    ? (Date.now() - new Date(gage_height_ft.datetime).getTime()) / 60000
    : null;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>
        Live Sensor Data
        <span style={{ marginLeft: 10, fontSize: "0.72rem", fontWeight: 400, color: "var(--accent-blue)" }}>
          USGS real-time telemetry
        </span>
      </h3>

      <div style={{
        background: "rgba(243,156,18,0.10)", border: "1px solid var(--accent-orange)",
        borderRadius: 6, padding: "8px 12px", marginBottom: 14, fontSize: "0.8rem",
      }}>
        The pilot gauge itself (<strong>{data.pilot_gauge.name}</strong>, USGS {data.pilot_gauge.id}) has no
        real-time telemetry equipment — common for small ephemeral-wash gauges. Showing the nearest gauge that
        IS live: <strong>{data.nearest_live_gauge.name}</strong> (USGS {data.nearest_live_gauge.id}),{" "}
        {data.distance_note}.
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        {discharge_cfs && (
          <div style={{ background: "var(--bg-primary)", borderRadius: 6, padding: 12, flex: 1, minWidth: 160 }}>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>Discharge</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{discharge_cfs.value.toFixed(1)} cfs</div>
            {discharge_cfs.provisional && (
              <div style={{ color: "var(--text-secondary)", fontSize: "0.72rem" }}>Provisional — subject to revision</div>
            )}
          </div>
        )}
        {gage_height_ft && (
          <div style={{ background: "var(--bg-primary)", borderRadius: 6, padding: 12, flex: 1, minWidth: 160 }}>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>Gage height</div>
            <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{gage_height_ft.value.toFixed(2)} ft</div>
            {gage_height_ft.provisional && (
              <div style={{ color: "var(--text-secondary)", fontSize: "0.72rem" }}>Provisional — subject to revision</div>
            )}
          </div>
        )}
      </div>

      <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: 10, marginBottom: 0 }}>
        {readingAgeMin !== null && `Reading is ${readingAgeMin.toFixed(0)} min old`}
        {lastUpdated && ` · dashboard refreshed ${lastUpdated.toLocaleTimeString()}`}
        {" "}· Source: USGS NWIS Instantaneous Values Service (waterservices.usgs.gov), no API key required.
      </p>
    </div>
  );
}
