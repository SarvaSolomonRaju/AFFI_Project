import { renderHook } from "@testing-library/react";
import { act } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useLiveData } from "./useLiveData";
import * as client from "../api/client";

describe("useLiveData", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Each test below shares the same "/api/v1/thing" path — without this,
    // a successful fetch cached (localStorage) by one test leaks into the
    // next as "last known good" data, since that's now deliberate behavior,
    // not a bug (see the last-known-good test further down).
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches immediately, then again every intervalMs", async () => {
    const apiGetSpy = vi.spyOn(client, "apiGet").mockResolvedValue({ value: 1 });

    const { unmount } = renderHook(() => useLiveData("/api/v1/thing", 60_000));
    // Flush the microtask the mocked apiGet() promise resolves on —
    // fake timers freeze setTimeout/setInterval, not microtasks, so a
    // plain awaited act() (no time advance) is enough for the initial
    // fetch that fires on mount.
    await act(async () => {});
    expect(apiGetSpy).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(apiGetSpy).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(apiGetSpy).toHaveBeenCalledTimes(3);
    unmount(); // stop the interval — otherwise it keeps firing into later tests
  });

  it("refetches immediately when refreshSignal changes, without waiting for the interval", async () => {
    const apiGetSpy = vi.spyOn(client, "apiGet").mockResolvedValue({ value: 1 });

    const { rerender, unmount } = renderHook(
      ({ signal }) => useLiveData("/api/v1/thing", 60_000, signal),
      { initialProps: { signal: 0 } },
    );
    await act(async () => {});
    // Delta, not an absolute count: another test's hook instance in
    // this file may not have unmounted (and thus stopped polling) by
    // the exact microtask this assertion runs in — the actual claim
    // this test makes is narrower: "changing refreshSignal causes
    // exactly one more fetch," regardless of what else is in flight.
    const before = apiGetSpy.mock.calls.length;

    // No time has passed — only a manual "refresh now" trigger.
    rerender({ signal: 1 });
    await act(async () => {});
    expect(apiGetSpy.mock.calls.length).toBe(before + 1);
    unmount();
  });

  it("sets error state and leaves data null when the fetch fails with no prior success", async () => {
    vi.spyOn(client, "apiGet").mockRejectedValue(new Error("network down"));

    const { result, unmount } = renderHook(() => useLiveData("/api/v1/thing", 60_000));
    await act(async () => {});

    expect(result.current.error).toBe("Error: network down");
    expect(result.current.data).toBeNull();
    expect(result.current.isStale).toBe(true);
    unmount();
  });

  it("keeps the last successful data (labeled stale) when a later fetch fails", async () => {
    // A dropped connection mid-event is exactly the case this exists for —
    // the dashboard should keep showing the last real data, not go blank.
    const apiGetSpy = vi.spyOn(client, "apiGet").mockResolvedValueOnce({ value: 42 });

    const { result, unmount } = renderHook(() => useLiveData("/api/v1/thing", 60_000));
    await act(async () => {});
    expect(result.current.data).toEqual({ value: 42 });
    expect(result.current.isStale).toBe(false);

    apiGetSpy.mockRejectedValueOnce(new Error("network down"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });

    expect(result.current.data).toEqual({ value: 42 }); // unchanged, not cleared
    expect(result.current.error).toBe("Error: network down");
    expect(result.current.isStale).toBe(true);
    unmount();
  });
});
