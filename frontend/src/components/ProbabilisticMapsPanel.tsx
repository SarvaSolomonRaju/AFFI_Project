import { useState } from "react";
import { ApiImage } from "./ApiImage";
import { apiRasterUrl } from "../api/client";
import type { SimState } from "../types/api";
import { fmtFeet } from "../utils/units";

interface MapCard {
  title: string;
  who: string;
  meaning: string;
  action: string;
  outputPath: string;
}

const CARDS: MapCard[] = [
  {
    title: "Worst-Case Flood Depth (P90)",
    who: "EOC Staff · Public Works Director",
    meaning: "10% chance flooding exceeds this depth. Plan road closures and infrastructure protection against this map, not the median.",
    action: "Set barricade thresholds from this map. If P90 shows a road flooded, close it preemptively.",
    outputPath: "task4/today_worst.png",
  },
  {
    title: "Life-Safety Probability Map",
    who: "EOC Staff · Road Closure Coordinator",
    meaning: "Per-pixel probability (0–100%) that flood depth exceeds 0.5 m — the threshold where wading becomes dangerous. Primary evacuation trigger map.",
    action: "Any area above 50% probability warrants evacuation consideration. Red zones = act now.",
    outputPath: "task4/today_prob_gt_05m.png",
  },
  {
    title: "Forecast Uncertainty",
    who: "EOC Supervisor · Technical Reviewer",
    meaning: "Standard deviation of predicted depth across ensemble members. High uncertainty = ensemble members disagree = decide conservatively.",
    action: "In high-uncertainty areas, do not rely on the P50 map alone. Err toward P90 thresholds.",
    outputPath: "task4/today_uncertainty.png",
  },
];

// A raster card that works for simulation scenario images (direct static URL, no auth needed)
function ScenarioCard({
  title, who, meaning, action, rasterUrl, returnPeriod, isActive,
}: {
  title: string; who: string; meaning: string; action: string;
  rasterUrl: string; returnPeriod: number; isActive: boolean;
}) {
  const [failed, setFailed] = useState(false);
  const fullUrl = apiRasterUrl(rasterUrl);
  return (
    <div style={{
      background: "var(--bg-primary)",
      borderRadius: 8,
      overflow: "hidden",
      border: isActive ? "2px solid var(--accent-blue)" : "1px solid var(--border)",
    }}>
      {isActive && (
        <div style={{ background: "var(--accent-blue)", color: "white", fontSize: "0.7rem", fontWeight: 700, padding: "3px 8px", textAlign: "center" }}>
          SELECTED SCENARIO
        </div>
      )}
      {/* Thumbnail is cropped + line-thickened for legibility at this size
          (src/probabilistic/scenarios.py) — its background is transparent
          white-ish, not the dark navy the rest of this dashboard uses, so
          the flood-blue line actually has contrast to read against. */}
      <div style={{ height: 180, background: "#f0f3f6", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
        {failed ? (
          <span style={{ fontSize: "0.8rem", color: "#556", padding: 10, textAlign: "center" }}>
            Map not available for {returnPeriod}-year scenario
          </span>
        ) : (
          <img
            src={fullUrl}
            alt={title}
            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
            onError={() => setFailed(true)}
          />
        )}
      </div>
      <div style={{ padding: "10px 12px 14px" }}>
        <div style={{ fontWeight: 700, fontSize: "0.9rem", marginBottom: 2 }}>{title}</div>
        <div style={{ color: "var(--accent-blue)", fontSize: "0.75rem", marginBottom: 6 }}>{who}</div>
        <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: 6 }}>{meaning}</div>
        <div style={{
          fontSize: "0.78rem",
          background: "var(--bg-secondary)",
          borderLeft: "3px solid var(--accent-orange)",
          padding: "5px 8px",
          borderRadius: "0 4px 4px 0",
        }}>
          {action}
        </div>
      </div>
    </div>
  );
}

interface ProbabilisticMapsPanelProps {
  refreshSignal?: number;
  simState?: SimState | null;
  isSimulationMode?: boolean;
}

export function ProbabilisticMapsPanel({ refreshSignal, simState, isSimulationMode = false }: ProbabilisticMapsPanelProps) {
  const inSimMode = simState !== undefined;

  if (inSimMode) {
    if (!simState) {
      return (
        <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
          <h3 style={{ marginTop: 0 }}>Scenario Flood Maps</h3>
          <p style={{ color: "var(--text-secondary)" }}>Increase rainfall above 1" to see scenario flood maps.</p>
        </div>
      );
    }

    // In sim mode: show best/likely/worst scenario rasters (pre-computed flood library)
    const rpBest  = simState.return_period_best;
    const rpLikely = simState.return_period_yr;
    const rpWorst = simState.return_period_worst;

    return (
      <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
        <h3 style={{ marginTop: 0 }}>
          Scenario Flood Maps — Best / Likely / Worst Case
          <span style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 400, color: "var(--accent-orange)" }}>
            {isSimulationMode ? "SIMULATION" : "EXPLORING SCENARIO"}
          </span>
        </h3>
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 14px" }}>
          Pre-computed HEC-RAS flood library rasters. Best = {rpBest}yr event (forecast overestimate),
          Likely = {rpLikely}yr (selected scenario), Worst = {rpWorst}yr (forecast underestimate).
          These are the same maps used in the live forecast — now driven by your rainfall input.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 16 }}>
          <ScenarioCard
            title={`Best Case — ${rpBest}-Year`}
            who={`What if forecast overestimates? Use for optimistic planning.`}
            meaning={`Flooding if rainfall is ~${rpBest < rpLikely ? "lower" : "similar"} than selected scenario. Roads with water only in this map — might still be passable.`}
            action="Do NOT use as sole basis for keeping roads open. Check against Likely map first."
            rasterUrl={simState.raster_url_best_thumb}
            returnPeriod={rpBest}
            isActive={rpBest === rpLikely}
          />
          <ScenarioCard
            title={`Likely Scenario — ${rpLikely}-Year`}
            who="Primary decision map for this rainfall input"
            meaning={`Flood extent for ${simState.rainfall_in.toFixed(2)}" in 24 hrs. Max depth ${fmtFeet(simState.max_depth_m)}. This is the scenario driving the Action Plan and Bulletin above.`}
            action="Base your road closures and evacuation orders on this map. Cross-check with Worst case."
            rasterUrl={simState.raster_url_thumb}
            returnPeriod={rpLikely}
            isActive={true}
          />
          <ScenarioCard
            title={`Worst Case — ${rpWorst}-Year`}
            who="EOC Supervisor · Conservative planning baseline"
            meaning={`Flooding if rainfall exceeds the forecast or antecedent soil moisture is high. Use this for final barricade placements and infrastructure protection.`}
            action="Set barricade locations from this map. Any road shown flooded here must be closed preemptively."
            rasterUrl={simState.raster_url_worst_thumb}
            returnPeriod={rpWorst}
            isActive={rpWorst === rpLikely}
          />
        </div>
      </div>
    );
  }

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>Probabilistic Flood Maps</h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 16px" }}>
        Three decision maps derived from the full ensemble. Read together with the P50 (median) map on the interactive map above.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
        {CARDS.map((card) => (
          <div key={card.outputPath} style={{ background: "var(--bg-primary)", borderRadius: 8, overflow: "hidden", border: "1px solid var(--border)" }}>
            <ApiImage outputPath={card.outputPath} alt={card.title} style={{ width: "100%", display: "block" }} refreshSignal={refreshSignal} />
            <div style={{ padding: "10px 12px 14px" }}>
              <div style={{ fontWeight: 700, fontSize: "0.9rem", marginBottom: 2 }}>{card.title}</div>
              <div style={{ color: "var(--accent-blue)", fontSize: "0.75rem", marginBottom: 6 }}>{card.who}</div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: 6 }}>{card.meaning}</div>
              <div style={{ fontSize: "0.78rem", background: "var(--bg-secondary)", borderLeft: "3px solid var(--accent-orange)", padding: "5px 8px", borderRadius: "0 4px 4px 0" }}>
                {card.action}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
