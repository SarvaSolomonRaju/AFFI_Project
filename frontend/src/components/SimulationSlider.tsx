import { useEffect, useState } from "react";
import { apiGet, apiRasterUrl } from "../api/client";
import type { SimulationScenariosResponse } from "../types/api";

interface SimulationSliderProps {
  // Tells the parent (App) which return period is selected, so it can
  // pass the matching raster URL down into FloodMap. This is "lifting
  // state up" — two sibling components (this slider and the map) both
  // need the same value, so it lives in their shared parent instead of
  // in either one of them.
  onChange: (returnPeriod: number, rasterUrl: string) => void;
}

export function SimulationSlider({ onChange }: SimulationSliderProps) {
  const [data, setData] = useState<SimulationScenariosResponse | null>(null);
  const [index, setIndex] = useState(4); // default preview: 100-yr scenario
  // Only true once the user actually drags the slider. Without this,
  // the map would silently switch to the simulation overlay the moment
  // this component loads — before anyone touched anything — which is
  // exactly the "simulation looks like it's live" confusion this was
  // built to avoid.
  const [touched, setTouched] = useState(false);

  useEffect(() => {
    apiGet<SimulationScenariosResponse>("/api/v1/simulation/scenarios").then(setData);
  }, []);

  // Tell the parent which scenario is active — but only after the user
  // has interacted. Until then, FloodMap keeps showing today's real
  // forecast, not this component's default preview value.
  useEffect(() => {
    if (!data || !touched) return;
    const T = data.return_periods_yr[index];
    const scenario = data.scenarios[String(T)];
    onChange(T, apiRasterUrl(scenario.raster_url));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, index, touched]);

  if (!data) return <p>Loading simulation scenarios…</p>;

  const T = data.return_periods_yr[index];
  const s = data.scenarios[String(T)];

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>Simulation Mode — what if a {T}-year storm hit today?</h3>
      <input
        type="range"
        min={0}
        max={data.return_periods_yr.length - 1}
        value={index}
        onChange={(e) => {
          setTouched(true);
          setIndex(Number(e.target.value));
        }}
        style={{ width: "100%" }}
      />
      <div style={{ display: "flex", gap: 24, marginTop: 12, flexWrap: "wrap" }}>
        <div>Discharge (Q): <strong>{s.Q_cms} cms</strong></div>
        <div>Max depth: <strong>{s.max_depth_m} m</strong></div>
        <div>Wet area: <strong>{s.wet_area_km2} km²</strong></div>
        <div>Roads at risk: <strong>{s.roads_at_risk}</strong></div>
        <div>Buildings at risk: <strong>{s.infra_at_risk}</strong></div>
        <div>Chance in any given year: <strong>{s.probability}</strong></div>
      </div>
    </div>
  );
}
