import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ForecastTable } from "./ForecastTable";
import * as client from "../api/client";

describe("ForecastTable", () => {
  it("renders one row per forecast day", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      generated_utc: "2026-06-30T00:00:00Z",
      forecast_days: [
        {
          day: 0,
          date: "2026-06-30",
          p10_24hr: 0,
          p50_24hr: 1.1,
          p90_24hr: 2.2,
          alert_level: "ADVISORY",
          return_period: { nearest_return_period: "< 2yr", severity_class: "Minor" },
        },
        {
          day: 1,
          date: "2026-07-01",
          p10_24hr: 0,
          p50_24hr: 0,
          p90_24hr: 0,
          alert_level: "GREEN",
          return_period: { nearest_return_period: "< 2yr", severity_class: "Minor" },
        },
      ],
    });

    render(<ForecastTable />);

    expect(await screen.findByText("2026-06-30")).toBeInTheDocument();
    expect(screen.getByText("2026-07-01")).toBeInTheDocument();
    expect(screen.getByText("1.10")).toBeInTheDocument();
    expect(screen.getByText("ADVISORY")).toBeInTheDocument();
  });
});
