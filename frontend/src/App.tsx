import { useState } from "react";
import "./theme.css";
import { AlertBanner } from "./components/AlertBanner";
import { ForecastTable } from "./components/ForecastTable";
import { FloodMap } from "./components/FloodMap";
import { SimulationSlider } from "./components/SimulationSlider";
import { ActionPanel } from "./components/ActionPanel";
import { BulletinPanel } from "./components/BulletinPanel";
import { HistoricalComparison } from "./components/HistoricalComparison";
import { DecisionCockpit } from "./components/DecisionCockpit";

function App() {
  // Lives here, not inside FloodMap or SimulationSlider, because both
  // of those components need it: the slider sets it, the map reads it.
  const [overlayUrl, setOverlayUrl] = useState<string | undefined>(undefined);
  const isSimulation = overlayUrl !== undefined;

  // Every LIVE component polls the backend every 60s on its own (see
  // useLiveData) — this is purely for the "Refresh now" button.
  // Bumping it forces all of them to refetch immediately instead of
  // waiting for their next interval tick; a manager watching an active
  // event shouldn't have to wait up to a minute after a page reload
  // just to force a check.
  const [refreshSignal, setRefreshSignal] = useState(0);

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: 8 }}>
        <h1 style={{ margin: 0 }}>FloodAI — Upper Sonoita Creek</h1>
        <button
          onClick={() => setRefreshSignal((n) => n + 1)}
          style={{ padding: "6px 14px", borderRadius: 6, border: "1px solid var(--border)", cursor: "pointer", background: "var(--bg-card)", color: "var(--text-primary)" }}
        >
          Refresh now
        </button>
      </div>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: 4 }}>
        Auto-refreshes every 60s — no manual reload needed during an active event.
      </p>

      {/* LIVE section — ordered for a flood manager: alert level first,
          then how much time is actually available (Decision Cockpit),
          then what to DO about it, then situational awareness (map),
          then how to communicate it, then the trend ahead. Everything
          here reflects today's real forecast regardless of what the
          simulation slider below is set to. */}
      <AlertBanner refreshSignal={refreshSignal} />
      <DecisionCockpit refreshSignal={refreshSignal} />
      <ActionPanel refreshSignal={refreshSignal} />
      <FloodMap overlayUrl={overlayUrl} isSimulation={isSimulation} />
      <BulletinPanel refreshSignal={refreshSignal} />
      <HistoricalComparison refreshSignal={refreshSignal} />
      <ForecastTable refreshSignal={refreshSignal} />

      {/* WHAT-IF section — deliberately separated and visually distinct
          so it can't be mistaken for live data. Only the map overlay
          responds to this; Action Panel / Bulletin above stay tied to
          today's real forecast (not wired to the slider — out of scope
          for now, by design). */}
      <div style={{ border: "1px dashed var(--accent-orange)", borderRadius: 8, padding: 16, marginTop: 32 }}>
        <p style={{ color: "var(--accent-orange)", fontWeight: 600, margin: "0 0 8px" }}>
          WHAT-IF SIMULATION — not live data. Only the map above changes; Action Plan and Bulletin stay based on today's real forecast.
        </p>
        <SimulationSlider onChange={(_T, url) => setOverlayUrl(url)} />
      </div>
    </div>
  );
}

export default App;
