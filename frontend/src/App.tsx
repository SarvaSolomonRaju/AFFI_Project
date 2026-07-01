import "./theme.css";
import { AlertBanner } from "./components/AlertBanner";
import { ForecastTable } from "./components/ForecastTable";

function App() {
  return (
    <div style={{ padding: 24, maxWidth: 900, margin: "0 auto" }}>
      <h1>FloodAI — Upper Sonoita Creek</h1>
      <AlertBanner />
      <ForecastTable />
    </div>
  );
}

export default App;
