import { useEffect, useMemo, useState } from "react";
import { useLiveData } from "../hooks/useLiveData";
import { apiGet } from "../api/client";
import type { DecisionCockpit as DecisionCockpitData, SimState, SimulationScenariosResponse } from "../types/api";
import { cmsToCfs, metersToFeet } from "../utils/units";

// The rating curve: how much water flow (cfs) turns into how deep the flood
// gets (ft). Built from the real flood library (each return-period scenario
// is one point). A manager reading a live gauge in cfs can trace up to see
// the depth it implies. Plain-language framing: "more flow → deeper water,"
// with today's flow marked so the depth it lands on is obvious.

interface Pt { q_cfs: number; depth_ft: number; rp: number; }

function Curve({ pts, todayQcfs, todayDepth }: { pts: Pt[]; todayQcfs: number | null; todayDepth: number | null }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 620, H = 250, ml = 54, mr = 18, mt = 18, mb = 42;
  const pw = W - ml - mr, ph = H - mt - mb;
  const maxQ = Math.max(...pts.map((p) => p.q_cfs), todayQcfs ?? 0) * 1.08;
  const maxD = Math.max(...pts.map((p) => p.depth_ft), todayDepth ?? 0) * 1.12;
  const xOf = (q: number) => ml + (q / maxQ) * pw;
  const yOf = (d: number) => mt + ph - (d / maxD) * ph;

  const line = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xOf(p.q_cfs).toFixed(1)} ${yOf(p.depth_ft).toFixed(1)}`).join(" ");
  const area = `${line} L ${xOf(pts[pts.length - 1].q_cfs).toFixed(1)} ${yOf(0)} L ${xOf(pts[0].q_cfs).toFixed(1)} ${yOf(0)} Z`;

  const xTicks = Array.from({ length: 5 }, (_, i) => (i / 4) * maxQ);
  const yTicks = Array.from({ length: 5 }, (_, i) => (i / 4) * maxD);

  return (
    <div style={{ width: "100%", overflowX: "auto" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W, display: "block" }} role="img"
        aria-label="Rating curve: river flow in cfs vs flood depth in feet">
        {yTicks.map((d, i) => (
          <line key={`g${i}`} x1={ml} y1={yOf(d)} x2={ml + pw} y2={yOf(d)} stroke="rgba(255,255,255,0.06)" strokeWidth={0.5} />
        ))}
        <path d={area} fill="rgba(42,120,214,0.12)" />
        <path d={line} fill="none" stroke="#2a78d6" strokeWidth={2.5} />

        {/* return-period points */}
        {pts.map((p, i) => (
          <g key={p.rp} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} style={{ cursor: "pointer" }}>
            <circle cx={xOf(p.q_cfs)} cy={yOf(p.depth_ft)} r={hover === i ? 6 : 4} fill="#2a78d6" stroke="#fff" strokeWidth={1.4} />
            {hover === i && (
              <g transform={`translate(${Math.min(xOf(p.q_cfs) + 8, ml + pw - 108)}, ${Math.max(mt, yOf(p.depth_ft) - 38)})`}>
                <rect width={104} height={34} rx={4} fill="rgba(10,18,30,0.95)" />
                <text x={7} y={14} fontSize={9.5} fill="#c3c2b7">{p.rp}-yr event</text>
                <text x={7} y={27} fontSize={10} fill="#fff">{Math.round(p.q_cfs).toLocaleString()} cfs → {p.depth_ft.toFixed(1)} ft</text>
              </g>
            )}
          </g>
        ))}

        {/* today marker */}
        {todayQcfs !== null && todayDepth !== null && (
          <g>
            <line x1={xOf(todayQcfs)} y1={mt} x2={xOf(todayQcfs)} y2={yOf(0)} stroke="#e67e22" strokeWidth={1.5} strokeDasharray="4 2" />
            <line x1={ml} y1={yOf(todayDepth)} x2={xOf(todayQcfs)} y2={yOf(todayDepth)} stroke="#e67e22" strokeWidth={1.2} strokeDasharray="4 2" opacity={0.7} />
            <circle cx={xOf(todayQcfs)} cy={yOf(todayDepth)} r={5.5} fill="#e67e22" stroke="#fff" strokeWidth={1.6} />
            <text x={xOf(todayQcfs)} y={mt - 4} textAnchor="middle" fontSize={10.5} fontWeight={800} fill="#e67e22">
              today ≈ {todayDepth.toFixed(1)} ft
            </text>
          </g>
        )}

        {/* axes */}
        {xTicks.filter((_, i) => i > 0).map((q, i) => (
          <text key={`xl${i}`} x={xOf(q)} y={mt + ph + 15} textAnchor="middle" fontSize={9.5} fill="var(--text-secondary)">
            {Math.round(q).toLocaleString()}
          </text>
        ))}
        <text x={ml + pw / 2} y={H - 6} textAnchor="middle" fontSize={10.5} fill="var(--text-secondary)">River flow (cfs) →</text>
        {yTicks.filter((_, i) => i > 0).map((d, i) => (
          <text key={`yl${i}`} x={ml - 6} y={yOf(d) + 4} textAnchor="end" fontSize={9} fill="var(--text-secondary)">{d.toFixed(0)}</text>
        ))}
        <text x={14} y={mt + ph / 2} textAnchor="middle" fontSize={10} fill="var(--text-secondary)"
          transform={`rotate(-90, 14, ${mt + ph / 2})`}>Flood depth (ft)</text>
      </svg>
    </div>
  );
}

export function StageRatingCurve({ refreshSignal, simState }: { refreshSignal?: number; simState?: SimState | null }) {
  const inSimMode = simState !== undefined;
  const [scenarios, setScenarios] = useState<SimulationScenariosResponse | null>(null);
  useEffect(() => {
    apiGet<SimulationScenariosResponse>("/api/v1/simulation/scenarios").then(setScenarios).catch(() => {});
  }, []);
  const { data } = useLiveData<DecisionCockpitData>(
    "/api/v1/decision-cockpit",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  const pts = useMemo<Pt[]>(() => {
    if (!scenarios) return [];
    return Object.entries(scenarios.scenarios)
      .map(([rp, s]) => ({ q_cfs: cmsToCfs(s.Q_cms), depth_ft: metersToFeet(s.max_depth_m), rp: Number(rp) }))
      .sort((a, b) => a.q_cfs - b.q_cfs);
  }, [scenarios]);

  if (pts.length < 2) return null;

  // Today's marker uses today's OWN real flow + depth (not interpolated off
  // the scenario curve) so it stays consistent with the depth panel — today's
  // flow sits below the smallest modeled scenario, so interpolation would
  // have mis-clamped it to the 5-yr depth.
  const todayQcfs = inSimMode
    ? (simState ? cmsToCfs(simState.Q_cms) : null)
    : (data?.discharge_cms ? cmsToCfs(data.discharge_cms.p50) : null);
  const todayDepth = inSimMode
    ? (simState ? metersToFeet(simState.max_depth_m) : null)
    : (data ? metersToFeet(data.flood_footprint.likely.max_depth_m) : null);

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>How river flow becomes water height</h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 12px" }}>
        More flow (cfs) means deeper water (ft). Each blue dot is a modeled flood size (deepest point in the creek channel); the{" "}
        <strong style={{ color: "#e67e22" }}>orange marker</strong> is {inSimMode ? "this scenario" : "today's forecast"} —
        trace it up to read the depth it produces. Hover any dot for its numbers.
      </p>
      <Curve pts={pts} todayQcfs={todayQcfs} todayDepth={todayDepth} />
    </div>
  );
}
