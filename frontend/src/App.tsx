import { useState } from "react";
import "./theme.css";
import { AlertBanner } from "./components/AlertBanner";
import { ForecastTable } from "./components/ForecastTable";
import { FloodMap } from "./components/FloodMap";
import { SimulationSlider } from "./components/SimulationSlider";

function App() {
  // Lives here, not inside FloodMap or SimulationSlider, because both
  // of those components need it: the slider sets it, the map reads it.
  const [overlayUrl, setOverlayUrl] = useState<string | undefined>(undefined);

  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h1>FloodAI — Upper Sonoita Creek</h1>
      <AlertBanner />
      <FloodMap overlayUrl={overlayUrl} />
      <SimulationSlider onChange={(_T, url) => setOverlayUrl(url)} />
      <ForecastTable />
    </div>
  );
}

export default App;
