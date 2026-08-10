import { useState } from "react";
import type { SevenDayDetailResponse } from "../types/api";
import { metersToFeet } from "../utils/units";

// A 7-day glance: one bar per day, HEIGHT = how deep the water gets,
// COLOR = the alert level. The dashed worst-case cap shows how much worse it
// could be. Turns "read seven thumbnails and a table" into one trend anyone
// can scan: are things getting better or worse this week?

const ALERT_COLOR: Record<string, string> = {
  GREEN: "#27ae60", ADVISORY: "#f39c12", WATCH: "#e67e22", WARNING: "#c0392b",
};

export function SevenDayRiskStrip({ data }: { data: SevenDayDetailResponse }) {
  const [hover, setHover] = useState<number | null>(null);
  const days = data.days.slice(0, 7);

  const W = 620, H = 190, mt = 14, mb = 40, ml = 34, mr = 12;
  const pw = W - ml - mr, ph = H - mt - mb;
  const maxFt = Math.max(2, ...days.map((d) => metersToFeet(d.worst.max_depth_m))) * 1.12;
  const yOf = (ft: number) => mt + ph - (ft / maxFt) * ph;
  const bandW = pw / days.length;
  const barW = Math.min(46, bandW * 0.56);

  // life-safety reference line (1.6 ft = swept off your feet)
  const dangerFt = 1.6;

  return (
    <div style={{ width: "100%", overflowX: "auto" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: W, display: "block" }} role="img"
        aria-label="Seven-day flood risk: bar height is water depth, color is alert level">
        {/* gridlines */}
        {[0, 0.25, 0.5, 0.75, 1].map((f, i) => (
          <line key={i} x1={ml} y1={yOf(f * maxFt)} x2={ml + pw} y2={yOf(f * maxFt)} stroke="rgba(255,255,255,0.06)" strokeWidth={0.5} />
        ))}
        {/* danger line */}
        {dangerFt < maxFt && (
          <>
            <line x1={ml} y1={yOf(dangerFt)} x2={ml + pw} y2={yOf(dangerFt)} stroke="#c0392b" strokeWidth={1} strokeDasharray="4 3" opacity={0.7} />
            <text x={ml + pw} y={yOf(dangerFt) - 4} textAnchor="end" fontSize={9.5} fill="#c0392b">1.6 ft — life-safety</text>
          </>
        )}

        {days.map((d, i) => {
          const cx = ml + bandW * i + bandW / 2;
          const likelyFt = metersToFeet(d.likely.max_depth_m);
          const worstFt = metersToFeet(d.worst.max_depth_m);
          const color = ALERT_COLOR[d.alert_level] ?? "#27ae60";
          const label = i === 0 ? "Today" : new Date(d.date + "T12:00:00").toLocaleDateString("en-US", { weekday: "short" });
          return (
            <g key={d.day} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} style={{ cursor: "pointer" }}>
              {/* worst-case cap (light, dashed top) */}
              <rect x={cx - barW / 2} y={yOf(worstFt)} width={barW} height={Math.max(0, yOf(0) - yOf(worstFt))}
                fill={color} opacity={hover === i ? 0.28 : 0.18} rx={3} />
              <line x1={cx - barW / 2} y1={yOf(worstFt)} x2={cx + barW / 2} y2={yOf(worstFt)} stroke={color} strokeWidth={1.2} strokeDasharray="4 2" opacity={0.8} />
              {/* likely depth (solid) */}
              <rect x={cx - barW / 2} y={yOf(likelyFt)} width={barW} height={Math.max(0, yOf(0) - yOf(likelyFt))}
                fill={color} opacity={hover === i ? 1 : 0.9} rx={3} />
              {/* day label + alert */}
              <text x={cx} y={H - 24} textAnchor="middle" fontSize={11} fontWeight={i === 0 ? 800 : 600} fill="var(--text-primary)">{label}</text>
              <text x={cx} y={H - 12} textAnchor="middle" fontSize={8.5} fontWeight={700} fill={color}>{d.alert_level}</text>
              {hover === i && (
                <g transform={`translate(${Math.min(cx + 6, ml + pw - 96)}, ${mt})`}>
                  <rect width={92} height={34} rx={4} fill="rgba(10,18,30,0.95)" />
                  <text x={6} y={14} fontSize={9.5} fill="#c3c2b7">likely {likelyFt.toFixed(1)} ft</text>
                  <text x={6} y={27} fontSize={9.5} fill="#fff">worst {worstFt.toFixed(1)} ft</text>
                </g>
              )}
            </g>
          );
        })}
        {/* y label */}
        <text x={12} y={mt + ph / 2} textAnchor="middle" fontSize={10} fill="var(--text-secondary)"
          transform={`rotate(-90, 12, ${mt + ph / 2})`}>Depth (ft)</text>
      </svg>
    </div>
  );
}
