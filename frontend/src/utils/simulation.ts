import type { AlertLevel, SimulationScenario, SimState } from "../types/api";
import { fmtAcres, fmtCfs, fmtFeet } from "./units";

// Scenario library alert levels use YELLOW/ORANGE/RED — map to our canonical set
function normalizeAlertLevel(raw: string): AlertLevel {
  switch (raw.toUpperCase()) {
    case "YELLOW":   return "ADVISORY";
    case "ORANGE":   return "WATCH";
    case "RED":      return "WARNING";
    case "GREEN":    return "GREEN";
    case "ADVISORY": return "ADVISORY";
    case "WATCH":    return "WATCH";
    case "WARNING":  return "WARNING";
    default:         return "ADVISORY";
  }
}

// Build the static URL for a scenario raster (served by StaticFiles mount — no auth)
export function simRasterUrl(returnPeriod: number): string {
  const t = String(returnPeriod).padStart(3, "0");
  return `/outputs/sim/depth_T${t}yr.png`;
}

// The creek channel is only ~1-2% of the full raster frame — real geography,
// not a bug, but it reads as an empty black box at small card-thumbnail size.
// This is the cropped + dilated version from scripts' scenario-library
// generation (src/probabilistic/scenarios.py _reproject_depth_to_png) —
// use this one for small previews, simRasterUrl() for the full interactive map.
export function simRasterThumbUrl(returnPeriod: number): string {
  const t = String(returnPeriod).padStart(3, "0");
  return `/outputs/sim/depth_T${t}yr_thumb.png`;
}

// NOAA Atlas 14 24-hour rainfall IDF for Santa Cruz County, AZ
export const IDF_24HR: Record<number, number> = {
  5:   1.68,
  10:  2.18,
  25:  2.90,
  50:  3.56,
  100: 4.32,
  200: 5.17,
};

export const RETURN_PERIODS = [5, 10, 25, 50, 100, 200] as const;
export const RAINFALL_MIN = 0.0;
export const RAINFALL_MAX = 6.0;
export const FLOOD_ONSET_RAINFALL = 1.0; // below this = no flood scenario

// Map rainfall → highest return period whose IDF threshold is crossed
// Returns null if below minimum flooding threshold
export function rainfallToReturnPeriod(
  rainfall_in: number,
  available: number[]
): number | null {
  if (rainfall_in < FLOOD_ONSET_RAINFALL) return null;
  const sorted = [...available].sort((a, b) => a - b);
  // Scenario list hasn't loaded yet (e.g. right after switching to
  // SIMULATION mode, before the /simulation/scenarios fetch resolves) --
  // without this, sorted[0] on an empty array is undefined, not null, and
  // that undefined leaked into a literal "/simulation/raster/undefined"
  // request further down the line.
  if (sorted.length === 0) return null;
  let selected = sorted[0]; // default to lowest
  for (const T of sorted) {
    const threshold = IDF_24HR[T];
    if (threshold !== undefined && rainfall_in >= threshold) selected = T;
  }
  return selected;
}

// Kirpich + SCS Lag time-to-peak for Upper Sonoita Creek
// L = 24 km channel length, S = 0.012 average slope
function kirpichTimeToPeak(rainfall_in: number) {
  const L_ft = 24.0 * 3280.84;
  const slope = 0.012;
  const Tc_h = (0.0078 * Math.pow(L_ft, 0.77) * Math.pow(slope, -0.385)) / 60.0;
  const Tlag = 0.6 * Tc_h;
  const D = 1.0;
  const Tp_base = Tlag + D / 2.0;
  const scale = 1.0 / (1.0 + 0.05 * Math.max(0, rainfall_in));
  return {
    p10: parseFloat((Tp_base * 1.25).toFixed(2)),
    p50: parseFloat((Tp_base * scale).toFixed(2)),
    p90: parseFloat((Tp_base * scale * 0.75).toFixed(2)),
  };
}

function depthToLifeSafetyPct(max_depth_m: number): number {
  if (max_depth_m <= 0) return 0;
  if (max_depth_m <= 0.3) return Math.round((max_depth_m / 0.3) * 12);
  if (max_depth_m <= 0.5) return Math.round(12 + ((max_depth_m - 0.3) / 0.2) * 28);
  if (max_depth_m <= 1.0) return Math.round(40 + ((max_depth_m - 0.5) / 0.5) * 42);
  return Math.min(97, Math.round(82 + (max_depth_m - 1.0) * 10));
}

export function buildSimState(
  rainfall_in: number,
  returnPeriod: number,
  scenario: SimulationScenario,
  allPeriods: number[],  // sorted list of all available return periods
): SimState {
  const ttp = kirpichTimeToPeak(rainfall_in);
  const sorted = [...allPeriods].sort((a, b) => a - b);
  const idx = sorted.indexOf(returnPeriod);
  const bestT  = idx > 0                  ? sorted[idx - 1] : sorted[0];
  const worstT = idx < sorted.length - 1  ? sorted[idx + 1] : sorted[sorted.length - 1];
  return {
    rainfall_in,
    return_period_yr:   returnPeriod,
    return_period_best:  bestT,
    return_period_worst: worstT,
    Q_cms:          scenario.Q_cms,
    max_depth_m:    scenario.max_depth_m,
    wet_area_km2:   scenario.wet_area_km2,
    roads_at_risk:  scenario.roads_at_risk,
    infra_at_risk:  scenario.infra_at_risk,
    alert_level:    normalizeAlertLevel(scenario.alert_level as string),
    severity:       scenario.severity,
    raster_url:     simRasterUrl(returnPeriod),
    raster_url_best:  simRasterUrl(bestT),
    raster_url_worst: simRasterUrl(worstT),
    raster_url_thumb:       simRasterThumbUrl(returnPeriod),
    raster_url_best_thumb:  simRasterThumbUrl(bestT),
    raster_url_worst_thumb: simRasterThumbUrl(worstT),
    time_to_peak_p10: ttp.p10,
    time_to_peak_p50: ttp.p50,
    time_to_peak_p90: ttp.p90,
    life_safety_pct: depthToLifeSafetyPct(scenario.max_depth_m),
    population_exposed: scenario.population_exposed,
    population_life_safety: scenario.population_life_safety,
  };
}

// Gamma unit hydrograph — same formula as manager_products.py
// q(t) = Qp * (t/tp)^α * exp(α * (1 - t/tp)),  α = 3.7
export function gammaHydro(Qp: number, tp: number, tArr: number[]): number[] {
  const alpha = 3.7;
  return tArr.map((t) => {
    if (t <= 0) return 0;
    const tau = t / tp;
    return Qp * Math.pow(tau, alpha) * Math.exp(alpha * (1 - tau));
  });
}

const ACTION_BY_LEVEL: Record<string, string> = {
  GREEN:    "Monitor conditions. No public action required.",
  ADVISORY: "Pre-stage sandbags and pumps at known trouble spots. Monitor forecast for escalation.",
  WATCH:    "Barricade low-water crossings. Notify schools and residents in the affected area.",
  WARNING:  "Evacuate all at-risk buildings NOW. Activate EOC at full staff. Barricade all listed roads. Issue public warning via all available channels.",
};

export function generateSimBulletin(sim: SimState, isSimulationMode: boolean = true): string {
  const action = ACTION_BY_LEVEL[sim.alert_level] ?? ACTION_BY_LEVEL.GREEN;
  return [
    isSimulationMode
      ? `SIMULATION — ${sim.alert_level} FLOOD SCENARIO`
      : `REFERENCE SCENARIO — ${sim.alert_level} FLOOD SCENARIO (${sim.return_period_yr}-YR EVENT)`,
    isSimulationMode
      ? `*** NOT A REAL FORECAST — FOR PLANNING PURPOSES ONLY ***`
      : `*** REAL FEMA/USGS SCENARIO DATA, NOT TODAY'S FORECAST — FOR PLANNING PURPOSES ONLY ***`,
    ``,
    `* SCENARIO: ${sim.rainfall_in.toFixed(2)}" rain in 24 hours (~${sim.return_period_yr}-year event)`,
    `* WATERSHED: Upper Sonoita Creek, Santa Cruz County, AZ`,
    `* PEAK DISCHARGE: ~${fmtCfs(sim.Q_cms)} at Sonoita Creek outlet (Patagonia, AZ)`,
    `* MAX FLOOD DEPTH: ${fmtFeet(sim.max_depth_m)}`,
    `* INUNDATED AREA: ~${fmtAcres(sim.wet_area_km2)}`,
    `* ROADS AT RISK: ${sim.roads_at_risk} segments`,
    `* INFRASTRUCTURE ELEMENTS AT RISK: ${sim.infra_at_risk}`,
    ...(sim.population_life_safety !== null
      ? [`* POPULATION AT LIFE-SAFETY RISK: ~${sim.population_life_safety.toLocaleString()} (WorldPop estimate, exceeds 0.5m depth)`]
      : []),
    ``,
    `* TIME TO PEAK FLOW: ~${sim.time_to_peak_p50.toFixed(1)} hours from storm onset`,
    `  (range: ${sim.time_to_peak_p90.toFixed(1)} hrs [fast-track] — ${sim.time_to_peak_p10.toFixed(1)} hrs [slow-track])`,
    ``,
    `* SEVERITY: ${sim.severity}`,
    `* ACTION: ${action}`,
    ``,
    `Source: AFFI probabilistic flood library (HEC-RAS, Upper Sonoita Creek).`,
    `IDF thresholds: NOAA Atlas 14, Santa Cruz County, AZ, 24-hour duration.`,
  ].join("\n");
}

export function rainfallLabel(rainfall_in: number, returnPeriod: number | null): string {
  if (returnPeriod === null) return "No flood scenario";
  return `${rainfall_in.toFixed(2)}" / ${returnPeriod}-year event`;
}
