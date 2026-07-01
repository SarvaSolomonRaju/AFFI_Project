import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SimulationSlider } from "./SimulationSlider";
import * as client from "../api/client";

const SCENARIOS = {
  return_periods_yr: [5, 10, 25, 50, 100, 200],
  scenarios: {
    "5": { Q_cms: 166, max_depth_m: 8.02, wet_area_km2: 5.25, roads_at_risk: 82, infra_at_risk: 4, alert_level: "YELLOW", severity: "Minor", probability: "20%", raster_url: "/api/v1/simulation/raster/5" },
    "100": { Q_cms: 455, max_depth_m: 12.0, wet_area_km2: 5.28, roads_at_risk: 154, infra_at_risk: 12, alert_level: "RED", severity: "Severe", probability: "1%", raster_url: "/api/v1/simulation/raster/100" },
  },
};

describe("SimulationSlider", () => {
  it("previews the 100-yr scenario without telling the parent, until touched", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue(SCENARIOS);
    vi.spyOn(client, "apiRasterUrl").mockImplementation((p) => `http://localhost:8000${p}`);
    const onChange = vi.fn();

    render(<SimulationSlider onChange={onChange} />);

    // Shows a default preview (100-yr) so the panel isn't empty, but
    // does NOT tell the parent yet — the map must keep showing today's
    // real forecast until the user actually drags the slider.
    expect(await screen.findByText(/100-year storm/)).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("dragging the slider reports the scenario to the parent for the first time", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue(SCENARIOS);
    vi.spyOn(client, "apiRasterUrl").mockImplementation((p) => `http://localhost:8000${p}`);
    const onChange = vi.fn();

    render(<SimulationSlider onChange={onChange} />);
    await screen.findByText(/100-year storm/);

    fireEvent.change(screen.getByRole("slider"), { target: { value: "0" } });

    expect(await screen.findByText(/5-year storm/)).toBeInTheDocument();
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith(5, "http://localhost:8000/api/v1/simulation/raster/5");
  });
});
