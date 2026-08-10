import { useState } from "react";
import { apiGet } from "../api/client";
import type { CurrentAlert, DecisionCockpit, ActionPlan, Bulletin } from "../types/api";
import { fmtFeet } from "../utils/units";

interface SummaryData {
  alert: CurrentAlert;
  cockpit: DecisionCockpit;
  plan: ActionPlan;
  bulletin: Bulletin;
  generatedAt: string;
}

// Plain-text incident summary — built once, then handed to whichever
// channel the user picks (email client via mailto:, or X's web share
// intent). Both are real, credential-free hand-offs to the user's own
// mail/X app; this component never calls a social/email API directly; no
// API keys exist for that, and faking one would be dishonest.
function buildSummaryText(d: SummaryData): string {
  const lines = [
    `FLOODAI INCIDENT SUMMARY — Upper Sonoita Creek`,
    `Generated ${d.generatedAt}`,
    ``,
    `CURRENT ALERT: ${d.alert.current_alert} (7-day max: ${d.alert.max_7day_alert})`,
    `Forecast generated ${d.alert.generated_utc} · source: ${d.alert.data_source}`,
    ``,
    `DECISION COCKPIT`,
    `- Time to peak flow: ${d.cockpit.time_to_peak_hours.p50.toFixed(1)} hrs (range ${d.cockpit.time_to_peak_hours.p90.toFixed(1)}-${d.cockpit.time_to_peak_hours.p10.toFixed(1)} hrs)`,
    `- Life-safety threshold: ${d.cockpit.life_safety.prob_gt_0_5m_max_pct}% chance any area exceeds 1.6 ft depth`,
    ...(d.cockpit.population?.life_safety_p90 != null
      ? [`- Population at risk (P90 worst-case): ~${d.cockpit.population.life_safety_p90.toLocaleString()}`]
      : []),
    `- Today's likely footprint: max depth ${fmtFeet(d.cockpit.flood_footprint.likely.max_depth_m, 2)}, wet area ${d.cockpit.flood_footprint.likely.wet_area_km2.toFixed(2)} km2`,
    ``,
    `ACTION PLAN — ${d.plan.reference_scenario}`,
    `Roads to barricade (${d.plan.roads_to_barricade.total_count} total):`,
    ...(d.plan.roads_to_barricade.top.length === 0
      ? [`  None at this reference scenario.`]
      : d.plan.roads_to_barricade.top.map((r) => `  - ${r.name} — ${r.max_depth_m.toFixed(2)} m`)),
    `Buildings to evacuate (${d.plan.buildings_to_evacuate.total_count} total):`,
    ...(d.plan.buildings_to_evacuate.top.length === 0
      ? [`  None at this reference scenario.`]
      : d.plan.buildings_to_evacuate.top.map((b) => `  - ${b.name} [${b.category}] — ${b.max_depth_m.toFixed(2)} m`)),
    ...(d.plan.schools_in_flood_zone.length > 0
      ? [`Schools in flood zone — evacuate first:`, ...d.plan.schools_in_flood_zone.map((s) => `  - ${s.name} — ${s.max_depth_m.toFixed(2)} m`)]
      : []),
    ``,
    d.plan.legal_note,
    ``,
    `BULLETIN`,
    d.bulletin.text,
  ];
  return lines.join("\n");
}

export function PrintSummaryButton() {
  const [data, setData] = useState<SummaryData | null>(null);
  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  async function handlePrepare() {
    setLoading(true);
    setError(null);
    try {
      const [alert, cockpit, plan, bulletin] = await Promise.all([
        apiGet<CurrentAlert>("/api/v1/alert/current"),
        apiGet<DecisionCockpit>("/api/v1/decision-cockpit"),
        apiGet<ActionPlan>("/api/v1/action-plan"),
        apiGet<Bulletin>("/api/v1/bulletin"),
      ]);
      const d = { alert, cockpit, plan, bulletin, generatedAt: new Date().toLocaleString() };
      setData(d);
      setText(buildSummaryText(d));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function handleEmail() {
    if (!data || !text) return;
    const subject = `FloodAI Incident Summary — ${data.alert.current_alert} — Upper Sonoita Creek`;
    // mailto: bodies are practically capped around ~2000 chars by mail
    // clients/OS — truncate with a visible marker rather than silently
    // clipping the action-plan detail the recipient needs most.
    const MAX_BODY = 1800;
    const body = text.length > MAX_BODY ? text.slice(0, MAX_BODY) + "\n\n[...truncated — see full dashboard]" : text;
    window.location.href = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  }

  function handleShareX() {
    if (!data) return;
    const post = `FloodAI alert — ${data.alert.current_alert} — Upper Sonoita Creek. Time to peak ${data.cockpit.time_to_peak_hours.p50.toFixed(1)} hrs. Details: `;
    window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(post)}`, "_blank", "noopener,noreferrer");
  }

  async function handleCopy() {
    if (!text) return;
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        {!text ? (
          <button
            onClick={handlePrepare}
            disabled={loading}
            title="Fetch the latest alert, decision cockpit, action plan, and bulletin, then choose how to send it"
            style={{
              padding: "6px 14px", borderRadius: 6, border: "1px solid var(--border)", cursor: loading ? "wait" : "pointer",
              background: "var(--bg-card)", color: "var(--text-primary)",
            }}
          >
            {loading ? "Preparing…" : "📤 Prepare Incident Summary"}
          </button>
        ) : (
          <>
            <button
              onClick={handleEmail}
              title="Open your email client with this summary ready to send to EOC / professional contacts"
              style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid var(--border)", cursor: "pointer", background: "var(--bg-card)", color: "var(--text-primary)" }}
            >
              ✉️ Email
            </button>
            <button
              onClick={handleShareX}
              title="Open X (Twitter) with a short alert ready to post"
              style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid var(--border)", cursor: "pointer", background: "var(--bg-card)", color: "var(--text-primary)" }}
            >
              🐦 Share to X
            </button>
            <button
              onClick={handleCopy}
              title="Copy the full plain-text summary to clipboard, to paste anywhere"
              style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid var(--border)", cursor: "pointer", background: "var(--bg-card)", color: "var(--text-primary)" }}
            >
              {copied ? "Copied!" : "📋 Copy"}
            </button>
            <button
              onClick={() => { setData(null); setText(null); }}
              style={{ padding: "6px 10px", borderRadius: 6, border: "1px solid var(--border)", cursor: "pointer", background: "transparent", color: "var(--text-secondary)", fontSize: "0.8rem" }}
            >
              ↺ Refresh
            </button>
          </>
        )}
        {error && <span style={{ color: "var(--accent-orange)", fontSize: "0.78rem" }}>Could not prepare summary: {error}</span>}
      </div>
      {text && (
        <textarea
          readOnly
          value={text}
          rows={6}
          style={{
            width: "100%", maxWidth: 640, fontFamily: "monospace", fontSize: "0.75rem",
            background: "var(--bg-primary)", color: "var(--text-primary)", border: "1px solid var(--border)",
            borderRadius: 6, padding: 8, resize: "vertical",
          }}
        />
      )}
    </div>
  );
}
