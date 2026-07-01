import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { BulletinPanel } from "./BulletinPanel";
import * as client from "../api/client";

describe("BulletinPanel", () => {
  beforeEach(() => {
    // jsdom doesn't implement the Clipboard API — stub it so the
    // "Copy" button has something real to call. navigator.clipboard is
    // a getter-only property in jsdom, so Object.assign silently fails
    // to replace it; defineProperty is what actually works.
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
  });

  it("renders the bulletin text and copies it on click", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      alert_level: "WATCH",
      text: "FLOOD WATCH — UPPER SONOITA CREEK\n* WHAT: test",
    });

    render(<BulletinPanel />);

    // Text lives in a <textarea readOnly>'s value, not child text nodes
    // — getByText won't find it, getByDisplayValue is the right query.
    const box = await screen.findByDisplayValue(/FLOOD WATCH/);
    expect(box).toBeInTheDocument();

    // Plain fireEvent, not userEvent — userEvent.setup() installs its
    // own clipboard stub internally, which silently overwrote ours
    // and made the assertion below fail against the wrong function.
    fireEvent.click(screen.getByRole("button", { name: /copy/i }));

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
      "FLOOD WATCH — UPPER SONOITA CREEK\n* WHAT: test",
    );
    expect(await screen.findByRole("button", { name: /copied/i })).toBeInTheDocument();
  });

  it("falls back to selecting the text when the clipboard API is blocked", async () => {
    vi.spyOn(client, "apiGet").mockResolvedValue({
      alert_level: "WATCH",
      text: "FLOOD WATCH — UPPER SONOITA CREEK\n* WHAT: test",
    });
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockRejectedValue(new Error("Read permission denied")) },
      configurable: true,
    });

    render(<BulletinPanel />);
    await screen.findByDisplayValue(/FLOOD WATCH/);

    fireEvent.click(screen.getByRole("button", { name: /copy/i }));

    expect(await screen.findByRole("button", { name: /select/i })).toBeInTheDocument();
  });
});
