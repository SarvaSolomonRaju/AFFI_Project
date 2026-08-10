import { useLiveData } from "../hooks/useLiveData";
import { useAlertEscalation } from "../hooks/useAlertEscalation";
import type { CurrentAlert, SimState } from "../types/api";
import { fmtCfs, fmtFeet } from "../utils/units";
import { alertIcon } from "../utils/alertLevel";
import { StaleBadge } from "./StaleBadge";

function AlertSoundToggle({ enabled, onEnable, onDisable }: { enabled: boolean; onEnable: () => void; onDisable: () => void }) {
  return (
    <button
      onClick={enabled ? onDisable : onEnable}
      title={enabled
        ? "Audible + push alert on escalation: ON. Click to disable."
        : "Enable an audible tone + browser notification whenever the alert level escalates"}
      style={{
        marginLeft: 10, padding: "2px 10px", borderRadius: 5, fontSize: "0.72rem", fontWeight: 700,
        cursor: "pointer", border: "1px solid currentColor", background: enabled ? "rgba(255,255,255,0.18)" : "transparent",
        color: "inherit", verticalAlign: "middle",
      }}
    >
      {enabled ? "🔔 Alerts ON" : "🔕 Enable alerts"}
    </button>
  );
}

function alertClass(level: string): string {
  return `alert-banner alert-${level.toLowerCase()}`;
}

// A forecast pipeline that silently dies still leaves a "GREEN" banner
// on screen — the manager has no way to tell live data from a stuck one
// unless the age of that data is surfaced. Thresholds tuned to how often
// the pipeline is expected to refresh (hourly cadence, daily worst case).
const STALE_WARN_HOURS = 2;
const STALE_CRITICAL_HOURS = 6;

function ageHours(generatedUtc: string | undefined | null): number | null {
  if (!generatedUtc) return null;
  const t = Date.parse(generatedUtc);
  if (Number.isNaN(t)) return null;
  return (Date.now() - t) / 3_600_000;
}

function StalenessBadge({ generatedUtc }: { generatedUtc: string | undefined | null }) {
  const hrs = ageHours(generatedUtc);
  if (hrs === null) return null;

  if (hrs >= STALE_CRITICAL_HOURS) {
    return (
      <div style={{
        background: "#c0392b", color: "white", borderRadius: 6,
        padding: "8px 12px", marginTop: 8, fontWeight: 700, fontSize: "0.85rem",
      }}>
        ⚠ DATA STALE — last forecast {hrs.toFixed(1)} hrs old. Pipeline may have failed.
        Do not treat this alert level as current. Check <code>make serve-api</code> logs.
      </div>
    );
  }
  if (hrs >= STALE_WARN_HOURS) {
    return (
      <div style={{
        background: "rgba(243,156,18,0.15)", border: "1px solid #f39c12", color: "#f39c12",
        borderRadius: 6, padding: "6px 12px", marginTop: 8, fontWeight: 600, fontSize: "0.8rem",
      }}>
        Forecast is {hrs.toFixed(1)} hrs old — confirm pipeline is still refreshing.
      </div>
    );
  }
  return null;
}

interface AlertBannerProps {
  refreshSignal?: number;
  simState?: SimState | null; // undefined = live, null = sim/no-flood, object = scenario active
  // True only for the rainfall-slider what-if (mode==="sim"). False when a
  // return-period is being explored from LIVE mode — that scenario data is
  // real 100-yr-etc library data, not a hypothetical, so it shouldn't say
  // "SIMULATION" while the mode toggle still reads LIVE FORECAST.
  isSimulationMode?: boolean;
}

export function AlertBanner({ refreshSignal, simState, isSimulationMode = false }: AlertBannerProps) {
  const inSimMode = simState !== undefined;
  const scenarioLabel = isSimulationMode ? "SIMULATION" : "EXPLORING SCENARIO";
  const { data: alert, error, lastUpdated } = useLiveData<CurrentAlert>(
    "/api/v1/alert/current",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  // Escalation sound/push only makes sense for the real live alert — a
  // simulation slider isn't a real event, so it never drives this hook.
  const { enabled: alertsEnabled, enable, disable } = useAlertEscalation(inSimMode ? null : alert?.current_alert);

  if (inSimMode) {
    if (!simState) {
      return (
        <div className="alert-banner alert-green">
          <span style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.08em", opacity: 0.75 }}>{scenarioLabel} ·</span>
          {" "}No flooding at current rainfall level
        </div>
      );
    }
    return (
      <div className={`alert-banner alert-${simState.alert_level.toLowerCase()}`}>
        <span style={{ fontSize: "0.72rem", fontWeight: 700, letterSpacing: "0.08em", opacity: 0.75 }}>{scenarioLabel} ·</span>
        {" "}Alert: <strong>{alertIcon(simState.alert_level)} {simState.alert_level}</strong> — {simState.return_period_yr}-year event
        ({simState.rainfall_in.toFixed(2)}" in 24 hrs)
        <div style={{ fontSize: "0.85rem", fontWeight: 400, marginTop: 4 }}>
          Peak Q: {fmtCfs(simState.Q_cms)} ·
          Max depth: {fmtFeet(simState.max_depth_m)} ·
          {simState.severity}
        </div>
      </div>
    );
  }

  if (error && !alert) {
    return (
      <div className="alert-banner alert-warning">
        Could not reach the backend: {error}
        <br />
        Is it running? (<code>make serve-api</code>)
      </div>
    );
  }
  if (!alert) return <div className="alert-banner">Loading current alert…</div>;

  return (
    <div className={alertClass(alert.current_alert)}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      Current alert: <strong>{alertIcon(alert.current_alert)} {alert.current_alert}</strong>
      <AlertSoundToggle enabled={alertsEnabled} onEnable={enable} onDisable={disable} />
      <div style={{ fontSize: "0.85rem", fontWeight: 400, marginTop: 4 }}>
        7-day max: {alert.max_7day_alert} · generated {alert.generated_utc} ·
        source: {alert.data_source}
        {lastUpdated && <> · refreshed {lastUpdated.toLocaleTimeString()}</>}
      </div>
      <StalenessBadge generatedUtc={alert.generated_utc} />
    </div>
  );
}
