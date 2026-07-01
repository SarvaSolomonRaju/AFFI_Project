import "./theme.css";
import { AlertBanner } from "./components/AlertBanner";
import { ForecastTable } from "./components/ForecastTable";
import { FloodMap } from "./components/FloodMap";

function App() {
  return (
    <div style={{ padding: 24, maxWidth: 1100, margin: "0 auto" }}>
      <h1>FloodAI — Upper Sonoita Creek</h1>
      <AlertBanner />
      <FloodMap />
      <ForecastTable />
    </div>
  );
}

export default App;
