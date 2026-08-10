import { useEffect, useState } from "react";
import { apiRasterUrl } from "../api/client";

interface ApiImageProps {
  /** Path under /outputs/ — e.g. "task4/today_ensemble_hydrograph.png" */
  outputPath: string;
  alt: string;
  style?: React.CSSProperties;
  refreshSignal?: number;
}

const MAX_ATTEMPTS = 4;
const RETRY_DELAY_MS = 2500;

export function ApiImage({ outputPath, alt, style, refreshSignal }: ApiImageProps) {
  // The background scheduler rewrites these PNGs (~every 60s). An <img> that
  // happens to fetch one mid-write gets a decode error — and the old code
  // then latched `failed=true` forever, so a single transient blip left
  // "Image not available" on screen for the rest of the session even though
  // the file was fine a second later. This retries a few times (cache-busted
  // so each attempt actually re-fetches) before giving up, and resets when
  // the parent bumps refreshSignal or the path changes.
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setAttempt(0);
    setFailed(false);
  }, [outputPath, refreshSignal]);

  // Served as static files at /outputs/<path> — no auth header needed
  // (StaticFiles mount in server.py is unauthenticated by design).
  const src = apiRasterUrl(`/outputs/${outputPath}?v=${refreshSignal ?? 0}-${attempt}`);

  if (failed) {
    return (
      <div style={{
        background: "var(--bg-primary)",
        borderRadius: 4,
        padding: 16,
        color: "var(--text-secondary)",
        fontSize: "0.8rem",
        textAlign: "center",
      }}>
        Image not available. Run <code>make forecast</code> to generate outputs,
        then restart the API server (<code>make serve-api</code>).
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      style={style}
      onError={() => {
        if (attempt + 1 < MAX_ATTEMPTS) {
          setTimeout(() => setAttempt((a) => a + 1), RETRY_DELAY_MS);
        } else {
          setFailed(true);
        }
      }}
    />
  );
}
