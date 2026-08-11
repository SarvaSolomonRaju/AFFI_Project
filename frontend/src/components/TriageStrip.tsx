import { useLiveData } from "../hooks/useLiveData";
import type { CurrentAlert, DecisionCockpit as CockpitData } from "../types/api";
import { InfoTip } from "./InfoTip";

/**
 * The 3-second answer row. Research on emergency-operations dashboards is
 * consistent: the operator must grasp the whole situation the instant the
 * screen loads, before scrolling anything. This strip sits directly under
 * the alert banner and answers the four questions a flood manager actually
 * asks — how bad, how long do I have, who could die, what do I do — in
 * plain language, pulling from the same live endpoints the panels below use.
 *
 * Live mode only; hidden during what-if simulation.
 */

const LEVEL_ACTION: Record<string, { action: string; tone: string }> = {
  GREEN:    { action: "Normal operations — keep monitoring the forecast.", tone: "var(--status-good)" },
  ADVISORY: { action: "Stay alert — brief staff, check equipment & routes.", tone: "var(--status-advisory)" },
  WATCH:    { action: "Prepare — stage barricades, ready rescue crews.", tone: "var(--status-watch)" },
  WARNING:  { action: "Act now — close roads and begin evacuation.", tone: "var(--status-warning)" },
};

function levelStyle(level: string): { bg: string; ink: string; fill: string } {
  const l = (level || "").toUpperCase();
  if (l === "WARNING") return { bg: "var(--status-warning-bg)", ink: "var(--status-warning-ink)", fill: "var(--status-warning)" };
  if (l === "WATCH")   return { bg: "var(--status-watch-bg)",   ink: "var(--status-watch-ink)",   fill: "var(--status-watch)" };
  if (l === "ADVISORY")return { bg: "var(--status-advisory-bg)",ink: "var(--status-advisory-ink)",fill: "var(--status-advisory)" };
  return { bg: "var(--status-good-bg)", ink: "var(--status-good-ink)", fill: "var(--status-good)" };
}

function Cell({ label, tip, children, sub, accent }: {
  label: string; tip?: React.ReactNode; children: React.ReactNode; sub?: string; accent?: string;
}) {
  return (
    <div style={{
      background: "var(--bg-card)", border: "1px solid var(--border)", borderTop: `3px solid ${accent ?? "var(--border-strong)"}`,
      borderRadius: "var(--radius)", padding: "12px 14px", boxShadow: "var(--shadow-card)", minWidth: 0,
    }}>
      <div style={{ fontSize: "var(--text-2xs)", fontWeight: 800, letterSpacing: "0.09em", textTransform: "uppercase", color: "var(--text-secondary)", display: "flex", alignItems: "center", gap: 4, marginBottom: 6 }}>
        {label}{tip}
      </div>
      <div style={{ fontSize: "1.5rem", fontWeight: 800, lineHeight: 1.05, color: "var(--text-primary)" }}>{children}</div>
      {sub && <div style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)", marginTop: 4, lineHeight: 1.3 }}>{sub}</div>}
    </div>
  );
}

export function TriageStrip({ refreshSignal }: { refreshSignal?: number }) {
  const { data: alert } = useLiveData<CurrentAlert>("/api/v1/alert/current", 60_000, refreshSignal);
  const { data: cockpit } = useLiveData<CockpitData>("/api/v1/decision-cockpit", 60_000, refreshSignal);

  if (!alert) return null;

  const level = alert.current_alert;
  const ls = levelStyle(level);
  const act = LEVEL_ACTION[level] ?? LEVEL_ACTION.GREEN;

  const ttp = cockpit?.time_to_peak_hours;
  const lifePct = cockpit?.life_safety?.prob_gt_0_5m_max_pct;
  const pop = cockpit?.population?.life_safety_p90;

  return (
    <div
      className="rise-in"
      style={{
        display: "grid", gap: 12, marginTop: 12,
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
      }}
    >
      {/* 1 — THREAT LEVEL */}
      <div style={{
        background: ls.bg, border: "1px solid var(--border)", borderTop: `3px solid ${ls.fill}`,
        borderRadius: "var(--radius)", padding: "12px 14px", boxShadow: "var(--shadow-card)",
      }}>
        <div style={{ fontSize: "var(--text-2xs)", fontWeight: 800, letterSpacing: "0.09em", textTransform: "uppercase", color: ls.ink, marginBottom: 6 }}>
          Threat level
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="live-dot" style={{ background: ls.fill }} />
          <span style={{ fontSize: "1.5rem", fontWeight: 800, lineHeight: 1, color: ls.ink }}>{level}</span>
        </div>
        <div style={{ fontSize: "var(--text-xs)", color: ls.ink, opacity: 0.85, marginTop: 4 }}>
          Next 7 days, worst: <strong>{alert.max_7day_alert}</strong>
        </div>
      </div>

      {/* 2 — TIME TO ACT */}
      <Cell
        label="Time to act"
        tip={<InfoTip term="time to peak" />}
        sub={ttp ? `range ${ttp.p10.toFixed(1)}–${ttp.p90.toFixed(1)} hrs` : "no active flood"}
        accent="var(--accent)"
      >
        {ttp ? <>{ttp.p50.toFixed(1)} <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "var(--text-secondary)" }}>hrs</span></> : "—"}
      </Cell>

      {/* 3 — LIFE-SAFETY RISK */}
      <Cell
        label="Life-safety risk"
        tip={<InfoTip term="life-safety threshold" />}
        sub="chance any spot gets over 1.6 ft (0.5 m) deep"
        accent={lifePct && lifePct > 0 ? "var(--status-warning)" : "var(--status-good)"}
      >
        {lifePct != null ? `${Math.round(lifePct)}%` : "—"}
      </Cell>

      {/* 4 — PEOPLE AT RISK */}
      <Cell
        label="People at risk"
        tip={<InfoTip text="Estimated number of people in areas that could get life-threatening depth in the worst-case (P90) scenario, from WorldPop population data." />}
        sub="worst-case exposure (P90)"
        accent={pop && pop > 0 ? "var(--status-watch)" : "var(--status-good)"}
      >
        {pop != null ? pop.toLocaleString() : "—"}
      </Cell>

      {/* 5 — RECOMMENDED ACTION (full width row on wrap) */}
      <div style={{
        gridColumn: "1 / -1", background: "var(--bg-card)", border: "1px solid var(--border)",
        borderLeft: `4px solid ${act.tone}`, borderRadius: "var(--radius)", padding: "11px 16px",
        boxShadow: "var(--shadow-card)", display: "flex", alignItems: "center", gap: 10,
      }}>
        <span style={{ fontSize: "var(--text-2xs)", fontWeight: 800, letterSpacing: "0.09em", textTransform: "uppercase", color: act.tone }}>
          Do now
        </span>
        <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-primary)" }}>{act.action}</span>
      </div>
    </div>
  );
}
