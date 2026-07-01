import { useState } from "react";
import "./theme.css";
import { AlertBanner } from "./components/AlertBanner";
import { ForecastTable } from "./components/ForecastTable";
import { FloodMap } from "./components/FloodMap";
import { SimulationSlider } from "./components/SimulationSlider";
import { ActionPanel } from "./components/ActionPanel";
import { BulletinPanel } from "./components/BulletinPanel";

function App() {
  // Lives here, not inside FloodMap or SimulationSlider, because both
  // of those components need it: the slider sets it, the map reads it.
  const [overlayUrl, setOverlayUrl] = useState<string | undefined>(undefined);
  const isSimulation = overlayUrl !== undefined;

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h1>FloodAI — Upper Sonoita Creek</h1>

      {/* LIVE section — ordered for a flood manager: alert level first,
          then what to DO about it, then situational awareness (map),
          then how to communicate it, then the trend ahead. Everything
          here reflects today's real forecast regardless of what the
          simulation slider below is set to. */}
      <AlertBanner />
      <ActionPanel />
      <FloodMap overlayUrl={overlayUrl} isSimulation={isSimulation} />
      <BulletinPanel />
      <ForecastTable />

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
