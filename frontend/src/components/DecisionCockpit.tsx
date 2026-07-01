import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { DecisionCockpit as DecisionCockpitData } from "../types/api";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ background: "var(--bg-primary)", borderRadius: 6, padding: 12, flex: 1, minWidth: 160 }}>
      <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>{label}</div>
      <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>{sub}</div>}
    </div>
  );
}

export function DecisionCockpit() {
  const [data, setData] = useState<DecisionCockpitData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<DecisionCockpitData>("/api/v1/decision-cockpit")
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  if (error) return <p>Could not load decision cockpit: {error}</p>;
  if (!data) return <p>Loading decision cockpit…</p>;

  const { time_to_peak_hours: ttp, life_safety, uncertainty_m } = data;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>Decision Cockpit</h3>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <Stat
          label="Time to peak flow"
          value={`${ttp.p50.toFixed(1)} hrs`}
          sub={`range ${ttp.p90.toFixed(1)}–${ttp.p10.toFixed(1)} hrs (faster storm = sooner peak)`}
        />
        <Stat
          label="Life-safety threshold"
          value={`${life_safety.prob_gt_0_5m_max_pct}%`}
          sub="chance any area exceeds 0.5 m depth (wading danger)"
        />
        <Stat
          label="Forecast uncertainty"
          value={`± ${uncertainty_m.mean.toFixed(2)} m`}
          sub={`max spread ${uncertainty_m.max.toFixed(2)} m across ensemble`}
        />
      </div>
      <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: 12, marginBottom: 0 }}>
        Method: {ttp.method}
      </p>
    </div>
  );
}
