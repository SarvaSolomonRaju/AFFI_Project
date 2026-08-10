import { useLiveData } from "../hooks/useLiveData";
import type { DecisionCockpit as DecisionCockpitData, SimState } from "../types/api";
import { cmsToCfs } from "../utils/units";
import { Hydrograph } from "./Hydrograph";

interface EnsembleHydrographProps {
  refreshSignal?: number;
  simState?: SimState | null;
  isSimulationMode?: boolean;
}

// Which return-period lines to draw as flood thresholds, and their color —
// the Google Flood Hub palette convention: rising severity from caution to
// danger. Only these few so the chart isn't a ladder of 8 lines.
const THRESHOLD_SPEC: { rp: string; label: string; color: string }[] = [
  { rp: "2", label: "Flood begins (2-yr)", color: "#f39c12" },
  { rp: "10", label: "Moderate (10-yr)", color: "#e67e22" },
  { rp: "50", label: "Major (50-yr)", color: "#e34948" },
  { rp: "100", label: "Severe (100-yr)", color: "#b5382a" },
];

function buildThresholds(map: Record<string, number> | null | undefined) {
  if (!map) return undefined;
  return THRESHOLD_SPEC
    .filter((s) => map[s.rp] != null)
    .map((s) => ({ label: s.label, cfs: cmsToCfs(map[s.rp]), color: s.color }))
    .sort((a, b) => a.cfs - b.cfs);
}

export function EnsembleHydrograph({ refreshSignal, simState, isSimulationMode = false }: EnsembleHydrographProps) {
  const inSimMode = simState !== undefined;
  const { data } = useLiveData<DecisionCockpitData>(
    "/api/v1/decision-cockpit",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  // Thresholds come from the live cockpit fetch (flood_thresholds_cms) — real
  // return-period discharges from the flood-library manifest.
  const thresholds = buildThresholds(data?.flood_thresholds_cms);

  if (inSimMode) {
    if (!simState) {
      return (
        <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
          <h3 style={{ marginTop: 0 }}>{isSimulationMode ? "Simulated" : "Scenario"} water-flow timeline</h3>
          <p style={{ color: "var(--text-secondary)" }}>Increase rainfall above 1" to see the water-flow timeline.</p>
        </div>
      );
    }
    return (
      <Hydrograph
        title={`${isSimulationMode ? "Simulated" : "Scenario"} water-flow timeline — ${simState.return_period_yr}-yr event`}
        subtitle="How river flow at the Sonoita Creek outlet rises and falls over the next 24 hours. Dashed lines = flood levels."
        q50_cms={simState.Q_cms}
        ttpP50={simState.time_to_peak_p50}
        ttpP10={simState.time_to_peak_p10}
        ttpP90={simState.time_to_peak_p90}
        thresholds={thresholds}
      />
    );
  }

  if (!data || !data.discharge_cms) {
    return (
      <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
        <h3 style={{ marginTop: 0 }}>Water-flow timeline (next 24 hours)</h3>
        <p style={{ color: "var(--text-secondary)" }}>Loading…</p>
      </div>
    );
  }

  const ttp = data.time_to_peak_hours;
  return (
    <Hydrograph
      title="Water-flow timeline — next 24 hours"
      subtitle="How river flow at the Sonoita Creek outlet is expected to rise and fall today. Dashed lines = flood levels (like Google Flood Hub)."
      q50_cms={data.discharge_cms.p50}
      ttpP50={ttp.p50}
      ttpP10={ttp.p10}
      ttpP90={ttp.p90}
      thresholds={thresholds}
    />
  );
}
