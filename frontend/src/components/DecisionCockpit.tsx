import { useLiveData } from "../hooks/useLiveData";
import type { DecisionCockpit as DecisionCockpitData, FloodFootprintScenario, SimState } from "../types/api";
import { fmtAcreFt, fmtAcres, fmtCfs, fmtFeet } from "../utils/units";
import { StaleBadge } from "./StaleBadge";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div style={{ background: "var(--bg-primary)", borderRadius: 6, padding: 12, flex: 1, minWidth: 160 }}>
      <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>{label}</div>
      <div style={{ fontSize: "1.4rem", fontWeight: 700 }}>{value}</div>
      {sub && <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>{sub}</div>}
    </div>
  );
}

function FootprintRow({ label, s, highlight }: { label: string; s: FloodFootprintScenario; highlight?: boolean }) {
  return (
    <tr style={{ borderBottom: "1px solid var(--border)", fontWeight: highlight ? 700 : 400 }}>
      <td style={{ padding: "5px 8px", color: "var(--text-secondary)" }}>{label}</td>
      <td style={{ padding: "5px 8px" }}>{fmtFeet(s.max_depth_m, 2)}</td>
      <td style={{ padding: "5px 8px" }}>{fmtAcres(s.wet_area_km2)}</td>
      <td style={{ padding: "5px 8px" }}>{fmtAcreFt(s.total_volume_m3)}</td>
    </tr>
  );
}

// Google Flood Hub's own gauge-status convention: a river reach is labeled
// Normal / Warning / Danger / Extreme by comparing today's discharge to the
// 2-yr / 5-yr / ~20-yr return-period thresholds (their published definition:
// warning ≈ once every 2 yrs, danger ≈ once every 5 yrs, extreme ≈ once every
// 20 yrs). This dashboard's own library doesn't have a 20-yr map, so 25-yr
// (the closest real entry) stands in for it — labeled honestly as such
// rather than silently rounding one figure into the other.
interface GaugeStatus {
  label: string;
  color: string;
  textColor: string;
}

function gaugeStatus(dischargeCms: number, thresholds: Record<string, number> | null | undefined): GaugeStatus | null {
  if (!thresholds || thresholds["2"] == null) return null;
  const t2 = thresholds["2"];
  const t5 = thresholds["5"] ?? t2;
  const t20 = thresholds["25"] ?? thresholds["50"] ?? t5; // closest real entry to Google's 20-yr definition
  if (dischargeCms >= t20) return { label: "EXTREME", color: "#7b241c", textColor: "white" };
  if (dischargeCms >= t5) return { label: "DANGER", color: "var(--status-warning)", textColor: "white" };
  if (dischargeCms >= t2) return { label: "WARNING", color: "var(--status-watch)", textColor: "white" };
  return { label: "NORMAL", color: "var(--status-good)", textColor: "white" };
}

function GaugeStatusBadge({ dischargeCms, thresholds }: { dischargeCms: number; thresholds: Record<string, number> | null | undefined }) {
  const status = gaugeStatus(dischargeCms, thresholds);
  if (!status) return null;
  return (
    <span
      title="Same Normal/Warning/Danger/Extreme convention Google Flood Hub uses — compares today's discharge to the 2/5/~20-yr return-period levels."
      style={{
        marginLeft: 10, padding: "2px 10px", borderRadius: 5, fontSize: "0.72rem", fontWeight: 700,
        letterSpacing: "0.04em", background: status.color, color: status.textColor, verticalAlign: "middle",
      }}
    >
      GAUGE: {status.label}
    </span>
  );
}

interface UrgencyLevel {
  label: string;
  color: string;
  textColor: string;
  actions: string[];
}

function getUrgency(lifeSafetyPct: number, ttpP50: number): UrgencyLevel {
  if (lifeSafetyPct === 0) {
    return {
      label: "MONITOR",
      color: "var(--status-good)",
      textColor: "white",
      actions: [
        "Normal operations — no flooding expected",
        "Check forecast every 60 min during active weather",
        "Verify evacuation routes and equipment are accessible",
      ],
    };
  }
  if (ttpP50 > 4 || lifeSafetyPct < 15) {
    return {
      label: "PREPARE",
      color: "var(--status-advisory)",
      textColor: "black",
      actions: [
        "Alert emergency crews and stage barricades",
        "Notify school district and EOC of elevated threat",
        "Pre-position high-water rescue equipment",
      ],
    };
  }
  if (ttpP50 > 2 || lifeSafetyPct < 50) {
    return {
      label: "DEPLOY",
      color: "var(--status-watch)",
      textColor: "white",
      actions: [
        "Close highest-risk roads now (see Action Plan below)",
        "Begin school and vulnerable-population evacuation",
        "Issue public Flash Flood Watch notification",
      ],
    };
  }
  return {
    label: "EXECUTE — IMMEDIATE ACTION",
    color: "var(--status-warning)",
    textColor: "white",
    actions: [
      "Mandatory evacuation of ALL listed buildings NOW",
      "Barricade every flagged road — no exceptions",
      "Deploy water rescue, activate county EOC at full staff",
    ],
  };
}

function ConfidenceFramework({ isSim }: { isSim: boolean }) {
  return (
    <div style={{ marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 12, fontSize: "0.8rem" }}>
      <div style={{ fontWeight: 600, marginBottom: 6, color: "var(--text-secondary)" }}>
        {isSim ? "Simulation confidence context" : "Forecast confidence by lead time"}
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {([
          { range: "2–7 days", source: isSim ? "Scenario library" : "GFS ensemble", conf: isSim ? "Deterministic" : "Low–Medium", use: isSim ? "Pre-event planning, budget estimates, EOC briefings" : "Pre-positioning resources, early briefings", active: true },
          { range: "6–24 hrs",  source: "HRRR + GFS",  conf: "Medium–High", use: "Road closure decisions, evacuation planning", active: false },
          { range: "0–6 hrs",   source: "MRMS nowcast", conf: "High",        use: "Active road closures, emergency response",  active: false },
        ] as const).map((row) => (
          <div
            key={row.range}
            style={{
              flex: 1,
              minWidth: 160,
              background: row.active ? "rgba(78,168,222,0.12)" : "var(--bg-primary)",
              border: row.active ? "1px solid var(--accent-blue)" : "1px solid var(--border)",
              borderRadius: 6,
              padding: "8px 10px",
              opacity: row.active ? 1 : 0.5,
            }}
          >
            <div style={{ fontWeight: row.active ? 700 : 400, color: row.active ? "var(--accent-blue)" : "var(--text-secondary)" }}>
              {row.range} {row.active && "← current"}
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>{row.source}</div>
            <div style={{ fontWeight: 600, marginTop: 2 }}>Confidence: {row.conf}</div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem", marginTop: 2 }}>{row.use}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

interface DecisionCockpitProps {
  refreshSignal?: number;
  simState?: SimState | null;
  isSimulationMode?: boolean;
}

export function DecisionCockpit({ refreshSignal, simState, isSimulationMode = false }: DecisionCockpitProps) {
  const inSimMode = simState !== undefined;
  const scenarioLabel = isSimulationMode ? "SIMULATION" : "EXPLORING SCENARIO";
  const { data, error, lastUpdated } = useLiveData<DecisionCockpitData>(
    "/api/v1/decision-cockpit",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  if (inSimMode) {
    if (!simState) {
      return (
        <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
          <h3 style={{ marginTop: 0 }}>Decision Cockpit — {isSimulationMode ? "Simulation" : "Scenario Explorer"}</h3>
          <p style={{ color: "var(--text-secondary)" }}>Increase rainfall above 1" to see simulated decision metrics.</p>
        </div>
      );
    }

    const urgency = getUrgency(simState.life_safety_pct, simState.time_to_peak_p50);

    return (
      <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
        <h3 style={{ marginTop: 0 }}>
          Decision Cockpit
          <span style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 400, color: "var(--accent-orange)" }}>
            {scenarioLabel} — {simState.return_period_yr}-YR EVENT
          </span>
        </h3>

        <div style={{ background: urgency.color, color: urgency.textColor, borderRadius: 8, padding: "12px 16px", marginBottom: 16 }}>
          <div style={{ fontWeight: 700, fontSize: "1.1rem", marginBottom: 6 }}>
            {urgency.label}
            <span style={{ fontWeight: 400, fontSize: "0.9rem", marginLeft: 12 }}>
              Peak in ~{simState.time_to_peak_p50.toFixed(1)} hrs (range {simState.time_to_peak_p90.toFixed(1)}–{simState.time_to_peak_p10.toFixed(1)} hrs)
            </span>
          </div>
          <ol style={{ margin: 0, paddingLeft: 20 }}>
            {urgency.actions.map((a) => <li key={a} style={{ marginBottom: 2 }}>{a}</li>)}
          </ol>
        </div>

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
          <Stat
            label="Time to peak flow"
            value={`${simState.time_to_peak_p50.toFixed(1)} hrs`}
            sub={`range ${simState.time_to_peak_p90.toFixed(1)}–${simState.time_to_peak_p10.toFixed(1)} hrs`}
          />
          <Stat
            label="Life-safety threshold"
            value={`${simState.life_safety_pct}%`}
            sub="chance any area exceeds 1.6 ft depth (wading danger)"
          />
          <Stat
            label="Peak discharge"
            value={fmtCfs(simState.Q_cms)}
            sub={`${simState.return_period_yr}-year return period`}
          />
          <Stat
            label="Population at risk"
            value={simState.population_life_safety !== null ? simState.population_life_safety.toLocaleString() : "n/a"}
            sub={simState.population_exposed !== null ? `${simState.population_exposed.toLocaleString()} total in flood extent` : "WorldPop source missing"}
          />
        </div>

        {/* Footprint table */}
        <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginBottom: 6 }}>
          Simulated flood footprint for this scenario
        </div>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-secondary)", fontSize: "0.8rem" }}>
              <th style={{ padding: "4px 8px", textAlign: "left" }}>Metric</th>
              <th style={{ padding: "4px 8px", textAlign: "left" }}>Value</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={{ padding: "5px 8px", color: "var(--text-secondary)" }}>Max depth</td>
              <td style={{ padding: "5px 8px", fontWeight: 700 }}>{fmtFeet(simState.max_depth_m, 2)}</td>
            </tr>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={{ padding: "5px 8px", color: "var(--text-secondary)" }}>Inundated area</td>
              <td style={{ padding: "5px 8px", fontWeight: 700 }}>{fmtAcres(simState.wet_area_km2)}</td>
            </tr>
            <tr style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={{ padding: "5px 8px", color: "var(--text-secondary)" }}>Roads at risk</td>
              <td style={{ padding: "5px 8px", fontWeight: 700 }}>{simState.roads_at_risk}</td>
            </tr>
            <tr>
              <td style={{ padding: "5px 8px", color: "var(--text-secondary)" }}>Infrastructure at risk</td>
              <td style={{ padding: "5px 8px", fontWeight: 700 }}>{simState.infra_at_risk}</td>
            </tr>
          </tbody>
        </table>

        <ConfidenceFramework isSim />
      </div>
    );
  }

  if (error && !data) return <p>Could not load decision cockpit: {error}</p>;
  if (!data) return <p>Loading decision cockpit…</p>;

  const { time_to_peak_hours: ttp, life_safety, uncertainty_m, flood_footprint: fp } = data;
  const urgency = getUrgency(life_safety.prob_gt_0_5m_max_pct, ttp.p50);

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>
        Decision Cockpit
        {data.discharge_cms && (
          <GaugeStatusBadge dischargeCms={data.discharge_cms.p50} thresholds={data.flood_thresholds_cms} />
        )}
      </h3>

      <div style={{ background: urgency.color, color: urgency.textColor, borderRadius: 8, padding: "12px 16px", marginBottom: 16 }}>
        <div style={{ fontWeight: 700, fontSize: "1.1rem", marginBottom: 6 }}>
          {urgency.label}
          {life_safety.prob_gt_0_5m_max_pct > 0 && (
            <span style={{ fontWeight: 400, fontSize: "0.9rem", marginLeft: 12 }}>
              Peak arrives in ~{ttp.p50.toFixed(1)} hrs (range {ttp.p90.toFixed(1)}–{ttp.p10.toFixed(1)} hrs)
            </span>
          )}
        </div>
        <ol style={{ margin: 0, paddingLeft: 20 }}>
          {urgency.actions.map((a) => <li key={a} style={{ marginBottom: 2 }}>{a}</li>)}
        </ol>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
        <Stat label="Time to peak flow" value={`${ttp.p50.toFixed(1)} hrs`} sub={`range ${ttp.p90.toFixed(1)}–${ttp.p10.toFixed(1)} hrs`} />
        <Stat label="Life-safety threshold" value={`${life_safety.prob_gt_0_5m_max_pct}%`} sub="chance any area exceeds 1.6 ft depth" />
        <Stat label="Forecast uncertainty" value={`± ${fmtFeet(uncertainty_m.mean, 2)}`} sub={`max spread ${fmtFeet(uncertainty_m.max, 2)}`} />
        {data.population && (
          <Stat
            label="Population at risk"
            value={data.population.life_safety_p90 !== null ? data.population.life_safety_p90.toLocaleString() : "n/a"}
            sub={data.population.exposed_total !== null ? `${data.population.exposed_total.toLocaleString()} total exposed (P90 worst-case)` : "WorldPop source missing"}
          />
        )}
      </div>

      {fp && (
        <div>
          <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem", marginBottom: 6 }}>
            Today's flood footprint (P10 best-case → P50 likely → P90 worst-case)
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-secondary)", fontSize: "0.8rem" }}>
                <th style={{ padding: "4px 8px", textAlign: "left" }}>Scenario</th>
                <th style={{ padding: "4px 8px", textAlign: "left" }}>Max depth</th>
                <th style={{ padding: "4px 8px", textAlign: "left" }}>Wet area</th>
                <th style={{ padding: "4px 8px", textAlign: "left" }}>Volume</th>
              </tr>
            </thead>
            <tbody>
              <FootprintRow label="Best (P10)" s={fp.best} />
              <FootprintRow label="Likely (P50)" s={fp.likely} highlight />
              <FootprintRow label="Worst (P90)" s={fp.worst} />
            </tbody>
          </table>
        </div>
      )}

      <ConfidenceFramework isSim={false} />

      <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: 10, marginBottom: 0 }}>
        Hydrologic method: {ttp.method}
      </p>
    </div>
  );
}
