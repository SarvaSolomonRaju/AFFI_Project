import { useLiveData } from "../hooks/useLiveData";
import type { RegionalSensorsResponse, RegionalSensor } from "../types/api";
import { StaleBadge } from "./StaleBadge";

// Every real-time USGS gauge around the watershed, so a manager sees the
// whole regional picture — which creeks upstream are already running, where
// rain is falling — not just one point. All live, all public USGS data.

function Reading({ label, value, unit, strong }: { label: string; value: number | undefined; unit: string; strong?: boolean }) {
  if (value === undefined) return null;
  return (
    <span style={{ display: "inline-flex", flexDirection: "column", minWidth: 78 }}>
      <span style={{ fontSize: "0.66rem", color: "var(--text-secondary)" }}>{label}</span>
      <span style={{ fontSize: "0.95rem", fontWeight: 700, color: strong && value > 0 ? "#4ea8de" : "var(--text-primary)" }}>
        {value.toLocaleString(undefined, { maximumFractionDigits: 2 })} {unit}
      </span>
    </span>
  );
}

function SensorRow({ s }: { s: RegionalSensor }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap",
      background: "var(--bg-primary)", borderRadius: 8, padding: "9px 12px",
      borderLeft: `4px solid ${s.is_flowing ? "#4ea8de" : "#3a4a5a"}`,
    }}>
      <span style={{ fontSize: "1rem" }} title={s.is_flowing ? "Water flowing / rain now" : "Quiet"}>
        {s.is_flowing ? "🌊" : "○"}
      </span>
      <div style={{ flex: 1, minWidth: 180 }}>
        <div style={{ fontWeight: 600, fontSize: "0.88rem" }}>{s.name}</div>
        <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
          USGS {s.id} · {s.distance_mi} mi from Patagonia
        </div>
      </div>
      <Reading label="Flow" value={s.readings.discharge_cfs} unit="cfs" strong />
      <Reading label="Water height" value={s.readings.gage_height_ft} unit="ft" />
      <Reading label="Rain" value={s.readings.precip_in} unit="in" strong />
    </div>
  );
}

export function RegionalSensorsPanel({ refreshSignal }: { refreshSignal?: number }) {
  const { data, error, lastUpdated } = useLiveData<RegionalSensorsResponse>(
    "/api/v1/regional-sensors",
    120_000,
    refreshSignal,
  );

  if (!data) return null;
  if (!data.available) {
    return (
      <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
        <h3 style={{ marginTop: 0 }}>Regional Sensor Network</h3>
        <p style={{ color: "var(--text-secondary)" }}>USGS sensor network unreachable right now: {data.error}</p>
      </div>
    );
  }

  const flowing = data.sensors.filter((s) => s.is_flowing);

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>
        Regional Sensor Network
        <span style={{ marginLeft: 10, fontSize: "0.72rem", fontWeight: 400, color: "var(--accent-blue)" }}>
          {data.count} live USGS gauges
        </span>
      </h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 12px" }}>
        Every real-time gauge around the watershed. <span style={{ color: "#4ea8de" }}>🌊 = water flowing or rain right now.</span>{" "}
        Upstream gauges running is your earliest warning that water is on the way.
        {data.any_flowing
          ? ` Right now ${flowing.length} of ${data.count} gauge${flowing.length === 1 ? " is" : "s are"} active.`
          : " Right now all gauges are quiet."}
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {data.sensors.map((s) => <SensorRow key={s.id} s={s} />)}
      </div>
      <p style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: 10, marginBottom: 0 }}>
        Live from USGS NWIS (waterservices.usgs.gov), no API key.
        {lastUpdated && ` Refreshed ${lastUpdated.toLocaleTimeString()}.`}
      </p>
    </div>
  );
}
