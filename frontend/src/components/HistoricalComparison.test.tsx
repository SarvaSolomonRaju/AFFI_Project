import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { HistoricalComparison } from "./HistoricalComparison";
import * as client from "../api/client";

describe("HistoricalComparison", () => {
  it("renders the closest event with its date and source", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      today_discharge_cms: 10.0,
      closest_event: {
        name: "August 2017 Monsoon Flood",
        date: "2017-08-02",
        season: "monsoon",
        rainfall_24hr_in: 1.9,
        peak_q_cms: 12.0,
        peak_stage_m: 0.95,
        approx_return_period_yr: 5,
        source: "USGS 09481500 + ADWR monsoon report",
        notes: "Moderate monsoon event with brief overbank flow.",
      },
      delta_pct_vs_closest_event: -16.7,
      catalog_size: 4,
      catalog_source: "Curated catalog of documented Sonoita Creek flood events.",
    });

    render(<HistoricalComparison />);

    expect(await screen.findByText(/August 2017 Monsoon Flood/)).toBeInTheDocument();
    expect(screen.getByText(/2017-08-02/)).toBeInTheDocument();
    expect(screen.getByText(/USGS 09481500/)).toBeInTheDocument();
    expect(screen.getByText(/-16.7%/)).toBeInTheDocument();
  });

  it("uses 'no flow forecasted' framing instead of a meaningless -100% on dry days", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      today_discharge_cms: 0,
      closest_event: {
        name: "August 2008 Heavy Rain Event",
        date: "2008-08-01",
        season: "monsoon",
        rainfall_24hr_in: 1.6,
        peak_q_cms: 7.5,
        peak_stage_m: 0.75,
        approx_return_period_yr: 3,
        source: "USGS 09481500",
        notes: "Typical monsoon-season pulse; modest flooding.",
      },
      delta_pct_vs_closest_event: null,
      catalog_size: 4,
      catalog_source: "Curated catalog.",
    });

    render(<HistoricalComparison />);

    expect(await screen.findByText(/No flow forecasted today/)).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });
});
