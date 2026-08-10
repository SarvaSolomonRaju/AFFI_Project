import { useLiveData } from "../hooks/useLiveData";
import type { DecisionCockpit as DecisionCockpitData, SimState } from "../types/api";

// The single most decision-relevant question in a flash flood: "do I have
// time to do X before the water peaks?" This lays the time-to-peak against
// how long each protective action takes, so a glance answers go/no-go — a
// green bar finishes before the earliest the water could peak, a red one
// might not. Action durations are TYPICAL EOC planning estimates (labeled as
// such), the same kind of planning reference as the forecast-confidence
// ladder — a starting point, not a measured local value.

type Category = "structure" | "public" | "internal";

interface Action {
  label: string;
  hours: number;
  icon: string;
  category: Category;
}

const CATEGORY_META: Record<Category, { title: string; note: string }> = {
  structure: { title: "Structure priority plans", note: "Named facilities with occupants who can't self-evacuate quickly — always lead the clock." },
  public: { title: "Public plans", note: "Warning the public and controlling traffic/roads." },
  internal: { title: "Internal / agency plans", note: "EOC's own staffing and mutual-aid activation — runs in parallel with the above, not after." },
};

// Grouped per NIMS/ICS incident-priority order: life-safety-critical
// structures (schools/care facilities can't move occupants fast) come
// before general public actions, which run in parallel with the agency's
// own internal activation — not a strict sequence, but three concurrent
// tracks an EOC runs at once. Durations are still typical EOC PLANNING
// ESTIMATES, not measured local values (see footer caveat).
const ACTIONS: Action[] = [
  { label: "Evacuate schools", hours: 0.9, icon: "🏫", category: "structure" },
  { label: "Evacuate hospital / care facility", hours: 1.5, icon: "🏥", category: "structure" },
  { label: "Evacuate vulnerable/low-lying residents", hours: 1.75, icon: "🏠", category: "structure" },
  { label: "Issue public flash-flood warning (IPAWS/WEA)", hours: 0.25, icon: "📣", category: "public" },
  { label: "Barricade low-water crossings", hours: 0.5, icon: "🚧", category: "public" },
  { label: "Door-to-door notice (no-cell-signal areas)", hours: 1.25, icon: "🚪", category: "public" },
  { label: "Activate EOC & notify fire/sheriff/Red Cross", hours: 0.4, icon: "☎️", category: "internal" },
  { label: "Stage swift-water rescue teams", hours: 0.75, icon: "🚤", category: "internal" },
  { label: "Request county/state mutual aid", hours: 1.0, icon: "🤝", category: "internal" },
];

// Flattens the 3 category groups into a render list of header rows (taller,
// no bar) interleaved with action rows, so one SVG keeps a single time
// scale across all groups instead of three disconnected mini-charts.
type Row = { kind: "header"; category: Category } | { kind: "action"; action: Action };

function buildRows(): Row[] {
  const rows: Row[] = [];
  (Object.keys(CATEGORY_META) as Category[]).forEach((cat) => {
    rows.push({ kind: "header", category: cat });
    ACTIONS.filter((a) => a.category === cat).forEach((action) => rows.push({ kind: "action", action }));
  });
  return rows;
}
const ROWS = buildRows();

function TimeBudget({ ttpEarliest, ttpLikely }: { ttpEarliest: number; ttpLikely: number }) {
  const W = 720, rowH = 30, headerH = 24, gap = 8, labelW = 320, mt = 34, mb = 6;
  const barAreaW = W - labelW - 24;
  const maxH = Math.max(ttpLikely * 1.15, ...ACTIONS.map((a) => a.hours), ttpEarliest) * 1.05;
  const xOf = (h: number) => labelW + (h / maxH) * barAreaW;

  let y = mt;
  const positioned = ROWS.map((row) => {
    const rowTop = y;
    y += (row.kind === "header" ? headerH : rowH) + gap;
    return { row, rowTop };
  });
  const H = y + mb;

  return (
    <div style={{ width: "100%", overflowX: "auto" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W, display: "block" }} role="img"
        aria-label="Time available before the water peaks vs. how long each action takes, grouped by structure/public/internal plans">
        {/* peak window: earliest-peak (danger) to likely-peak */}
        <rect x={xOf(ttpEarliest)} y={mt - 6} width={Math.max(1, xOf(ttpLikely) - xOf(ttpEarliest))} height={H - mt - mb + 6}
          fill="#e67e22" opacity={0.12} />
        <line x1={xOf(ttpEarliest)} y1={mt - 12} x2={xOf(ttpEarliest)} y2={H - mb} stroke="#c0392b" strokeWidth={1.6} strokeDasharray="4 2" />
        <text x={xOf(ttpEarliest)} y={mt - 16} textAnchor="middle" fontSize={10.5} fontWeight="800" fill="#c0392b">
          earliest peak {ttpEarliest.toFixed(1)}h
        </text>
        <line x1={xOf(ttpLikely)} y1={mt - 12} x2={xOf(ttpLikely)} y2={H - mb} stroke="#e67e22" strokeWidth={1.6} />
        <text x={xOf(ttpLikely)} y={mt - 2} textAnchor="middle" fontSize={10.5} fontWeight="800" fill="#e67e22">
          likely peak {ttpLikely.toFixed(1)}h
        </text>

        {positioned.map(({ row, rowTop }, i) => {
          if (row.kind === "header") {
            const meta = CATEGORY_META[row.category];
            return (
              <g key={`h-${i}`}>
                <text x={0} y={rowTop + headerH - 8} fontSize="12.5" fontWeight="800" fill="var(--text-primary)">
                  {meta.title}
                </text>
                <line x1={0} y1={rowTop + headerH - 2} x2={W} y2={rowTop + headerH - 2} stroke="var(--border)" strokeWidth={1} />
              </g>
            );
          }
          const a = row.action;
          const fits = a.hours <= ttpEarliest;
          const fill = fits ? "#1b9e5a" : "#c0392b";
          const w = Math.max(3, (a.hours / maxH) * barAreaW);
          return (
            <g key={a.label}>
              <text x={labelW - 10} y={rowTop + rowH / 2 + 4} textAnchor="end" fontSize="11" fill="var(--text-primary)">
                {a.icon} {a.label}
              </text>
              <rect x={labelW} y={rowTop + 4} width={barAreaW} height={rowH - 8} rx={4} fill="rgba(255,255,255,0.04)" />
              <rect x={labelW} y={rowTop + 4} width={w} height={rowH - 8} rx={4} fill={fill} />
              <text x={labelW + w + 6} y={rowTop + rowH / 2 + 4} fontSize="11" fontWeight="700" fill={fill}>
                {a.hours < 1 ? `${Math.round(a.hours * 60)} min` : `${a.hours.toFixed(1)} hr`}
                {fits ? "  ✓ fits" : "  ✕ tight"}
              </text>
            </g>
          );
        })}
      </svg>
      <div style={{ display: "flex", gap: 14, marginTop: 6, flexWrap: "wrap" }}>
        {(Object.keys(CATEGORY_META) as Category[]).map((cat) => (
          <span key={cat} style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
            <strong>{CATEGORY_META[cat].title}:</strong> {CATEGORY_META[cat].note}
          </span>
        ))}
      </div>
    </div>
  );
}

export function EvacuationTimeBudget({ refreshSignal, simState }: { refreshSignal?: number; simState?: SimState | null }) {
  const inSimMode = simState !== undefined;
  const { data } = useLiveData<DecisionCockpitData>(
    "/api/v1/decision-cockpit",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  let ttpLikely: number | null = null;
  let ttpEarliest: number | null = null;
  if (inSimMode) {
    if (simState) { ttpLikely = simState.time_to_peak_p50; ttpEarliest = simState.time_to_peak_p90; }
  } else if (data) {
    ttpLikely = data.time_to_peak_hours.p50;
    ttpEarliest = data.time_to_peak_hours.p90;
  }

  if (ttpLikely === null || ttpEarliest === null) {
    if (inSimMode && !simState) return null;
    return null;
  }

  const allFit = ACTIONS.every((a) => a.hours <= ttpEarliest!);

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>Do you have time? — evacuation clock</h3>
      <p style={{ margin: "0 0 4px", fontSize: "0.9rem" }}>
        The water could peak as early as <strong style={{ color: "#c0392b" }}>{ttpEarliest.toFixed(1)} hours</strong> from now
        (likely {ttpLikely.toFixed(1)} h). A <strong style={{ color: "#1b9e5a" }}>green</strong> action finishes in time;{" "}
        <strong style={{ color: "#c0392b" }}>red</strong> may not.
      </p>
      <p style={{ margin: "0 0 12px", fontSize: "0.82rem", color: allFit ? "#1b9e5a" : "#e67e22", fontWeight: 600 }}>
        {allFit ? "✓ Everything fits before the earliest peak — but start now." : "⚠ Some actions may not finish before the earliest peak — prioritize life-safety first."}
      </p>
      <TimeBudget ttpEarliest={ttpEarliest} ttpLikely={ttpLikely} />
      <p style={{ fontSize: "0.74rem", color: "var(--text-secondary)", marginTop: 8, marginBottom: 0 }}>
        Action times are typical EOC planning estimates, not measured local values — adjust to your jurisdiction's real response times.
      </p>
    </div>
  );
}
