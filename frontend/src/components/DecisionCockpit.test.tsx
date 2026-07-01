import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DecisionCockpit } from "./DecisionCockpit";
import * as client from "../api/client";

describe("DecisionCockpit", () => {
  it("renders time-to-peak, life-safety, and uncertainty stats", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      time_to_peak_hours: { p10: 3.78, p50: 3.02, p90: 2.42, method: "Kirpich Tc + SCS Tlag" },
      life_safety: { prob_gt_0_5m_max_pct: 12.5, wet_pixels_above_0_5m: 340 },
      uncertainty_m: { max: 0.8, mean: 0.3 },
    });

    render(<DecisionCockpit />);

    expect(await screen.findByText("3.0 hrs")).toBeInTheDocument();
    expect(screen.getByText("12.5%")).toBeInTheDocument();
    expect(screen.getByText("± 0.30 m")).toBeInTheDocument();
    expect(screen.getByText(/Kirpich Tc/)).toBeInTheDocument();
  });
});
