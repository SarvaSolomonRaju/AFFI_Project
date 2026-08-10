import { useLiveData } from "../hooks/useLiveData";
import type { DecisionCockpit as DecisionCockpitData, SimState } from "../types/api";
import { metersToFeet } from "../utils/units";

// Checked once per mount, not per render — matches how prefers-reduced-motion
// is meant to be read (a static user setting, not something that changes
// mid-session).
const PREFERS_REDUCED_MOTION =
  typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

// "What does this depth actually mean?" — the single most understandable
// flood visual for non-experts. A vertical water column with a person + car
// silhouette and human-scale danger thresholds, with today's Likely and
// Worst forecast depths marked as water lines. Turns an abstract "3.3 ft"
// into "up to the waist — you'd be swept off your feet."
//
// SOURCE, verified directly (not assumed) before writing these numbers:
// the three vehicle/life-safety depths below are the National Weather
// Service's own published "Turn Around Don't Drown" (TADD) figures —
// 6 in sweeps an adult off their feet, 12 in floats a car away, 24 in
// carries away most vehicles including SUVs/trucks. These are the exact
// numbers Arizona's own agencies cite, not a separate AZ-specific figure:
// the Arizona Department of Water Resources Floodplain Management Program
// (azwater.gov/floodplain-management-overview) and Santa Cruz County/Pima
// County/Cochise County/Pinal County emergency-management pages all repeat
// this same NWS campaign rather than publishing their own numbers — so the
// honest citation is "NWS TADD, as adopted by ADWR and AZ county EM," not
// "ADWR's own research." Ankle/knee labels below are plain body-scale
// framing (not an NWS-specific figure) so the scale reads continuously.
interface Threshold {
  ft: number;
  label: string;
  color: string;
  sourced?: boolean; // true = an exact cited NWS TADD figure, not descriptive filler
}

const THRESHOLDS: Threshold[] = [
  { ft: 0.25, label: "Ankle-deep, slippery footing", color: "#2ecc71" },
  { ft: 0.5, label: "Sweeps an adult off their feet", color: "#f39c12", sourced: true },
  { ft: 1.0, label: "Floats a car away", color: "#e67e22", sourced: true },
  { ft: 2.0, label: "Carries away most vehicles", color: "#c0392b", sourced: true },
  { ft: 5.5, label: "Over an adult's head", color: "#8e1a1a" },
];

function dangerColor(ft: number): string {
  if (ft <= 0) return "#2ecc71";
  if (ft < 0.5) return "#2ecc71";
  if (ft < 1.0) return "#f39c12";
  if (ft < 2.0) return "#e67e22";
  return "#c0392b";
}

function dangerWord(ft: number): string {
  if (ft <= 0) return "No flooding";
  if (ft < 0.5) return "Ankle-deep";
  if (ft < 1.0) return "6+ in — can sweep an adult off their feet";
  if (ft < 2.0) return "12+ in — can float a car away";
  return "24+ in — carries away most vehicles";
}

export function DepthScaleReference({ likelyM, worstM }: { likelyM: number; worstM: number }) {
  const likelyFt = metersToFeet(likelyM);
  const worstFt = metersToFeet(worstM);

  // FIXED human-danger scale (0–7 ft). The decisions people make live in this
  // range: ankle → knee → waist → "cars float" → "over an adult's head."
  // A creek can crest at 15–18 ft, but if the scale auto-stretched to that,
  // the 0.5–2 ft thresholds — exactly the ones that matter — would collapse
  // into an unreadable pile at the bottom. So the scale is fixed, and any
  // depth beyond it is clamped to the top and flagged "off the top,"
  // which is itself the message: catastrophic, well over your head.
  const maxFt = 7;
  const likelyOver = likelyFt > maxFt;
  const worstOver = worstFt > maxFt;

  // SVG geometry
  const W = 560, H = 300;
  const padL = 8, padR = 210, padT = 22, padB = 28;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;
  const colX = padL + 66;          // left edge of the water column
  const colW = plotW - 70;         // width of the water column
  const yFor = (ft: number) => padT + plotH * (1 - Math.min(ft, maxFt) / maxFt);
  const groundY = yFor(0);

  const waterTopY = yFor(likelyFt);
  const worstTopY = yFor(worstFt);
  // When both readings are over the top, one shared water fill + one combined
  // callout reads far cleaner than two overlapping lines pinned to the edge.
  const bothOver = likelyOver && worstOver;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>
        What this flood depth means
        <span style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 400, color: "var(--text-secondary)" }}>
          today's forecast, at human scale
        </span>
      </h3>

      {/* Headline plain-language reading */}
      <div style={{
        display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 14,
      }}>
        <div style={{ background: "var(--bg-primary)", borderRadius: 8, padding: "10px 14px", borderLeft: `4px solid ${dangerColor(likelyFt)}`, flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", letterSpacing: "0.05em" }}>LIKELY (P50)</div>
          <div style={{ fontSize: "1.9rem", fontWeight: 800, lineHeight: 1.1 }}>{likelyFt.toFixed(1)} ft</div>
          <div style={{ fontSize: "0.82rem", color: dangerColor(likelyFt), fontWeight: 600 }}>{dangerWord(likelyFt)}</div>
        </div>
        <div style={{ background: "var(--bg-primary)", borderRadius: 8, padding: "10px 14px", borderLeft: `4px solid ${dangerColor(worstFt)}`, flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", letterSpacing: "0.05em" }}>WORST CASE (P90)</div>
          <div style={{ fontSize: "1.9rem", fontWeight: 800, lineHeight: 1.1 }}>{worstFt.toFixed(1)} ft</div>
          <div style={{ fontSize: "0.82rem", color: dangerColor(worstFt), fontWeight: 600 }}>{dangerWord(worstFt)}</div>
        </div>
      </div>

      <div style={{ width: "100%", overflowX: "auto" }}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W, display: "block" }} role="img"
          aria-label={`Flood depth scale: likely ${likelyFt.toFixed(1)} feet, worst case ${worstFt.toFixed(1)} feet`}>
          {/* danger threshold bands (filled zones behind the column) */}
          {THRESHOLDS.map((t, i) => {
            const yTop = yFor(THRESHOLDS[i + 1]?.ft ?? maxFt);
            const yBot = yFor(t.ft);
            return (
              <rect key={t.ft} x={colX} y={yTop} width={colW} height={Math.max(0, yBot - yTop)}
                fill={t.color} opacity={0.10} />
            );
          })}

          {/* ground line */}
          <line x1={colX} y1={groundY} x2={colX + colW} y2={groundY} stroke="#c3a37a" strokeWidth={2} />

          {/* worst-case water (lighter, behind) — only drawn as a distinct
              line when it's on-scale and meaningfully above likely. */}
          {!worstOver && worstFt - likelyFt > 0.15 && (
            <>
              <rect x={colX} y={worstTopY} width={colW} height={Math.max(0, groundY - worstTopY)}
                fill="#4ea8de" opacity={0.22} />
              <line x1={colX} y1={worstTopY} x2={colX + colW} y2={worstTopY} stroke="#4ea8de" strokeWidth={1.5} strokeDasharray="5 3" />
            </>
          )}

          {/* likely water (solid blue fill) — clamped to the top when over-scale.
              A small "breathing" bob on the surface line (±2px, ~3s) is the
              only animation here — a static flood-depth diagram otherwise
              reads as a screenshot, not live water. Skipped entirely under
              prefers-reduced-motion rather than just slowed down. */}
          <rect x={colX} y={waterTopY} width={colW} height={Math.max(0, groundY - waterTopY)}
            fill="#2a78d6" opacity={0.5}>
            {!PREFERS_REDUCED_MOTION && (
              <>
                <animate attributeName="y" values={`${waterTopY};${waterTopY - 2};${waterTopY}`} dur="3.2s" repeatCount="indefinite" />
                <animate attributeName="height"
                  values={`${Math.max(0, groundY - waterTopY)};${Math.max(0, groundY - waterTopY + 2)};${Math.max(0, groundY - waterTopY)}`}
                  dur="3.2s" repeatCount="indefinite" />
              </>
            )}
          </rect>
          <line x1={colX} y1={waterTopY} x2={colX + colW} y2={waterTopY} stroke="#2a78d6" strokeWidth={2.5}>
            {!PREFERS_REDUCED_MOTION && (
              <>
                <animate attributeName="y1" values={`${waterTopY};${waterTopY - 2};${waterTopY}`} dur="3.2s" repeatCount="indefinite" />
                <animate attributeName="y2" values={`${waterTopY};${waterTopY - 2};${waterTopY}`} dur="3.2s" repeatCount="indefinite" />
              </>
            )}
          </line>

          {/* person silhouette (approx 5.5 ft tall) standing on the ground */}
          <Person groundY={groundY} yFor={yFor} x={colX + colW * 0.30} />
          {/* car (approx 5 ft tall incl. body) */}
          <Car groundY={groundY} yFor={yFor} x={colX + colW * 0.64} />

          {/* threshold labels on the right */}
          {THRESHOLDS.map((t) => (
            <g key={`lbl-${t.ft}`}>
              <line x1={colX + colW} y1={yFor(t.ft)} x2={colX + colW + 8} y2={yFor(t.ft)} stroke={t.color} strokeWidth={1.5} />
              <text x={colX + colW + 12} y={yFor(t.ft) + 3} fontSize="11" fill="var(--text-secondary)">
                <tspan fill={t.color} fontWeight="700">{t.ft} ft</tspan> — {t.label}
              </text>
            </g>
          ))}

          {/* left-side callouts for the actual readings */}
          {bothOver ? (
            // Both over the top: one combined callout above the column.
            <text x={colX} y={padT - 8} fontSize="11.5" fill="#2a78d6" fontWeight="700">
              ▲ Likely {likelyFt.toFixed(1)} ft · Worst {worstFt.toFixed(1)} ft — off the top, well over your head
            </text>
          ) : (
            <>
              <text x={colX - 6} y={Math.max(padT + 8, waterTopY + 4)} fontSize="11" textAnchor="end" fill="#2a78d6" fontWeight="700">
                {likelyOver ? "▲ " : ""}Likely {likelyFt.toFixed(1)}′
              </text>
              {!worstOver && worstFt - likelyFt > 0.15 && (
                <text x={colX - 6} y={worstTopY + 4} fontSize="11" textAnchor="end" fill="#4ea8de" fontWeight="700">
                  Worst {worstFt.toFixed(1)}′
                </text>
              )}
              {worstOver && !likelyOver && (
                <text x={colX} y={padT - 8} fontSize="11" fill="#4ea8de" fontWeight="700">
                  ▲ Worst case {worstFt.toFixed(1)} ft — off the top
                </text>
              )}
            </>
          )}
        </svg>
      </div>

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 8, fontSize: "0.74rem", color: "var(--text-secondary)" }}>
        <Legend swatch="#2a78d6" label="Likely depth (P50)" />
        <Legend swatch="#4ea8de" label="Worst case (P90)" dashed />
        <span>Just 12 inches of moving water floats most cars — <strong style={{ color: "var(--accent-orange)" }}>Turn Around, Don't Drown.</strong></span>
      </div>

      <p style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: 10, marginBottom: 0, borderTop: "1px solid var(--border)", paddingTop: 8 }}>
        Depth thresholds (6 in / 12 in / 24 in) are the National Weather Service's own published{" "}
        <a href="https://www.weather.gov/safety/flood-turn-around-dont-drown" target="_blank" rel="noreferrer" style={{ color: "var(--accent-blue)" }}>
          "Turn Around Don't Drown"
        </a>{" "}
        figures — the same numbers cited by the{" "}
        <a href="https://www.azwater.gov/floodplain-management-overview" target="_blank" rel="noreferrer" style={{ color: "var(--accent-blue)" }}>
          Arizona Department of Water Resources Floodplain Management Program
        </a>{" "}
        and Santa Cruz County emergency management. No Arizona-specific figure exists separately — this is the same NWS standard every AZ county repeats.
      </p>
    </div>
  );
}

// Data wrapper — same live/sim convention as the other panels.
interface DepthScalePanelProps {
  refreshSignal?: number;
  simState?: SimState | null;
}

export function DepthScalePanel({ refreshSignal, simState }: DepthScalePanelProps) {
  const inSimMode = simState !== undefined;
  const { data } = useLiveData<DecisionCockpitData>(
    "/api/v1/decision-cockpit",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  if (inSimMode) {
    if (!simState) return null; // no scenario -> nothing to scale
    // Sim mode has one selected scenario; use its depth for both marks
    // (there is no separate P90 worst-case in a single what-if).
    return <DepthScaleReference likelyM={simState.max_depth_m} worstM={simState.max_depth_m} />;
  }

  if (!data) return null;
  const likelyM = data.flood_footprint.likely.max_depth_m;
  const worstM = data.flood_footprint.worst.max_depth_m;
  if (likelyM <= 0 && worstM <= 0) return null; // dry day -> panel adds nothing
  return <DepthScaleReference likelyM={likelyM} worstM={worstM} />;
}

function Legend({ swatch, label, dashed }: { swatch: string; label: string; dashed?: boolean }) {
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span style={{ display: "inline-block", width: 22, height: dashed ? 0 : 10, borderTop: dashed ? `2px dashed ${swatch}` : "none", background: dashed ? "none" : swatch, borderRadius: 2 }} />
      {label}
    </span>
  );
}

// Person silhouette, sized to ~5.5 ft using the same vertical scale as the
// water, so the water line crosses the body where it really would.
//
// Was rendering headless: headR was computed as (yFor(5.5) - yFor(4.9)) / 2
// — but yFor maps a LARGER ft to a SMALLER y (higher up the chart), so
// yFor(5.5) < yFor(4.9) and that subtraction produced a NEGATIVE radius.
// SVG treats a negative <circle r> as invalid and simply doesn't paint it,
// so the head silently disappeared, leaving only the arm/leg lines — which
// is exactly what read as "the man in the car" looking wrong. Fixed by
// subtracting in the other order, and rebuilt as filled shapes (matching
// the Car's visual weight) instead of bare stroke lines, so it actually
// reads as a person silhouette at a glance rather than a stick diagram.
function Person({ groundY, yFor, x }: { groundY: number; yFor: (ft: number) => number; x: number }) {
  const headTopY = yFor(5.5);
  const headR = (yFor(4.9) - headTopY) / 2; // yFor(4.9) is BELOW yFor(5.5) on screen — positive
  const headCy = headTopY + headR;
  const shoulderY = yFor(4.7);
  const hipY = yFor(2.7);
  const torsoW = headR * 1.8;
  const armW = headR * 0.55;
  const legGap = headR * 0.35;
  const legW = headR * 0.65;
  return (
    <g stroke="#2c3a48" strokeWidth={1.5} fill="#6b7f92">
      {/* arms — behind the torso so only the outer edge shows past it */}
      <line x1={x - torsoW / 2 + 2} y1={shoulderY + headR * 0.3} x2={x - torsoW / 2 - headR * 0.5} y2={hipY}
        strokeWidth={armW} strokeLinecap="round" />
      <line x1={x + torsoW / 2 - 2} y1={shoulderY + headR * 0.3} x2={x + torsoW / 2 + headR * 0.5} y2={hipY}
        strokeWidth={armW} strokeLinecap="round" />
      {/* legs */}
      <rect x={x - legGap - legW} y={hipY} width={legW} height={Math.max(0, groundY - hipY)} rx={legW * 0.35} />
      <rect x={x + legGap} y={hipY} width={legW} height={Math.max(0, groundY - hipY)} rx={legW * 0.35} />
      {/* torso — rounded capsule, drawn after legs/arms so it sits on top */}
      <rect x={x - torsoW / 2} y={shoulderY} width={torsoW} height={Math.max(0, hipY - shoulderY)} rx={torsoW * 0.3} />
      {/* head */}
      <circle cx={x} cy={headCy} r={headR} />
    </g>
  );
}

// Simple car silhouette ~5 ft tall, ~14 ft wide-ish (scaled down for the column).
function Car({ groundY, yFor, x }: { groundY: number; yFor: (ft: number) => number; x: number }) {
  const roofY = yFor(4.7);
  const beltY = yFor(3.4);
  const bodyY = yFor(1.8);
  const w = 62, cw = 34;
  return (
    <g stroke="#3a4a5a" strokeWidth={2} fill="#6a7b8a" opacity={0.85}>
      {/* cabin */}
      <path d={`M ${x - cw / 2} ${beltY} Q ${x - cw / 2} ${roofY} ${x - cw / 4} ${roofY} L ${x + cw / 4} ${roofY} Q ${x + cw / 2} ${roofY} ${x + cw / 2} ${beltY} Z`} />
      {/* body */}
      <rect x={x - w / 2} y={beltY} width={w} height={bodyY - beltY} rx={4} />
      {/* wheels */}
      <circle cx={x - w / 3} cy={groundY - 3} r={5} fill="#2a3540" />
      <circle cx={x + w / 3} cy={groundY - 3} r={5} fill="#2a3540" />
    </g>
  );
}
