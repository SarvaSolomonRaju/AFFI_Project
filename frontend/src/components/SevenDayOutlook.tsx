import { useState } from "react";
import { useLiveData } from "../hooks/useLiveData";
import { apiRasterUrl } from "../api/client";
import type { SevenDayDetailResponse, AlertLevel, SimState } from "../types/api";
import { fmtAcres, fmtFeet } from "../utils/units";
import { alertIcon } from "../utils/alertLevel";
import { StaleBadge } from "./StaleBadge";
import { SevenDayRiskStrip } from "./SevenDayRiskStrip";

const ALERT_BG: Record<string, { bg: string; color: string }> = {
  GREEN:    { bg: "#27ae60", color: "white" },
  ADVISORY: { bg: "#f39c12", color: "black" },
  WATCH:    { bg: "#e67e22", color: "white" },
  WARNING:  { bg: "#c0392b", color: "white" },
};

function alertBg(level: AlertLevel): { bg: string; color: string } {
  switch (level) {
    case "WARNING":  return { bg: "#c0392b", color: "white" };
    case "WATCH":    return { bg: "#e67e22", color: "white" };
    case "ADVISORY": return { bg: "#f39c12", color: "black" };
    default:         return { bg: "#27ae60", color: "white" };
  }
}

function DayThumbnail({ url, day, noFlood, refreshSignal }: {
  url: string; day: number; noFlood: boolean; refreshSignal?: number;
}) {
  const [failed, setFailed] = useState(false);
  const cacheBust = refreshSignal ? `?v=${refreshSignal}` : "";
  return (
    <div style={{ height: 100, background: "#0a1520", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
      {noFlood || failed ? (
        <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)", padding: 6, textAlign: "center" }}>
          {failed ? "Image unavailable" : "No flooding"}
        </span>
      ) : (
        <img
          src={`${apiRasterUrl(url)}${cacheBust}`}
          alt={`Day ${day} flood extent`}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}

// Separate component so hooks are always called unconditionally
function SimOutlook({ simState, isSimulationMode }: { simState: SimState | null; isSimulationMode: boolean }) {
  const [imgFailed, setImgFailed] = useState(false);

  const hasScenario = simState !== null;
  const simDays = [
    { day: 0, label: "Today",   level: hasScenario ? simState!.alert_level : "GREEN", depth: hasScenario ? simState!.max_depth_m : 0, wetArea: hasScenario ? simState!.wet_area_km2 : 0, showRaster: true },
    { day: 1, label: "+1 day",  level: hasScenario && simState!.max_depth_m > 1 ? "ADVISORY" : "GREEN", depth: hasScenario ? simState!.max_depth_m * 0.4 : 0, wetArea: hasScenario ? simState!.wet_area_km2 * 0.3 : 0, showRaster: false },
    { day: 2, label: "+2 days", level: "GREEN", depth: hasScenario ? simState!.max_depth_m * 0.1 : 0, wetArea: 0, showRaster: false },
    { day: 3, label: "+3 days", level: "GREEN", depth: 0, wetArea: 0, showRaster: false },
    { day: 4, label: "+4 days", level: "GREEN", depth: 0, wetArea: 0, showRaster: false },
    { day: 5, label: "+5 days", level: "GREEN", depth: 0, wetArea: 0, showRaster: false },
    { day: 6, label: "+6 days", level: "GREEN", depth: 0, wetArea: 0, showRaster: false },
  ];

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>
        7-Day Outlook — {isSimulationMode ? "Simulation" : "Exploring Scenario"}
        <span style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 400, color: "var(--accent-orange)" }}>
          Day 0 = scenario · Days 1–6 = synthetic recession
        </span>
      </h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 14px" }}>
        {hasScenario
          ? `Day 0 shows the ${simState!.return_period_yr}-year scenario flood extent. Days 1–6 show synthetic recession — no multi-day GFS forecast in ${isSimulationMode ? "simulation mode" : "this reference scenario"}.`
          : "Increase rainfall above 1\" to see the scenario flood extent."}
      </p>
      <div style={{ display: "flex", gap: 10, overflowX: "auto", paddingBottom: 6 }}>
        {simDays.map((d) => {
          const badge = ALERT_BG[d.level] ?? ALERT_BG.GREEN;
          return (
            <div key={d.day} style={{ minWidth: 130, background: "var(--bg-primary)", borderRadius: 8, overflow: "hidden", border: "1px solid var(--border)", flexShrink: 0 }}>
              <div style={{ background: badge.bg, color: badge.color, fontSize: "0.7rem", fontWeight: 700, padding: "3px 8px", textAlign: "center" }}>
                {alertIcon(d.level)} {d.level}
              </div>
              <div style={{ height: 100, background: "#f0f3f6", display: "flex", alignItems: "center", justifyContent: "center", overflow: "hidden" }}>
                {d.showRaster && hasScenario && !imgFailed ? (
                  <img
                    src={apiRasterUrl(simState!.raster_url_thumb)}
                    alt={`Scenario flood extent`}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    onError={() => setImgFailed(true)}
                  />
                ) : (
                  <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)", padding: 6, textAlign: "center" }}>
                    {d.depth > 0 ? `~${fmtFeet(d.depth)}` : "No flooding"}
                  </span>
                )}
              </div>
              <div style={{ padding: "8px 8px 10px", fontSize: "0.78rem" }}>
                <div style={{ fontWeight: 600, marginBottom: 2 }}>{d.label}</div>
                <div style={{ color: "var(--text-secondary)" }}>Max: {fmtFeet(d.depth, 2)}</div>
                <div style={{ color: "var(--text-secondary)" }}>Wet: {fmtAcres(d.wetArea)}</div>
                {d.day === 0 && hasScenario && (
                  <div style={{ color: "var(--accent-orange)", fontSize: "0.7rem", marginTop: 2 }}>
                    {simState!.return_period_yr}yr event
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

interface SevenDayOutlookProps {
  refreshSignal?: number;
  simState?: SimState | null;
  isSimulationMode?: boolean;
}

export function SevenDayOutlook({ refreshSignal, simState, isSimulationMode = false }: SevenDayOutlookProps) {
  const inSimMode = simState !== undefined;
  const { data, error, lastUpdated } = useLiveData<SevenDayDetailResponse>(
    "/api/v1/forecast/7day-detail",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  if (inSimMode) return <SimOutlook simState={simState ?? null} isSimulationMode={isSimulationMode} />;

  if (error && !data) return <p>Could not load 7-day outlook: {error}</p>;
  if (!data) return <p>Loading 7-day outlook…</p>;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>7-Day Flood Outlook</h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 10px" }}>
        Bar height = how deep the water gets each day; color = alert level; dashed cap = worst case. Getting better or worse this week, at a glance.
      </p>
      <SevenDayRiskStrip data={data} />
      <div style={{ fontWeight: 600, fontSize: "0.82rem", color: "var(--text-secondary)", margin: "14px 0 8px" }}>
        Daily likely flood-extent maps
      </div>
      <div style={{ display: "flex", gap: 10, overflowX: "auto", paddingBottom: 6 }}>
        {data.days.map((d) => {
          const badge = alertBg(d.alert_level);
          const noFlood = d.likely.max_depth_m === 0;
          return (
            <div key={d.day} style={{ minWidth: 130, background: "var(--bg-primary)", borderRadius: 8, overflow: "hidden", border: "1px solid var(--border)", flexShrink: 0 }}>
              <div style={{ background: badge.bg, color: badge.color, fontSize: "0.7rem", fontWeight: 700, padding: "3px 8px", textAlign: "center" }}>
                {d.alert_level}
              </div>
              <DayThumbnail url={d.likely.thumbnail_url} day={d.day} noFlood={noFlood} refreshSignal={refreshSignal} />
              <div style={{ padding: "8px 8px 10px", fontSize: "0.78rem" }}>
                <div style={{ fontWeight: 600, marginBottom: 2 }}>
                  {new Date(d.date + "T12:00:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                </div>
                <div style={{ color: "var(--text-secondary)" }}>Max: {fmtFeet(d.likely.max_depth_m, 2)}</div>
                <div style={{ color: "var(--text-secondary)" }}>Wet: {fmtAcres(d.likely.wet_area_km2)}</div>
                {!noFlood && d.worst.max_depth_m > d.likely.max_depth_m && (
                  <div style={{ color: "#e74c3c", fontSize: "0.73rem", marginTop: 2 }}>
                    Worst: {fmtFeet(d.worst.max_depth_m, 2)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      <p style={{ fontSize: "0.75rem", color: "var(--text-secondary)", marginTop: 10, marginBottom: 0 }}>
        Generated: {data.generated_utc} — thumbnails show P50 (likely scenario) flood depth.
      </p>
    </div>
  );
}
