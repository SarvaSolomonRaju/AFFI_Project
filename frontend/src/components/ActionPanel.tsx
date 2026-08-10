import { useLiveData } from "../hooks/useLiveData";
import type { ActionPlan, ActionItem, BuildingActionItem, SimState } from "../types/api";
import { fmtAcres, fmtFeet } from "../utils/units";
import { StaleBadge } from "./StaleBadge";

function ActionList({
  title,
  items,
  totalCount,
}: {
  title: string;
  items: (ActionItem | BuildingActionItem)[];
  totalCount: number;
}) {
  return (
    <div>
      <h4 style={{ marginBottom: 4 }}>{title} ({totalCount} total)</h4>
      {items.length === 0 ? (
        <p style={{ color: "var(--text-secondary)" }}>None at this reference scenario.</p>
      ) : (
        <ol style={{ paddingLeft: 20, margin: 0 }}>
          {items.map((item, i) => (
            <li key={`${item.name}-${i}`}>
              {item.name}
              {"category" in item && (
                <span style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}> [{item.category}]</span>
              )}
              {" — "}<strong>{fmtFeet(item.max_depth_m, 2)}</strong>
            </li>
          ))}
        </ol>
      )}
      {totalCount > items.length && (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: 4 }}>
          + {totalCount - items.length} more, sorted by depth
        </p>
      )}
    </div>
  );
}

function SimActionPanel({ simState, isSimulationMode }: { simState: SimState; isSimulationMode: boolean }) {
  const ALERT_ACCENT: Record<string, string> = {
    GREEN: "#27ae60", ADVISORY: "#f39c12", WATCH: "#e67e22", WARNING: "#c0392b",
  };
  const accent = ALERT_ACCENT[simState.alert_level] ?? "#e67e22";

  const schoolsNote = simState.alert_level === "WARNING" || simState.alert_level === "WATCH"
    ? "Initiate school evacuation check-list for all schools in the flood zone."
    : "Monitor school status as scenario evolves.";

  const roadAction = simState.alert_level === "WARNING"
    ? `Barricade all ${simState.roads_at_risk} at-risk road segments immediately.`
    : simState.alert_level === "WATCH"
      ? `Pre-barricade highest-risk segments of the ${simState.roads_at_risk} at-risk roads.`
      : `Monitor ${simState.roads_at_risk} road segments — barricade if flooding confirmed.`;

  const buildingAction = simState.alert_level === "WARNING"
    ? `Evacuate all ${simState.infra_at_risk} at-risk buildings. No exceptions.`
    : simState.alert_level === "WATCH"
      ? `Notify occupants of ${simState.infra_at_risk} at-risk buildings. Prepare for evacuation.`
      : `Log ${simState.infra_at_risk} at-risk infrastructure elements for monitoring.`;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>
        Action Plan — {isSimulationMode ? "Simulation" : "Exploring"}: {simState.return_period_yr}-Year Event
        <span style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 400, color: "var(--accent-orange)" }}>
          {isSimulationMode ? "WHAT-IF SCENARIO" : "REFERENCE SCENARIO"}
        </span>
      </h3>

      {/* School alert */}
      <div style={{
        background: simState.alert_level === "WARNING" ? "var(--accent-purple)" : "var(--bg-primary)",
        color: simState.alert_level === "WARNING" ? "white" : "var(--text-secondary)",
        borderRadius: 6,
        padding: "10px 14px",
        marginBottom: 16,
        fontWeight: simState.alert_level === "WARNING" ? 700 : 400,
      }}>
        {schoolsNote}
      </div>

      {/* Aggregate risk counts */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        {[
          {
            title: `${simState.roads_at_risk} roads at risk`,
            body: roadAction,
            icon: "🚧",
          },
          {
            title: `${simState.infra_at_risk} infrastructure items at risk`,
            body: buildingAction,
            icon: "🏚",
          },
        ].map(({ title, body, icon }) => (
          <div key={title} style={{ background: "var(--bg-primary)", borderRadius: 6, padding: "12px 14px", borderLeft: `4px solid ${accent}` }}>
            <div style={{ fontWeight: 700, marginBottom: 4 }}>{icon} {title}</div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>{body}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
        {[
          { label: "Max flood depth", value: fmtFeet(simState.max_depth_m) },
          { label: "Flooded area", value: fmtAcres(simState.wet_area_km2) },
          { label: "Time to peak", value: `~${simState.time_to_peak_p50.toFixed(1)} hrs` },
          { label: "Life-safety risk", value: `${simState.life_safety_pct}%` },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: "var(--bg-primary)", borderRadius: 6, padding: "8px 10px" }}>
            <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{label}</div>
            <div style={{ fontWeight: 700, fontSize: "1.1rem" }}>{value}</div>
          </div>
        ))}
      </div>

      <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 14, borderTop: "1px solid var(--border)", paddingTop: 10, marginBottom: 0 }}>
        Named road and building lists are based on today's live forecast action plan.
        In simulation, aggregate counts are from the pre-computed scenario library.
        For named assets, switch to LIVE FORECAST mode.
      </p>
    </div>
  );
}

interface ActionPanelProps {
  refreshSignal?: number;
  simState?: SimState | null;
  isSimulationMode?: boolean;
}

export function ActionPanel({ refreshSignal, simState, isSimulationMode = false }: ActionPanelProps) {
  const inSimMode = simState !== undefined;
  const { data: plan, error, lastUpdated } = useLiveData<ActionPlan>(
    "/api/v1/action-plan",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  if (inSimMode) {
    if (!simState) {
      return (
        <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
          <h3 style={{ marginTop: 0 }}>Action Plan — {isSimulationMode ? "Simulation" : "Scenario Explorer"}</h3>
          <p style={{ color: "var(--text-secondary)" }}>Increase rainfall above 1" to see simulated action requirements.</p>
        </div>
      );
    }
    return <SimActionPanel simState={simState} isSimulationMode={isSimulationMode} />;
  }

  if (error && !plan) return <p>Could not load action plan: {error}</p>;
  if (!plan) return <p>Loading action plan…</p>;

  const schoolCount = plan.schools_in_flood_zone.length;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>Action Plan — {plan.reference_scenario}</h3>

      <div style={{
        background: schoolCount > 0 ? "var(--accent-purple)" : "var(--bg-primary)",
        color: schoolCount > 0 ? "white" : "var(--text-secondary)",
        borderRadius: 6,
        padding: "10px 14px",
        marginBottom: 16,
        fontWeight: schoolCount > 0 ? 700 : 400,
      }}>
        {schoolCount > 0
          ? `${schoolCount} school${schoolCount === 1 ? "" : "s"} in the flood zone — evacuate first: ${plan.schools_in_flood_zone.map((s) => s.name).join(", ")}`
          : "No schools in the flood zone at this reference scenario."}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <ActionList title="Roads to barricade" items={plan.roads_to_barricade.top} totalCount={plan.roads_to_barricade.total_count} />
        <ActionList title="Buildings to evacuate" items={plan.buildings_to_evacuate.top} totalCount={plan.buildings_to_evacuate.total_count} />
      </div>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
        {plan.legal_note}
      </p>
    </div>
  );
}
