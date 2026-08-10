import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";

// Every LIVE-section component (AlertBanner, DecisionCockpit,
// ActionPanel, BulletinPanel, HistoricalComparison, ForecastTable) was
// repeating the same fetch-on-mount pattern with no way to refresh —
// a 24-hour EOC monitoring tool can't require a manual page reload to
// see new data. This hook is that pattern, once, plus polling.

function cacheKey(path: string): string {
  return `affi_cache_${path}`;
}

// Last-known-good persistence, keyed by endpoint path — survives a page
// reload, not just an in-memory fetch failure. A flood knocking out power/
// cell service is exactly when the backend is most likely to drop and
// exactly when a manager can least afford the screen going blank; this
// means even "closed the laptop lid, reopened it, API's still down" still
// shows the last real data instead of a bare loading spinner.
function readCache<T>(path: string): { data: T; lastUpdated: string } | null {
  try {
    const raw = localStorage.getItem(cacheKey(path));
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeCache<T>(path: string, data: T, lastUpdatedIso: string): void {
  try {
    localStorage.setItem(cacheKey(path), JSON.stringify({ data, lastUpdated: lastUpdatedIso }));
  } catch {
    // localStorage full or unavailable (private browsing) — in-memory
    // state below still works for the current session, just doesn't
    // survive a reload. Never worth breaking the dashboard over.
  }
}

export function useLiveData<T>(path: string, intervalMs = 60_000, refreshSignal = 0) {
  const cached = useRef(readCache<T>(path)).current;
  const [data, setData] = useState<T | null>(cached?.data ?? null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(
    cached ? new Date(cached.lastUpdated) : null,
  );
  // True only when the MOST RECENT fetch attempt failed. `data` and
  // `lastUpdated` above are never cleared on error — they keep whatever
  // was last successfully fetched — so a consumer can render that data
  // labeled stale instead of replacing the whole panel with an error
  // message the instant one poll fails.
  const [isStale, setIsStale] = useState(false);

  const load = useCallback(() => {
    apiGet<T>(path)
      .then((result) => {
        setData(result);
        setError(null);
        setIsStale(false);
        const now = new Date();
        setLastUpdated(now);
        writeCache(path, result, now.toISOString());
      })
      .catch((err) => {
        setError(String(err));
        setIsStale(true);
      });
  }, [path]);

  // refreshSignal isn't read inside the effect — it's here purely to
  // force this effect (and thus an immediate load()) to re-run when a
  // parent's "Refresh now" button bumps it, without waiting for the
  // next interval tick.
  useEffect(() => {
    load();
    const id = setInterval(load, intervalMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, intervalMs, refreshSignal]);

  // Exposed so a "Refresh now" button doesn't have to wait for the
  // next interval tick.
  return { data, error, lastUpdated, isStale, refresh: load };
}
