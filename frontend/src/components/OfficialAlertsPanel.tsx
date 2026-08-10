import { useLiveData } from "../hooks/useLiveData";
import type { OfficialAlertsResponse } from "../types/api";
import { StaleBadge } from "./StaleBadge";

// The authoritative real-time source shown next to our own forecast. If NWS
// has a flash-flood warning out, THAT is what phones get via Wireless
// Emergency Alerts — the dashboard must never quietly disagree with it.

const SEV_COLOR: Record<string, string> = {
  Extreme: "#7b1fa2", Severe: "#c0392b", Moderate: "#e67e22", Minor: "#f39c12",
};

export function OfficialAlertsPanel({ refreshSignal }: { refreshSignal?: number }) {
  const { data, error, lastUpdated } = useLiveData<OfficialAlertsResponse>(
    "/api/v1/official-alerts",
    120_000,
    refreshSignal,
  );

  if (!data) return null;

  if (!data.available) {
    return (
      <div style={{ background: "var(--bg-card)", padding: "10px 14px", borderRadius: 8, marginTop: 12, fontSize: "0.85rem", color: "var(--text-secondary)" }}>
        ⚠ Could not reach the National Weather Service ({data.error}). Check <a href="https://www.weather.gov/twc/" target="_blank" rel="noreferrer" style={{ color: "var(--accent-blue)" }}>weather.gov</a> directly.
      </div>
    );
  }

  const floodActive = data.flood_alert_active;
  const floodAlerts = data.alerts.filter((a) => a.is_flood);
  const otherAlerts = data.alerts.filter((a) => !a.is_flood);

  return (
    // Deliberately NOT the same red-gradient "hero" treatment as our own
    // AlertBanner above it — those two stacked identically was reading as
    // one merged red blob, making it hard to tell "our model's assessment"
    // apart from "the government's actual warning" at a glance. This one
    // gets a formal, document-style container (flat card + a navy top rail,
    // never reused as a UI accent elsewhere) so "official government
    // source" has its own consistent visual signature; severity color is
    // still used, but only as an accent bar on each alert line, not a full
    // solid fill competing with our own banner.
    <div style={{
      background: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderTop: "3px solid var(--gov-navy-light)",
      padding: "12px 14px", borderRadius: "var(--radius)", marginTop: 12,
    }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
        <div style={{ fontWeight: 700, fontSize: "var(--text-base)", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{
            fontSize: "var(--text-2xs)", fontWeight: 800, letterSpacing: "0.08em",
            background: "var(--gov-navy)", color: "#cfe0f5", padding: "2px 7px", borderRadius: 4,
          }}>
            OFFICIAL
          </span>
          National Weather Service — right now
        </div>
        <div style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)" }}>
          Authoritative source · api.weather.gov{lastUpdated && ` · ${lastUpdated.toLocaleTimeString()}`}
        </div>
      </div>

      {floodActive ? (
        <div style={{ marginTop: 8 }}>
          {floodAlerts.map((a, i) => (
            <div key={i} style={{
              background: "var(--bg-primary)", borderLeft: `4px solid ${SEV_COLOR[a.severity ?? ""] ?? "#c0392b"}`,
              borderRadius: "4px 6px 6px 4px", padding: "8px 12px", marginBottom: 6,
            }}>
              <div style={{ fontWeight: 800, color: SEV_COLOR[a.severity ?? ""] ?? "#c0392b" }}>
                ⚠ {a.event}{a.severity ? ` · ${a.severity}` : ""}
              </div>
              {a.headline && <div style={{ fontSize: "var(--text-sm)", marginTop: 2, color: "var(--text-primary)" }}>{a.headline}</div>}
              {a.expires && <div style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)", marginTop: 2 }}>Until {new Date(a.expires).toLocaleString()}</div>}
            </div>
          ))}
        </div>
      ) : (
        <div style={{ marginTop: 6, fontSize: "var(--text-sm)", color: "#2ecc71", fontWeight: 600 }}>
          ✓ No NWS flood watch or warning active for this point right now.
        </div>
      )}

      {otherAlerts.length > 0 && (
        <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
          {otherAlerts.map((a, i) => (
            <span key={i} style={{
              fontSize: "var(--text-xs)", padding: "2px 8px", borderRadius: 12,
              background: "var(--bg-primary)", border: `1px solid ${SEV_COLOR[a.severity ?? ""] ?? "var(--border)"}`,
              color: "var(--text-secondary)",
            }}>
              {a.event}{a.severity ? ` · ${a.severity}` : ""}
            </span>
          ))}
        </div>
      )}
      <div style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)", marginTop: 8 }}>
        This is the official word. Our forecast below is a model — when the two disagree, trust NWS + your county EOC.
      </div>
    </div>
  );
}
