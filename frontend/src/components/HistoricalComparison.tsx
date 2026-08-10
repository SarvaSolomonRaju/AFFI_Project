import { useEffect, useState } from "react";
import { useLiveData } from "../hooks/useLiveData";
import { apiGet } from "../api/client";
import type { HistoricalComparison as HistoricalComparisonData, HistoricalEventsCatalog, SimState } from "../types/api";
import { cmsToCfs, fmtCfs } from "../utils/units";
import { StaleBadge } from "./StaleBadge";

interface HistoricalComparisonProps {
  refreshSignal?: number;
  simState?: SimState | null;
  isSimulationMode?: boolean;
}

interface BarRow {
  label: string;
  sublabel: string;
  q_cms: number;
  isToday: boolean;
  isClosest: boolean;
}

// Horizontal magnitude comparison: today's forecast discharge against every
// documented past flood, biggest at top. Turns "today is close to the 2014
// event" from a sentence into a picture anyone can read at a glance.
function ComparisonBars({ rows }: { rows: BarRow[] }) {
  const maxQ = Math.max(...rows.map((r) => r.q_cms), 1);
  const rowH = 34, gap = 10, labelW = 188, valueW = 78;
  const chartW = 588;
  const barAreaW = chartW - labelW - valueW;
  const H = rows.length * (rowH + gap);

  return (
    <div style={{ width: "100%", overflowX: "auto" }}>
      {/* viewBox starts left of 0 so right-anchored event labels have room */}
      <svg viewBox={`-28 0 ${chartW + 28} ${H}`} width="100%" style={{ maxWidth: chartW + 28, display: "block" }} role="img"
        aria-label="Peak discharge: today's forecast vs documented past floods">
        {rows.map((r, i) => {
          const y = i * (rowH + gap);
          const w = Math.max(2, (r.q_cms / maxQ) * barAreaW);
          const fill = r.isToday ? "#e67e22" : "#6b8299";
          return (
            <g key={r.label}>
              {/* row label (event name) */}
              <text x={labelW - 10} y={y + rowH / 2 - 3} textAnchor="end" fontSize="12.5" fontWeight={r.isToday ? 800 : 600}
                fill={r.isToday ? "#e67e22" : "var(--text-primary)"}>
                {r.label}
              </text>
              <text x={labelW - 10} y={y + rowH / 2 + 12} textAnchor="end" fontSize="10.5" fill="var(--text-secondary)">
                {r.sublabel}
              </text>
              {/* track */}
              <rect x={labelW} y={y + 4} width={barAreaW} height={rowH - 8} rx={4} fill="rgba(255,255,255,0.04)" />
              {/* bar — 4px rounded data-end anchored to the baseline (left) */}
              <rect x={labelW} y={y + 4} width={w} height={rowH - 8} rx={4} fill={fill}
                stroke={r.isClosest ? "#4ea8de" : "none"} strokeWidth={r.isClosest ? 2 : 0} />
              {/* value at the end */}
              <text x={labelW + barAreaW + 6} y={y + rowH / 2 + 4} fontSize="12" fontWeight="700"
                fill={r.isToday ? "#e67e22" : "var(--text-secondary)"} style={{ fontVariantNumeric: "tabular-nums" }}>
                {Math.round(cmsToCfs(r.q_cms)).toLocaleString()}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export function HistoricalComparison({ refreshSignal, simState }: HistoricalComparisonProps) {
  const inSimMode = simState !== undefined;

  const path = inSimMode && simState
    ? `/api/v1/historical-comparison?q_cms=${simState.Q_cms.toFixed(1)}`
    : "/api/v1/historical-comparison";

  const { data, error, lastUpdated } = useLiveData<HistoricalComparisonData>(
    path,
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  // Full catalog (all past events) for the bar chart — static reference data.
  const [catalog, setCatalog] = useState<HistoricalEventsCatalog | null>(null);
  useEffect(() => {
    apiGet<HistoricalEventsCatalog>("/api/v1/historical-events").then(setCatalog).catch(() => {});
  }, []);

  if (inSimMode && !simState) {
    return (
      <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
        <h3 style={{ marginTop: 0 }}>Historical Match — Simulation</h3>
        <p style={{ color: "var(--text-secondary)" }}>Increase rainfall to see which historical event the scenario resembles.</p>
      </div>
    );
  }

  if (error && !data) return <p>Could not load historical comparison: {error}</p>;
  if (!data) return <p>Loading historical comparison…</p>;

  const { closest_event: event, delta_pct_vs_closest_event: delta } = data;
  const todayQ = inSimMode && simState ? simState.Q_cms : data.today_discharge_cms;
  const noFlowToday = todayQ === 0;

  // Build the bar rows: today + every catalog event, sorted big → small.
  const rows: BarRow[] = [];
  if (catalog && Array.isArray(catalog.events)) {
    if (!noFlowToday) {
      rows.push({
        label: inSimMode ? "This scenario" : "Today's forecast",
        sublabel: inSimMode && simState ? `~${simState.return_period_yr}-yr event` : "live",
        q_cms: todayQ, isToday: true, isClosest: false,
      });
    }
    for (const ev of catalog.events) {
      rows.push({
        label: ev.name.replace(/ Monsoon Flood| Heavy Rain Event| Remnants/, ""),
        sublabel: `${ev.date} · ~${ev.approx_return_period_yr}yr`,
        q_cms: ev.peak_q_cms,
        isToday: false,
        isClosest: ev.name === event.name,
      });
    }
    rows.sort((a, b) => b.q_cms - a.q_cms);
  }

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>
        {inSimMode ? "How this scenario compares to past floods" : "How today compares to past floods"}
      </h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 12px" }}>
        Peak discharge (cfs) — {inSimMode ? "this scenario" : "today's forecast"} against every documented flood on record.
        The <span style={{ color: "#4ea8de", fontWeight: 700 }}>blue outline</span> marks the closest match.
      </p>

      {rows.length > 0 ? (
        <ComparisonBars rows={rows} />
      ) : (
        <p style={{ color: "var(--text-secondary)" }}>{noFlowToday ? "Nothing to chart — creek stays in-channel." : "Loading events…"}</p>
      )}

      {/* One-line plain-language takeaway under the chart */}
      <p style={{ marginTop: 12, marginBottom: 6 }}>
        {noFlowToday && !inSimMode
          ? <>No flow forecasted today. Smallest documented event on record: <strong>{event.name}</strong> ({event.date}).</>
          : <>
              {inSimMode ? "This scenario" : "Today's forecast"} most resembles the{" "}
              <strong>{event.name}</strong> ({event.date}, {fmtCfs(event.peak_q_cms)}, ~{event.approx_return_period_yr}-yr event)
              {delta !== null && <> — {delta >= 0 ? "+" : ""}{delta}% vs. that event</>}.
            </>}
      </p>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.82rem", margin: 0 }}>{event.notes}</p>
      <p style={{ fontSize: "0.78rem", color: "var(--text-secondary)", borderTop: "1px solid var(--border)", paddingTop: 8, marginBottom: 0 }}>
        Source: {event.source}. Catalog of {data.catalog_size} documented events — {data.catalog_source}
      </p>
    </div>
  );
}
