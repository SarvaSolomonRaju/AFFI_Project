import { useCallback, useEffect, useState } from "react";
import { apiGet } from "../api/client";

// Every LIVE-section component (AlertBanner, DecisionCockpit,
// ActionPanel, BulletinPanel, HistoricalComparison, ForecastTable) was
// repeating the same fetch-on-mount pattern with no way to refresh —
// a 24-hour EOC monitoring tool can't require a manual page reload to
// see new data. This hook is that pattern, once, plus polling.
export function useLiveData<T>(path: string, intervalMs = 60_000, refreshSignal = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(() => {
    apiGet<T>(path)
      .then((result) => {
        setData(result);
        setError(null);
        setLastUpdated(new Date());
      })
      .catch((err) => setError(String(err)));
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
  return { data, error, lastUpdated, refresh: load };
}
