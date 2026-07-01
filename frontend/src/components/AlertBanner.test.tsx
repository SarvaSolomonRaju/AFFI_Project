import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AlertBanner } from "./AlertBanner";
import * as client from "../api/client";

// Same idea as mocking requests.get in a pytest test — we don't want a
// real network call in a unit test, just control what apiGet returns
// and check the component renders it correctly.
describe("AlertBanner", () => {
  it("shows the current alert level and color class once data arrives", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      current_alert: "WATCH",
      max_7day_alert: "WARNING",
      generated_utc: "2026-06-30T00:00:00Z",
      watershed: {},
      data_source: "test",
    });

    render(<AlertBanner />);

    const banner = await screen.findByText(/WATCH/);
    expect(banner.closest(".alert-watch")).not.toBeNull();
  });

  it("shows an error message if the backend is unreachable", async () => {
    vi.spyOn(client, "apiGet").mockRejectedValue(new Error("network down"));

    render(<AlertBanner />);

    expect(await screen.findByText(/Could not reach the backend/)).toBeInTheDocument();
  });
});
