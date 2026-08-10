import type { SimState } from "../types/api";
import {
  IDF_24HR,
  RETURN_PERIODS,
  RAINFALL_MAX,
  FLOOD_ONSET_RAINFALL,
} from "../utils/simulation";
import { cmsToCfs, fmtAcres, fmtFeet } from "../utils/units";
import { alertIcon } from "../utils/alertLevel";

// Controlled component — rainfall/scenarios/simState all live in App.tsx now,
// shared with FloodMap's return-period explorer, so the slider and the map
// can never silently disagree about which scenario is currently active.
interface RainfallControlProps {
  rainfall: number;
  onRainfallChange: (rainfall: number) => void;
  simState: SimState | null;
}

const ALERT_COLOR: Record<string, { bg: string; text: string }> = {
  GREEN:    { bg: "#1b7340", text: "white" },
  ADVISORY: { bg: "#b38600", text: "black" },
  WATCH:    { bg: "#b35900", text: "white" },
  WARNING:  { bg: "#8b1a1a", text: "white" },
};

const RP_LABEL: Record<number, string> = {
  5: "5yr", 10: "10yr", 25: "25yr", 50: "50yr", 100: "100yr", 200: "200yr",
};

function StatCard({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <div style={{
      background: "var(--bg-primary)",
      borderRadius: 6,
      padding: "8px 10px",
      borderTop: `3px solid ${accent}`,
      minWidth: 110,
    }}>
      <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)", marginBottom: 2 }}>{label}</div>
      <div style={{ fontWeight: 700, fontSize: "1.05rem" }}>{value}</div>
    </div>
  );
}

export function RainfallControl({ rainfall, onRainfallChange, simState }: RainfallControlProps) {
  const sim = simState;
  const rp = sim?.return_period_yr ?? null;
  const isFlooding = sim !== null;
  const alertColors = sim ? (ALERT_COLOR[sim.alert_level] ?? ALERT_COLOR.GREEN) : { bg: "#1b7340", text: "white" };

  return (
    <div style={{
      background: "var(--bg-card)",
      borderRadius: 10,
      padding: "18px 20px",
      border: `2px solid ${isFlooding ? alertColors.bg : "#2a4a2a"}`,
      marginBottom: 20,
      transition: "border-color 0.3s",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10, marginBottom: 14 }}>
        <div>
          <div style={{ fontWeight: 800, color: "var(--accent-orange)", fontSize: "0.8rem", letterSpacing: "0.1em", marginBottom: 2 }}>
            SIMULATION — WHAT-IF RAINFALL
          </div>
          <div style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}>
            Drag the bar. Every chart, map, alert, and bulletin updates instantly.
          </div>
        </div>
        <div style={{
          background: alertColors.bg,
          color: alertColors.text,
          borderRadius: 6,
          padding: "6px 14px",
          fontWeight: 800,
          fontSize: "0.9rem",
          letterSpacing: "0.05em",
        }}>
          {isFlooding ? `${alertIcon(sim!.alert_level)} ${sim!.alert_level} — ${rp}-YEAR EVENT` : `${alertIcon("GREEN")} NO FLOODING`}
        </div>
      </div>

      {/* Big rainfall number */}
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 14 }}>
        <span style={{
          fontSize: "3.4rem",
          fontWeight: 900,
          lineHeight: 1,
          color: isFlooding ? alertColors.bg : "#27ae60",
          transition: "color 0.3s",
          fontVariantNumeric: "tabular-nums",
        }}>
          {rainfall.toFixed(2)}
        </span>
        <div>
          <div style={{ fontSize: "1.1rem", color: "var(--text-secondary)", fontWeight: 600 }}>inches</div>
          <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>24-hour rainfall</div>
        </div>
        {sim && (
          <div style={{ marginLeft: 16, paddingLeft: 16, borderLeft: "1px solid var(--border)" }}>
            <div style={{ fontSize: "1.6rem", fontWeight: 700, color: "#e74c3c" }}>{Math.round(cmsToCfs(sim.Q_cms)).toLocaleString()}</div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>cfs peak Q</div>
          </div>
        )}
      </div>

      {/* Rainfall slider */}
      <div style={{ marginBottom: 6 }}>
        <input
          type="range"
          min={0}
          max={RAINFALL_MAX}
          step={0.05}
          value={rainfall}
          onChange={(e) => onRainfallChange(parseFloat(e.target.value))}
          style={{ width: "100%", cursor: "pointer", height: 6, accentColor: isFlooding ? alertColors.bg : "#27ae60" }}
        />
      </div>

      {/* IDF markers row */}
      <div style={{ position: "relative", height: 38, marginBottom: 8 }}>
        {/* Flood onset */}
        <div style={{
          position: "absolute",
          left: `${(FLOOD_ONSET_RAINFALL / RAINFALL_MAX) * 100}%`,
          transform: "translateX(-50%)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
        }}>
          <div style={{ width: 1, height: 8, background: "var(--text-secondary)", opacity: 0.5 }} />
          <div style={{ fontSize: "0.65rem", color: "var(--text-secondary)", whiteSpace: "nowrap", opacity: 0.7 }}>
            ~1" onset
          </div>
        </div>

        {/* Return period marks */}
        {RETURN_PERIODS.filter(T => IDF_24HR[T] <= RAINFALL_MAX).map(T => {
          const isActive = rp === T;
          const pct = (IDF_24HR[T] / RAINFALL_MAX) * 100;
          return (
            <div key={T} style={{
              position: "absolute",
              left: `${pct}%`,
              transform: "translateX(-50%)",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              cursor: "pointer",
            }} onClick={() => onRainfallChange(IDF_24HR[T])}>
              <div style={{ width: 1, height: 8, background: isActive ? alertColors.bg : "var(--border)" }} />
              <div style={{
                fontSize: "0.72rem",
                fontWeight: isActive ? 800 : 400,
                color: isActive ? alertColors.bg : "var(--text-secondary)",
                whiteSpace: "nowrap",
                marginTop: 1,
              }}>
                {RP_LABEL[T]}
              </div>
              <div style={{
                fontSize: "0.6rem",
                color: "var(--text-secondary)",
                opacity: 0.6,
              }}>
                {IDF_24HR[T]}"
              </div>
            </div>
          );
        })}
      </div>

      {/* Axis ticks */}
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.68rem", color: "var(--text-secondary)", opacity: 0.6, marginBottom: 14 }}>
        {[0, 1, 2, 3, 4, 5, 6].map(v => <span key={v}>{v}"</span>)}
      </div>

      {/* Scenario stats grid */}
      {sim ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(115px, 1fr))", gap: 8 }}>
          <StatCard label="Max flood depth" value={fmtFeet(sim.max_depth_m)} accent={alertColors.bg} />
          <StatCard label="Flooded area" value={fmtAcres(sim.wet_area_km2)} accent={alertColors.bg} />
          <StatCard label="Roads at risk" value={`${sim.roads_at_risk} segs`} accent={alertColors.bg} />
          <StatCard label="Infrastructure" value={`${sim.infra_at_risk} items`} accent={alertColors.bg} />
          <StatCard label="Time to peak" value={`~${sim.time_to_peak_p50.toFixed(1)} hrs`} accent={alertColors.bg} />
          <StatCard label="Life-safety risk" value={`${sim.life_safety_pct}%`} accent={alertColors.bg} />
        </div>
      ) : (
        <div style={{
          background: "rgba(27, 115, 64, 0.12)",
          border: "1px solid #1b7340",
          borderRadius: 6,
          padding: "10px 14px",
          color: "#4caf50",
          fontSize: "0.85rem",
        }}>
          Rainfall below flooding threshold for Upper Sonoita Creek.
          Increase to {FLOOD_ONSET_RAINFALL.toFixed(1)}" or more to see flood impacts. Click any return-period label above to jump to that scenario.
        </div>
      )}
    </div>
  );
}
