import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ActionPanel } from "./ActionPanel";
import * as client from "../api/client";

describe("ActionPanel", () => {
  it("renders named roads/buildings, category, and the legal citation", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      reference_scenario: "FEMA 1% annual chance (100-yr) flood",
      roads_to_barricade: { total_count: 154, top: [{ name: "Costello Drive", max_depth_m: 1.03 }] },
      buildings_to_evacuate: {
        total_count: 512,
        top: [{ name: "Stage Stop Inn", max_depth_m: 1.06, category: "Commercial/Industrial" }],
      },
      schools_in_flood_zone: [],
      legal_note: "Arizona Revised Statutes 28-910 ...",
    });

    render(<ActionPanel />);

    expect(await screen.findByText(/Costello Drive/)).toBeInTheDocument();
    expect(screen.getByText(/Stage Stop Inn/)).toBeInTheDocument();
    expect(screen.getByText(/Commercial\/Industrial/)).toBeInTheDocument();
    expect(screen.getByText(/28-910/)).toBeInTheDocument();
    expect(screen.getByText(/153 more, sorted by depth/)).toBeInTheDocument();
    expect(screen.getByText(/No schools in the flood zone/)).toBeInTheDocument();
  });

  it("calls out schools prominently when any are in the flood zone", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      reference_scenario: "FEMA 1% annual chance (100-yr) flood",
      roads_to_barricade: { total_count: 0, top: [] },
      buildings_to_evacuate: { total_count: 1, top: [{ name: "Patagonia Elementary", max_depth_m: 0.3, category: "School" }] },
      schools_in_flood_zone: [{ name: "Patagonia Elementary", max_depth_m: 0.3 }],
      legal_note: "Arizona Revised Statutes 28-910 ...",
    });

    render(<ActionPanel />);

    expect(await screen.findByText(/1 school in the flood zone — evacuate first: Patagonia Elementary/)).toBeInTheDocument();
  });
});
