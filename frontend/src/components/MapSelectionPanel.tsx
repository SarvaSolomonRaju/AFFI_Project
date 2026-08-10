import { useLiveData } from "../hooks/useLiveData";
import type { DecisionCockpit as DecisionCockpitData, MapSelection, SimState } from "../types/api";
import { cmsToCfs } from "../utils/units";
import { StaleBadge } from "./StaleBadge";

// The rainfall -> discharge -> nearest-library-map lookup already runs on
// every forecast; this panel just makes it VISIBLE. Without it the map
// simply appeared, with no way to see that an intelligent "pull the closest
// pre-built map for this rainfall" step happened (which is the whole point
// of a discharge-indexed flood library).

function Step({ n, label, value, sub }: { n: number; label: string; value: string; sub?: string }) {
  return (
    <div style={{ flex: 1, minWidth: 150, background: "var(--bg-primary)", borderRadius: 8, padding: "10px 14px" }}>
      <div style={{ fontSize: "0.68rem", color: "var(--accent-blue)", fontWeight: 700, letterSpacing: "0.06em", marginBottom: 4 }}>
        STEP {n}
      </div>
      <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>{label}</div>
      <div style={{ fontSize: "1.3rem", fontWeight: 800, lineHeight: 1.15 }}>{value}</div>
      {sub && <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function Arrow({ label }: { label: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minWidth: 90, padding: "0 4px" }}>
      <div style={{ fontSize: "1.3rem", color: "var(--accent-blue)", lineHeight: 1 }}>→</div>
      <div style={{ fontSize: "0.64rem", color: "var(--text-secondary)", textAlign: "center", marginTop: 2 }}>{label}</div>
    </div>
  );
}

function matchedMapText(sel: MapSelection): { value: string; sub: string } {
  if (sel.regime === "dry") {
    return { value: "No map — dry", sub: "zero discharge → creek stays in-channel, no flooding" };
  }
  if (sel.regime === "below_smallest") {
    // Honest: NOT dry. The library extrapolates down from the smallest
    // stored map with Leopold depth scaling, so real (reduced) depth shows.
    return {
      value: `sub-${sel.smallest_return_period_yr}-yr`,
      sub: `below the smallest stored map — depth scaled down from the ${sel.smallest_return_period_yr}-yr map${sel.leopold_scale !== null ? ` (×${sel.leopold_scale.toFixed(2)}, Leopold)` : ""}`,
    };
  }
  if (sel.regime === "clipped_above") {
    return { value: `${sel.bracket.high.return_period_yr}-yr map`, sub: "discharge exceeds the largest library map — capped at the most extreme available" };
  }
  const { low, high, interp_weight } = sel.bracket;
  if (sel.bracket.exact_match) {
    // weight fully on the high end (rare, interior exact boundary) -> that's
    // the matched map; otherwise it's the low one.
    const rp = interp_weight >= 0.999 ? high.return_period_yr : low.return_period_yr;
    return { value: `${rp}-yr map`, sub: "exact match to a stored return-period map" };
  }
  const pct = Math.round(interp_weight * 100);
  return {
    value: `${low.return_period_yr}yr ↔ ${high.return_period_yr}yr`,
    sub: `interpolated ${pct}% toward the ${high.return_period_yr}-yr map`,
  };
}

function Panel({ sel }: { sel: MapSelection }) {
  const matched = matchedMapText(sel);
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "stretch" }}>
      <Step n={1} label="Forecast rainfall (24 hr)" value={`${sel.rainfall_in.toFixed(2)}"`} />
      <Arrow label="SCS Curve-Number" />
      <Step n={2} label="Predicted peak discharge" value={`${Math.round(cmsToCfs(sel.discharge_cms)).toLocaleString()} cfs`} sub={`${sel.discharge_cms.toFixed(0)} cms`} />
      <Arrow label="library lookup" />
      <Step n={3} label="Closest pre-built map" value={matched.value} sub={matched.sub} />
    </div>
  );
}

interface MapSelectionPanelProps {
  refreshSignal?: number;
  simState?: SimState | null;
  isSimulationMode?: boolean;
}

export function MapSelectionPanel({ refreshSignal, simState, isSimulationMode = false }: MapSelectionPanelProps) {
  const inSimMode = simState !== undefined;
  const { data, error, lastUpdated } = useLiveData<DecisionCockpitData>(
    "/api/v1/decision-cockpit",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  const label = isSimulationMode ? "Simulation" : inSimMode ? "Exploring scenario" : "Today's live forecast";

  // Sim / explore: the rainfall slider snaps to a return period, so the
  // selection is an exact match to that stored map — build the same
  // provenance shape client-side from simState (which already carries
  // rainfall_in, Q_cms, return_period_yr).
  if (inSimMode) {
    if (!simState) {
      return (
        <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
          <h3 style={{ marginTop: 0 }}>How this map was selected — {label}</h3>
          <p style={{ color: "var(--text-secondary)" }}>Increase rainfall above 1" to see which library map gets pulled.</p>
        </div>
      );
    }
    const sel: MapSelection = {
      rainfall_in: simState.rainfall_in,
      discharge_cms: simState.Q_cms,
      regime: "interior",
      smallest_return_period_yr: null,
      leopold_scale: null,
      bracket: {
        low: { return_period_yr: simState.return_period_yr, q_cms: simState.Q_cms },
        high: { return_period_yr: simState.return_period_yr, q_cms: simState.Q_cms },
        interp_weight: 0,
        exact_match: true,
      },
      method: "",
    };
    return (
      <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
        <h3 style={{ marginTop: 0 }}>
          How this map was selected
          <span style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 400, color: "var(--accent-orange)" }}>{label}</span>
        </h3>
        <Panel sel={sel} />
      </div>
    );
  }

  if (error && !data) return <p>Could not load map-selection detail: {error}</p>;
  if (!data) return <p>Loading map-selection detail…</p>;
  if (!data.map_selection) return null;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>
        How this map was selected
        <span style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 400, color: "var(--accent-blue)" }}>{label}</span>
      </h3>
      <Panel sel={data.map_selection} />
      <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: 12, marginBottom: 0 }}>
        {data.map_selection.method}
      </p>
    </div>
  );
}
