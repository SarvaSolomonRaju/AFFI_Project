import { useMemo, useState } from "react";
import { gammaHydro } from "../utils/simulation";
import { cmsToCfs } from "../utils/units";

// A hydrograph that a non-technical person can read. The old version was a
// matplotlib PNG axis-labeled "Discharge Q (m³/s)" with P10/P50/P90 curves —
// meaningless to anyone without hydrology training. This says, in plain
// words: how high the water gets, WHEN it peaks (your decision clock), and
// the best-to-worst range around that — with a hover readout and an
// annotated peak, so the single most important number ("act before ~2.5 h")
// jumps out.

interface HydrographProps {
  title: string;
  subtitle?: string;
  q50_cms: number;          // likely peak discharge
  ttpP50: number;           // hours to peak, likely
  ttpP10: number;           // hours to peak, best (slower/later)
  ttpP90: number;           // hours to peak, worst (faster/earlier)
  // Horizontal "flood begins here" reference lines (the Google Flood Hub
  // convention) — real return-period discharges, sorted ascending.
  thresholds?: { label: string; cfs: number; color: string }[];
}

export function Hydrograph({ title, subtitle, q50_cms, ttpP50, ttpP10, ttpP90, thresholds }: HydrographProps) {
  const [hoverT, setHoverT] = useState<number | null>(null);

  const q50 = cmsToCfs(q50_cms);
  const W = 620, H = 280;
  const ml = 60, mr = 20, mt = 24, mb = 46;
  const pw = W - ml - mr;
  const ph = H - mt - mb;

  const { qBest, qLikely, qWorst, qMax, t } = useMemo(() => {
    const N = 240;
    const tArr = Array.from({ length: N }, (_, i) => (i + 0.5) * (24 / N));
    const qLikely = gammaHydro(q50, Math.max(0.05, ttpP50), tArr);
    const qBest = gammaHydro(q50 * 0.65, Math.max(0.05, ttpP10), tArr);
    const qWorst = gammaHydro(q50 * 1.35, Math.max(0.05, ttpP90), tArr);
    // Y-scale fits the CURVE first (worst-case peak). Pulling the flood
    // threshold into frame unconditionally — the naive Flood-Hub approach —
    // crushes the flow line into an invisible sliver on a calm day, when
    // flow is ~1% of flood level. Instead: include a threshold line only if
    // it's within reach of the worst-case peak (≤ 2.2× it). Anything higher
    // is shown as an out-of-frame "↑ flood level" banner, so the curve stays
    // readable AND the flood context is never lost.
    const worstPeak = Math.max(...qWorst, 1);
    let yTop = worstPeak * 1.2;
    if (thresholds && thresholds.length > 0) {
      const reachable = thresholds.filter((th) => th.cfs <= worstPeak * 2.2);
      if (reachable.length > 0) yTop = Math.max(yTop, reachable[reachable.length - 1].cfs * 1.12);
    }
    return { qBest, qLikely, qWorst, qMax: yTop, t: tArr };
  }, [q50, ttpP50, ttpP10, ttpP90, thresholds]);

  const xOf = (ti: number) => ml + (ti / 24) * pw;
  const yOf = (q: number) => mt + ph - (Math.max(0, q) / qMax) * ph;
  const pathOf = (qs: number[]) => t.map((ti, i) => `${i === 0 ? "M" : "L"} ${xOf(ti).toFixed(1)} ${yOf(qs[i]).toFixed(1)}`).join(" ");

  const bandPath = [
    ...t.map((ti, i) => `${i === 0 ? "M" : "L"} ${xOf(ti).toFixed(1)} ${yOf(qWorst[i]).toFixed(1)}`),
    ...[...t].reverse().map((ti, i) => `L ${xOf(ti).toFixed(1)} ${yOf(qBest[t.length - 1 - i]).toFixed(1)}`),
    "Z",
  ].join(" ");

  const peakX = xOf(ttpP50);
  const peakY = yOf(q50);
  const flipLeft = peakX + 150 > ml + pw;

  const xTicks = [0, 4, 8, 12, 16, 20, 24];
  const yTicks = Array.from({ length: 5 }, (_, i) => (i / 4) * qMax);

  // hover readout (likely curve value at the hovered hour)
  const hoverIdx = hoverT === null ? null : Math.min(t.length - 1, Math.max(0, Math.round((hoverT / 24) * t.length)));
  const hoverQ = hoverIdx === null ? null : qLikely[hoverIdx];

  // Threshold crossing — the Flood Hub signature annotation: WHEN does the
  // likely flow cross the "flood begins" line (if it does at all).
  const firstThreshold = thresholds && thresholds.length > 0 ? thresholds[0] : null;
  const crossIdx = firstThreshold ? qLikely.findIndex((q) => q >= firstThreshold.cfs) : -1;
  const crossT = crossIdx >= 0 ? t[crossIdx] : null;
  const pctOfFlood = firstThreshold ? Math.round((100 * q50) / firstThreshold.cfs) : null;
  const visibleThresholds = (thresholds ?? []).filter((th) => th.cfs <= qMax * 0.99);
  // Flood level is off the top of the chart (calm day) — show it as a banner
  // with how many times bigger than today's peak it is, so the context isn't
  // lost even though the line can't be drawn without crushing the curve.
  const floodOffTop = firstThreshold && firstThreshold.cfs > qMax * 0.99 ? firstThreshold : null;
  const floodMultiple = floodOffTop && q50 > 0 ? Math.round(floodOffTop.cfs / q50) : null;

  function onMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const ti = ((px - ml) / pw) * 24;
    setHoverT(ti >= 0 && ti <= 24 ? ti : null);
  }

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>{title}</h3>
      {subtitle && <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 6px" }}>{subtitle}</p>}
      {/* Plain-language takeaway — the one sentence that matters */}
      <p style={{ margin: "0 0 12px", fontSize: "0.9rem" }}>
        Water rises fast and peaks about <strong style={{ color: "#e67e22" }}>{ttpP50.toFixed(1)} hours from now</strong>,
        then falls.{" "}
        {firstThreshold && crossT !== null ? (
          <>It <strong style={{ color: "#e34948" }}>crosses the {firstThreshold.label} about {crossT.toFixed(1)} hours from now</strong> — act before that, not before the peak.</>
        ) : firstThreshold && pctOfFlood !== null ? (
          <>The peak stays <strong style={{ color: "#2ecc71" }}>below the {firstThreshold.label}</strong> (about {pctOfFlood}% of it) — the creek should stay in its channel on the likely forecast.</>
        ) : (
          <><strong>Act before the peak</strong> — that's your window.</>
        )}
      </p>

      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto", display: "block", cursor: "crosshair" }}
        onMouseMove={onMove} onMouseLeave={() => setHoverT(null)} role="img"
        aria-label={`Water flow over 24 hours, peaking around ${ttpP50.toFixed(1)} hours from now`}>
        {/* horizontal gridlines */}
        {yTicks.map((q, i) => (
          <line key={`yg${i}`} x1={ml} y1={yOf(q)} x2={ml + pw} y2={yOf(q)} stroke="rgba(255,255,255,0.06)" strokeWidth={0.5} />
        ))}

        {/* FLOOD THRESHOLD LINES — the Google Flood Hub signature: horizontal
            "flood begins here" levels the flow is read against. Shaded band
            above the first line = flood territory. */}
        {firstThreshold && yOf(firstThreshold.cfs) > mt && (
          <rect x={ml} y={mt} width={pw} height={Math.max(0, yOf(firstThreshold.cfs) - mt)} fill="rgba(227,73,72,0.07)" />
        )}
        {visibleThresholds.map((th) => (
          <g key={th.label}>
            <line x1={ml} y1={yOf(th.cfs)} x2={ml + pw} y2={yOf(th.cfs)} stroke={th.color} strokeWidth={1.2} strokeDasharray="6 4" opacity={0.8} />
            <text x={ml + pw - 3} y={yOf(th.cfs) - 3} textAnchor="end" fill={th.color} fontSize={9} fontWeight={700}>
              {th.label} ({Math.round(th.cfs).toLocaleString()} cfs)
            </text>
          </g>
        ))}

        {/* flood level off the top (calm day) — banner instead of a crushed curve */}
        {floodOffTop && (
          <g>
            <line x1={ml} y1={mt + 1} x2={ml + pw} y2={mt + 1} stroke={floodOffTop.color} strokeWidth={1.4} strokeDasharray="6 4" opacity={0.75} />
            <text x={ml + pw - 3} y={mt + 13} textAnchor="end" fill={floodOffTop.color} fontSize={9.5} fontWeight={800}>
              ↑ {floodOffTop.label} at {Math.round(floodOffTop.cfs).toLocaleString()} cfs{floodMultiple ? ` — ${floodMultiple}× today's peak` : ""}
            </text>
          </g>
        )}

        {/* range band (best → worst) */}
        <path d={bandPath} fill="rgba(78,168,222,0.16)" />

        {/* curves: best (light dashed), worst (red dashed), likely (bold blue) */}
        <path d={pathOf(qBest)} fill="none" stroke="#86b6ef" strokeWidth={1.4} strokeDasharray="5 3" opacity={0.7} />
        <path d={pathOf(qWorst)} fill="none" stroke="#e34948" strokeWidth={1.6} strokeDasharray="5 3" opacity={0.85} />
        <path d={pathOf(qLikely)} fill="none" stroke="#2a78d6" strokeWidth={3} />

        {/* "NOW" marker at t=0 */}
        <line x1={xOf(0)} y1={mt} x2={xOf(0)} y2={mt + ph} stroke="#8899aa" strokeWidth={1.2} />
        <text x={xOf(0) + 4} y={mt + 10} fill="#8899aa" fontSize={10} fontWeight="700">NOW</text>

        {/* peak marker + plain callout */}
        <line x1={peakX} y1={mt} x2={peakX} y2={mt + ph} stroke="#e67e22" strokeWidth={1.4} strokeDasharray="4 2" opacity={0.8} />
        <circle cx={peakX} cy={peakY} r={5.5} fill="#e67e22" stroke="#fff" strokeWidth={1.5} />
        <g transform={`translate(${flipLeft ? peakX - 150 : peakX + 8}, ${Math.max(mt + 4, peakY - 34)})`}>
          <rect width={144} height={40} rx={5} fill="rgba(10,18,30,0.94)" stroke="#e67e22" strokeWidth={1} />
          <text x={8} y={16} fill="#e67e22" fontSize={11} fontWeight="800">▲ PEAK — highest water</text>
          <text x={8} y={31} fill="#fff" fontSize={10.5}>
            ~{Math.round(q50).toLocaleString()} cfs, in {ttpP50.toFixed(1)} hrs
          </text>
        </g>

        {/* flood-crossing marker — WHEN the likely flow reaches flood level */}
        {firstThreshold && crossT !== null && (
          <g>
            <circle cx={xOf(crossT)} cy={yOf(firstThreshold.cfs)} r={5} fill="#e34948" stroke="#fff" strokeWidth={1.5} />
            <text x={xOf(crossT)} y={yOf(firstThreshold.cfs) + 18} textAnchor="middle" fill="#e34948" fontSize={9.5} fontWeight={800}>
              floods at +{crossT.toFixed(1)}h
            </text>
          </g>
        )}

        {/* rising / falling plain labels */}
        <text x={xOf(Math.max(0.4, ttpP50 * 0.4))} y={mt + ph - 6} fill="#8899aa" fontSize={9.5} textAnchor="middle">water rising ↑</text>
        <text x={xOf(Math.min(23, ttpP50 + (24 - ttpP50) * 0.4))} y={mt + ph - 6} fill="#8899aa" fontSize={9.5} textAnchor="middle">water falling ↓</text>

        {/* hover crosshair + tooltip */}
        {hoverT !== null && hoverQ !== null && (
          <g>
            <line x1={xOf(hoverT)} y1={mt} x2={xOf(hoverT)} y2={mt + ph} stroke="#fff" strokeWidth={0.8} opacity={0.4} />
            <circle cx={xOf(hoverT)} cy={yOf(hoverQ)} r={3.5} fill="#2a78d6" stroke="#fff" strokeWidth={1.5} />
            <g transform={`translate(${Math.min(xOf(hoverT) + 8, ml + pw - 108)}, ${mt + 4})`}>
              <rect width={104} height={34} rx={4} fill="rgba(10,18,30,0.94)" />
              <text x={7} y={14} fill="#c3c2b7" fontSize={9.5}>{hoverT.toFixed(1)} hrs from now</text>
              <text x={7} y={28} fill="#fff" fontSize={11} fontWeight="700">~{Math.round(hoverQ).toLocaleString()} cfs</text>
            </g>
          </g>
        )}

        {/* axes */}
        {xTicks.map((ti) => (
          <text key={`xl${ti}`} x={xOf(ti)} y={mt + ph + 15} textAnchor="middle" fill="var(--text-secondary)" fontSize={10}>+{ti}h</text>
        ))}
        <text x={ml + pw / 2} y={H - 6} textAnchor="middle" fill="var(--text-secondary)" fontSize={10.5}>Hours from now →</text>
        {yTicks.filter((_, i) => i > 0).map((q, i) => (
          <text key={`yll${i}`} x={ml - 6} y={yOf(q) + 4} textAnchor="end" fill="var(--text-secondary)" fontSize={9} style={{ fontVariantNumeric: "tabular-nums" }}>
            {Math.round(q).toLocaleString()}
          </text>
        ))}
        <text x={16} y={mt + ph / 2} textAnchor="middle" fill="var(--text-secondary)" fontSize={10}
          transform={`rotate(-90, 16, ${mt + ph / 2})`}>Water flow (cfs)</text>
      </svg>

      {/* legend — plain words, not P50/P10/P90 */}
      <div style={{ display: "flex", gap: 18, marginTop: 8, fontSize: "0.8rem", color: "var(--text-secondary)", flexWrap: "wrap" }}>
        <LegendItem color="#2a78d6" label="Most likely" thick />
        <LegendItem color="#e34948" label="Worst case" dashed />
        <LegendItem color="#86b6ef" label="Best case" dashed />
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ display: "inline-block", width: 22, height: 11, background: "rgba(78,168,222,0.22)", borderRadius: 2 }} />
          Range of what could happen
        </span>
        <span style={{ opacity: 0.8 }}>Hover the line to read any hour.</span>
      </div>
    </div>
  );
}

function LegendItem({ color, label, thick, dashed }: { color: string; label: string; thick?: boolean; dashed?: boolean }) {
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ display: "inline-block", width: 22, height: 0, borderTop: `${thick ? 3 : 2}px ${dashed ? "dashed" : "solid"} ${color}` }} />
      {label}
    </span>
  );
}
