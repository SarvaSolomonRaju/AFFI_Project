import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ActionPanel } from "./ActionPanel";
import * as client from "../api/client";

describe("ActionPanel", () => {
  it("renders named roads/buildings and the legal citation", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      reference_scenario: "FEMA 1% annual chance (100-yr) flood",
      roads_to_barricade: { total_count: 154, top: [{ name: "Costello Drive", max_depth_m: 1.03 }] },
      buildings_to_evacuate: { total_count: 512, top: [{ name: "Stage Stop Inn", max_depth_m: 1.06 }] },
      legal_note: "Arizona Revised Statutes 28-910 ...",
    });

    render(<ActionPanel />);

    expect(await screen.findByText(/Costello Drive/)).toBeInTheDocument();
    expect(screen.getByText(/Stage Stop Inn/)).toBeInTheDocument();
    expect(screen.getByText(/28-910/)).toBeInTheDocument();
    expect(screen.getByText(/153 more, sorted by depth/)).toBeInTheDocument();
  });
});
