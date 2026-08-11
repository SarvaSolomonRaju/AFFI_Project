import { useEffect, useMemo, useState } from "react";
import "./theme.css";
import { ModeToggle } from "./components/ModeToggle";
import { RainfallControl } from "./components/RainfallControl";
import { AlertBanner } from "./components/AlertBanner";
import { ForecastTable } from "./components/ForecastTable";
import { FloodMap } from "./components/FloodMap";
import { ActionPanel } from "./components/ActionPanel";
import { BulletinPanel } from "./components/BulletinPanel";
import { HistoricalComparison } from "./components/HistoricalComparison";
import { DecisionCockpit } from "./components/DecisionCockpit";
import { EnsembleHydrograph } from "./components/EnsembleHydrograph";
import { SevenDayOutlook } from "./components/SevenDayOutlook";
import { ProbabilisticMapsPanel } from "./components/ProbabilisticMapsPanel";
import { ModelPerformancePanel } from "./components/ModelPerformancePanel";
import { LiveGaugePanel } from "./components/LiveGaugePanel";
import { PrintSummaryButton } from "./components/PrintSummary";
import { ContactRosterPanel } from "./components/ContactRosterPanel";
import { MapSelectionPanel } from "./components/MapSelectionPanel";
import { DepthScalePanel } from "./components/DepthScaleReference";
import { EvacuationTimeBudget } from "./components/EvacuationTimeBudget";
import { StageRatingCurve } from "./components/StageRatingCurve";
import { OfficialAlertsPanel } from "./components/OfficialAlertsPanel";
import { ForecastVsReality } from "./components/ForecastVsReality";
import { RegionalSensorsPanel } from "./components/RegionalSensorsPanel";
import { DownloadMapsBar } from "./components/DownloadMapsBar";
import { OfficialFloodMapsPanel } from "./components/OfficialFloodMapsPanel";
import { TriageStrip } from "./components/TriageStrip";
import { ChatAssistant } from "./components/ChatAssistant";
import { apiGet, apiRasterUrl } from "./api/client";
import type { SimState, SimulationScenariosResponse } from "./types/api";
import { IDF_24HR, buildSimState, rainfallToReturnPeriod } from "./utils/simulation";

function DevPanel({ refreshSignal, simState }: { refreshSignal: number; simState?: SimState | null }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginTop: 40, borderTop: "1px dashed var(--border)" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          background: "none",
          border: "1px solid var(--border)",
          color: "var(--text-secondary)",
          cursor: "pointer",
          fontSize: "0.78rem",
          padding: "6px 14px",
          borderRadius: 6,
          marginTop: 12,
          display: "block",
          marginLeft: "auto",
          marginRight: "auto",
        }}
      >
        {open ? "▲ Hide Developer View" : "▼ Developer View — Model Diagnostics"}
      </button>
      {open && (
        <div style={{ marginTop: 8, padding: "4px 0 20px" }}>
          <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)", textAlign: "center", marginBottom: 12, opacity: 0.6 }}>
            FOR TECHNICAL STAFF — not displayed in flood manager view
          </div>
          <ModelPerformancePanel refreshSignal={refreshSignal} simState={simState} />
        </div>
      )}
    </div>
  );
}

function App() {
  const [mode, setMode] = useState<"live" | "sim">("live");
  const [refreshSignal, setRefreshSignal] = useState(0);

  // Scenario library — fetched once here (not inside RainfallControl) because
  // the map's return-period explorer needs it too, and both controls must
  // agree on the exact same scenario data or they can silently disagree.
  const [scenarios, setScenarios] = useState<SimulationScenariosResponse | null>(null);
  useEffect(() => {
    apiGet<SimulationScenariosResponse>("/api/v1/simulation/scenarios").then(setScenarios);
  }, []);

  // rainfall: the sim-mode slider's continuous position (inches). Only
  // meaningful in sim mode.
  const [rainfall, setRainfall] = useState(2.18); // default: 10yr event

  // exploreRP: set only when the user clicks a return-period button on the
  // FloodMap's explorer strip WHILE IN LIVE MODE. Previously this lived as
  // local state inside FloodMap itself, so clicking "5yr" on the map changed
  // the map's own rendering but nothing else — Action Plan, Bulletin, Decision
  // Cockpit etc kept showing whatever the rainfall slider (or nothing, in live
  // mode) last produced. That mismatch — map says one return period,
  // everything else says another — is fixed by making this the single shared
  // source of truth for both modes instead of two disconnected states.
  const [exploreRP, setExploreRP] = useState<number | null>(null);

  // In sim mode there is exactly one source of truth: the slider. The map's
  // explorer buttons move the slider (see handleMapSelectRP) rather than
  // keeping a second, independent notion of "selected return period" — so
  // the map and the rest of the dashboard can never disagree by construction.
  // In live mode, nothing is active unless the user explicitly explores one
  // via the map.
  const activeRP = mode === "sim"
    ? rainfallToReturnPeriod(rainfall, scenarios?.return_periods_yr ?? [])
    : exploreRP;

  const simState = useMemo<SimState | null>(() => {
    if (!scenarios || activeRP === null) return null;
    const scenario = scenarios.scenarios[String(activeRP)];
    if (!scenario) return null;
    // Sim mode: use the slider's exact rainfall value. Live-mode exploration
    // has no slider position, so fall back to that return period's own IDF
    // threshold — still a real, labeled number, not a guess.
    const rainfallForScenario = mode === "sim" ? rainfall : (IDF_24HR[activeRP] ?? rainfall);
    return buildSimState(rainfallForScenario, activeRP, scenario, scenarios.return_periods_yr);
  }, [scenarios, activeRP, mode, rainfall]);

  // simStateProp convention used by every child panel: undefined = true live
  // fetch, null/SimState = show scenario data. Sim mode always shows scenario
  // data (even the "no flood" null case); live mode only does so while a map
  // exploration is active — otherwise every panel fetches real forecast data.
  const simStateProp = (mode === "sim" || exploreRP !== null) ? simState : undefined;

  const overlayUrl = simStateProp !== undefined && simState
    ? apiRasterUrl(simState.raster_url)
    : undefined;

  function handleModeChange(newMode: "live" | "sim") {
    setMode(newMode);
    if (newMode === "live") {
      setRefreshSignal((n) => n + 1);
      setExploreRP(null);
    }
  }

  // Called when the user clicks a return-period button on the map itself.
  // Sim mode: move the slider (there's only ever one shared state). Live
  // mode: set the temporary explore override that every panel picks up.
  function handleMapSelectRP(rp: number | null) {
    if (mode === "sim") {
      if (rp !== null) setRainfall(IDF_24HR[rp]);
    } else {
      setExploreRP(rp);
    }
  }

  return (
    <div id="dashboard-root" style={{ padding: "28px 24px 40px", maxWidth: 1120, margin: "0 auto" }}>
      {/* Editorial masthead / command bar */}
      <header style={{
        display: "flex", justifyContent: "space-between", alignItems: "flex-start",
        flexWrap: "wrap", gap: 16, paddingBottom: 16, marginBottom: 18,
        borderBottom: "2px solid var(--border-strong)",
      }}>
        <div style={{ display: "flex", gap: 14, alignItems: "flex-start" }}>
          {/* Warning-system mark — a wave + rising level, not an "AI" badge */}
          <div style={{
            width: 44, height: 44, borderRadius: 10, flexShrink: 0,
            background: "var(--accent)", color: "#fff",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "var(--shadow-card)", marginTop: 2,
          }}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M2 15c2 0 2-1.6 4-1.6s2 1.6 4 1.6 2-1.6 4-1.6 2 1.6 4 1.6 2-1.6 4-1.6" stroke="#fff" strokeWidth="1.8" strokeLinecap="round"/>
              <path d="M2 19c2 0 2-1.6 4-1.6s2 1.6 4 1.6 2-1.6 4-1.6 2 1.6 4 1.6 2-1.6 4-1.6" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" opacity="0.55"/>
              <path d="M12 3.2l2.6 4.4h-5.2L12 3.2z" fill="#fff"/>
              <rect x="11.2" y="8.2" width="1.6" height="2.2" rx="0.8" fill="#fff"/>
            </svg>
          </div>
          <div>
            <div style={{
              fontSize: "var(--text-2xs)", fontWeight: 800, letterSpacing: "0.14em",
              textTransform: "uppercase", color: "var(--accent-ink)", marginBottom: 2,
            }}>
              Arizona Flash-Flood Inundation AI · Early Warning System
            </div>
            <h1 style={{ margin: 0 }}>Upper Sonoita Creek</h1>
            <div style={{ fontSize: "var(--text-xs)", color: "var(--text-secondary)", marginTop: 3 }}>
              HUC-12 150503010204 · Patagonia, Santa Cruz County, AZ · pour point USGS 09481500
            </div>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          {mode === "live" && (
            <button
              onClick={() => setRefreshSignal((n) => n + 1)}
              style={{ padding: "7px 14px", borderRadius: "var(--radius-sm)", border: "1px solid var(--border-strong)", cursor: "pointer", background: "var(--bg-card)", color: "var(--text-primary)", fontWeight: 600, fontSize: "0.82rem" }}
            >
              ↻ Refresh now
            </button>
          )}
          <PrintSummaryButton />
          <ModeToggle mode={mode} onChange={handleModeChange} />
        </div>
      </header>

      {mode === "live" ? (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.82rem", marginTop: 0, marginBottom: 16, display: "flex", alignItems: "center", gap: 7 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--status-good)", display: "inline-block", flexShrink: 0 }} />
          Live forecast · auto-refreshes every 60 s — no manual reload needed during an active event.
        </p>
      ) : (
        <p style={{ color: "var(--accent-orange)", fontSize: "0.82rem", marginTop: 0, marginBottom: 16, fontWeight: 700, letterSpacing: "0.02em" }}>
          ▲ SIMULATION MODE — no real forecast data. Slide the rainfall bar to explore what-if scenarios.
        </p>
      )}

      {/* Simulation controls — only visible in sim mode */}
      {mode === "sim" && (
        <RainfallControl rainfall={rainfall} onRainfallChange={setRainfall} simState={simState} />
      )}

      {/* All panels — receive simStateProp (undefined=live, null=sim/no-flood, SimState=sim/active).
          isSimulationMode is passed separately from simState: simState alone can't tell a panel
          whether it's showing the rainfall-slider's what-if (mode==="sim") or a return-period
          explored while still in LIVE mode (exploreRP!==null) — those are different situations
          that read the same today's-real-forecast-vs-hypothetical distinction FloodMap.tsx already
          gets right (isSimulation vs isExploring) but every other panel was labeling both
          "SIMULATION," even while the mode toggle still said LIVE FORECAST. */}
      {/* Ordered for EOC scanning: alert -> spatial picture -> time-sensitive decision data -> supporting detail */}
      <AlertBanner refreshSignal={refreshSignal} simState={simStateProp} isSimulationMode={mode === "sim"} />
      {/* The 3-second situational summary — how bad, how long, who's at risk,
          what to do — sits immediately under our alert so a manager grasps the
          whole picture before scrolling. Live mode only. */}
      {mode === "live" && <TriageStrip refreshSignal={refreshSignal} />}
      {/* The authoritative NWS word sits right under our own alert — always
          in live mode, so our model is never read in isolation. */}
      {mode === "live" && <OfficialAlertsPanel refreshSignal={refreshSignal} />}

      <div className="zone-label">Live Decision Support</div>
      <FloodMap
        overlayUrl={overlayUrl}
        isSimulation={mode === "sim"}
        activeRP={activeRP}
        onSelectReturnPeriod={handleMapSelectRP}
        simState={simState}
        refreshSignal={refreshSignal}
      />

      <MapSelectionPanel refreshSignal={refreshSignal} simState={simStateProp} isSimulationMode={mode === "sim"} />
      <DecisionCockpit refreshSignal={refreshSignal} simState={simStateProp} isSimulationMode={mode === "sim"} />
      <DepthScalePanel refreshSignal={refreshSignal} simState={simStateProp} />
      <OfficialFloodMapsPanel />
      <EvacuationTimeBudget refreshSignal={refreshSignal} simState={simStateProp} />
      <ActionPanel refreshSignal={refreshSignal} simState={simStateProp} isSimulationMode={mode === "sim"} />
      <EnsembleHydrograph refreshSignal={refreshSignal} simState={simStateProp} isSimulationMode={mode === "sim"} />
      <StageRatingCurve refreshSignal={refreshSignal} simState={simStateProp} />

      <ProbabilisticMapsPanel refreshSignal={refreshSignal} simState={simStateProp} isSimulationMode={mode === "sim"} />
      <BulletinPanel refreshSignal={refreshSignal} simState={simStateProp} isSimulationMode={mode === "sim"} />

      <div className="zone-label">History &amp; Forecast Verification</div>
      <HistoricalComparison refreshSignal={refreshSignal} simState={simStateProp} isSimulationMode={mode === "sim"} />
      {mode === "live" && <ForecastVsReality refreshSignal={refreshSignal} />}

      <div className="zone-label">Live Sensors &amp; Reference Data</div>
      <LiveGaugePanel refreshSignal={refreshSignal} />
      {mode === "live" && <RegionalSensorsPanel refreshSignal={refreshSignal} />}
      <DownloadMapsBar />
      <ContactRosterPanel refreshSignal={refreshSignal} />
      <SevenDayOutlook refreshSignal={refreshSignal} simState={simStateProp} isSimulationMode={mode === "sim"} />

      {/* Forecast table — raw numbers, only meaningful in live mode */}
      {mode === "live" && <ForecastTable refreshSignal={refreshSignal} />}

      <DevPanel refreshSignal={refreshSignal} simState={simStateProp} />

      {/* Floating "explain this to me" assistant — available on every view. */}
      <ChatAssistant />
    </div>
  );
}

export default App;
