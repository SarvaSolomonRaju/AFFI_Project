import { useState } from "react";
import { useLiveData } from "../hooks/useLiveData";
import type { ForecastVerificationResponse, VerificationRecord } from "../types/api";
import { StaleBadge } from "./StaleBadge";

// Prediction vs. reality. A forecast tool you can't check is a tool you
// can't trust — this shows the honest track record: of the floods that
// really happened (measured at the nearest live gauge), how many did we
// catch, how often did we cry wolf, and is the model running systematically
// high or low — with a self-correction the pipeline can apply going forward.

const CAT = {
  hit:          { color: "#2ecc71", label: "Caught it", icon: "✓" },
  miss:         { color: "#c0392b", label: "Missed it", icon: "✕" },
  false_alarm:  { color: "#e67e22", label: "False alarm", icon: "!" },
  correct_calm: { color: "#6b8299", label: "Correctly calm", icon: "·" },
  pending:      { color: "#3a4a5a", label: "Awaiting", icon: "…" },
} as const;

function StatTile({ big, label, sub, color }: { big: string; label: string; sub?: string; color: string }) {
  return (
    <div style={{ background: "var(--bg-primary)", borderRadius: 8, padding: "12px 14px", flex: 1, minWidth: 150, borderTop: `3px solid ${color}` }}>
      <div style={{ fontSize: "2rem", fontWeight: 800, lineHeight: 1, color }}>{big}</div>
      <div style={{ fontSize: "0.82rem", fontWeight: 600, marginTop: 4 }}>{label}</div>
      {sub && <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function VerdictTimeline({ records }: { records: VerificationRecord[] }) {
  const [hover, setHover] = useState<number | null>(null);
  // most recent last (left→right = older→newer)
  const rows = [...records].reverse();
  const cell = 22, gap = 3, W = rows.length * (cell + gap);
  return (
    <div style={{ position: "relative", width: "100%", overflowX: "auto", paddingBottom: 4 }}>
      <svg viewBox={`0 0 ${Math.max(W, 1)} ${cell + 4}`} width={Math.max(W, 1)} height={cell + 4} style={{ display: "block" }}>
        {rows.map((r, i) => {
          const c = CAT[r.category] ?? CAT.pending;
          return (
            <rect key={i} x={i * (cell + gap)} y={2} width={cell} height={cell} rx={4}
              fill={c.color} opacity={hover === i ? 1 : 0.85}
              onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} style={{ cursor: "pointer" }} />
          );
        })}
      </svg>
      {hover !== null && rows[hover] && (
        <div style={{
          position: "absolute", top: cell + 6, left: Math.min(hover * (cell + gap), 300),
          background: "rgba(10,18,30,0.97)", border: "1px solid var(--border)", borderRadius: 6,
          padding: "6px 10px", fontSize: "0.76rem", zIndex: 5, whiteSpace: "nowrap",
        }}>
          <div style={{ fontWeight: 700, color: CAT[rows[hover].category]?.color }}>
            {rows[hover].date} — {CAT[rows[hover].category]?.label}
          </div>
          <div style={{ color: "var(--text-secondary)" }}>
            Predicted {rows[hover].predicted_alert}
            {rows[hover].predicted_p50_in != null && ` (${rows[hover].predicted_p50_in}" rain)`}
            {" · "}gauge {rows[hover].observed_mean_cfs != null ? `${rows[hover].observed_mean_cfs} cfs` : "—"}
          </div>
        </div>
      )}
    </div>
  );
}

export function ForecastVsReality({ refreshSignal }: { refreshSignal?: number }) {
  const { data, error, lastUpdated } = useLiveData<ForecastVerificationResponse>(
    "/api/v1/forecast-verification",
    300_000,
    refreshSignal,
  );

  if (error && !data) return null;
  if (!data) return null;

  const s = data.summary;
  const sc = data.self_correction;
  const total = Math.max(1, s.n_verified);

  const tendencyColor = sc.tendency === "over-forecasting" ? "#e67e22"
    : sc.tendency === "under-forecasting" ? "#c0392b"
    : sc.tendency === "balanced" ? "#2ecc71" : "#6b8299";

  // stacked proportion bar
  const segs = [
    { cat: "hit" as const, n: s.hits },
    { cat: "correct_calm" as const, n: s.correct_calm },
    { cat: "false_alarm" as const, n: s.false_alarms },
    { cat: "miss" as const, n: s.misses },
  ].filter((x) => x.n > 0);

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>
        Prediction vs. reality — our track record
        <span style={{ marginLeft: 10, fontSize: "0.72rem", fontWeight: 400, color: "var(--text-secondary)" }}>
          {s.n_verified} forecasts checked against the live gauge
        </span>
      </h3>

      {s.n_verified === 0 ? (
        <p style={{ color: "var(--text-secondary)" }}>
          No forecasts verified yet — the track record builds as each forecast day passes and the gauge records what actually happened.
        </p>
      ) : (
        <>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
            <StatTile
              big={s.hit_rate_pct != null ? `${s.hit_rate_pct}%` : "—"}
              label="of real floods caught"
              sub={`${s.hits} of ${s.hits + s.misses} actual events`}
              color="#2ecc71"
            />
            <StatTile
              big={s.false_alarm_rate_pct != null ? `${s.false_alarm_rate_pct}%` : "—"}
              label="of our flood calls were false alarms"
              sub={`${s.false_alarms} of ${s.hits + s.false_alarms} flood predictions`}
              color="#e67e22"
            />
            <StatTile
              big={`${Math.round((100 * (s.hits + s.correct_calm)) / total)}%`}
              label="overall correct"
              sub={`${s.hits + s.correct_calm} of ${s.n_verified} forecasts`}
              color="var(--accent-blue)"
            />
          </div>

          {/* proportion bar */}
          <div style={{ display: "flex", height: 18, borderRadius: 5, overflow: "hidden", marginBottom: 6 }}>
            {segs.map((seg) => (
              <div key={seg.cat} title={`${CAT[seg.cat].label}: ${seg.n}`}
                style={{ width: `${(100 * seg.n) / total}%`, background: CAT[seg.cat].color }} />
            ))}
          </div>
          <div style={{ display: "flex", gap: 14, flexWrap: "wrap", fontSize: "0.74rem", color: "var(--text-secondary)", marginBottom: 14 }}>
            {(["hit", "correct_calm", "false_alarm", "miss"] as const).map((c) => (
              <span key={c} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: CAT[c].color, display: "inline-block" }} />
                {CAT[c].label} ({c === "hit" ? s.hits : c === "correct_calm" ? s.correct_calm : c === "false_alarm" ? s.false_alarms : s.misses})
              </span>
            ))}
          </div>

          {/* per-forecast verdict timeline */}
          <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginBottom: 4 }}>
            Each forecast, oldest → newest (hover for detail):
          </div>
          <VerdictTimeline records={data.records} />

          {/* self-correction */}
          <div style={{
            marginTop: 14, background: "var(--bg-primary)", borderLeft: `4px solid ${tendencyColor}`,
            borderRadius: 6, padding: "10px 14px",
          }}>
            <div style={{ fontWeight: 700, color: tendencyColor, textTransform: "capitalize" }}>
              Self-correction: model is {sc.tendency}
            </div>
            <div style={{ fontSize: "0.84rem", marginTop: 3 }}>{sc.note}</div>
            {sc.suggested_threshold_delta_in != null && sc.suggested_threshold_delta_in !== 0 && (
              <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: 3 }}>
                Suggested rain-threshold nudge: <strong>{sc.suggested_threshold_delta_in > 0 ? "+" : ""}{sc.suggested_threshold_delta_in}"</strong> to
                {sc.suggested_threshold_delta_in > 0 ? " cut false alarms" : " catch more events"}.
              </div>
            )}
          </div>
        </>
      )}

      <p style={{ fontSize: "0.74rem", color: "var(--text-secondary)", marginTop: 12, marginBottom: 0, borderTop: "1px solid var(--border)", paddingTop: 8 }}>
        Reality measured at {data.observed_source.name} (gauge {data.observed_source.id}). {data.proxy_note}
      </p>
    </div>
  );
}
