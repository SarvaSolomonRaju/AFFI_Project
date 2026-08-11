import { useState } from "react";
import { Marker, Popup } from "react-map-gl/maplibre";
import { useLiveData } from "../hooks/useLiveData";
import type { DecisionCockpit as CockpitData } from "../types/api";
import { fmtCfs } from "../utils/units";

/**
 * A live river-gauge status pin on the map — the signature Google Flood Hub
 * map feature we were missing. Flood Hub drops a colored pin at each gauge
 * showing Normal / Warning / Danger / Extreme; this does the same at the
 * pilot watershed's own gauge, using today's forecast discharge against the
 * flood-library return-period thresholds (the same scale the Decision
 * Cockpit badge uses, so the two never disagree).
 *
 * Rendered as a child of <Map>, so it lives inside FloodMap's map with no
 * other change to that component.
 */

type Status = "NORMAL" | "WARNING" | "DANGER" | "EXTREME" | "UNKNOWN";

const STATUS_STYLE: Record<Status, { color: string; label: string; blurb: string }> = {
  NORMAL:  { color: "var(--status-good)",     label: "Normal",  blurb: "Flow within the channel — no flooding expected." },
  WARNING: { color: "var(--status-advisory)", label: "Warning", blurb: "Above the ~2-year level — minor/nuisance flooding possible." },
  DANGER:  { color: "var(--status-watch)",    label: "Danger",  blurb: "Above the ~5-year level — significant flooding likely." },
  EXTREME: { color: "var(--status-warning)",  label: "Extreme", blurb: "Above the ~25-year level — severe, life-threatening flooding." },
  UNKNOWN: { color: "#8592a0",                label: "No forecast", blurb: "Today's forecast discharge is unavailable." },
};

function classify(qCms: number | null | undefined, thr: Record<string, number> | null | undefined): Status {
  if (qCms == null || !thr || thr["2"] == null) return "UNKNOWN";
  const t2 = thr["2"];
  const t5 = thr["5"] ?? t2;
  const t25 = thr["25"] ?? thr["50"] ?? t5;
  if (qCms >= t25) return "EXTREME";
  if (qCms >= t5) return "DANGER";
  if (qCms >= t2) return "WARNING";
  return "NORMAL";
}

interface Props {
  longitude: number;
  latitude: number;
  gaugeId: string;
  gaugeName: string;
  refreshSignal?: number;
}

export function GaugeStatusMarker({ longitude, latitude, gaugeId, gaugeName, refreshSignal }: Props) {
  const [open, setOpen] = useState(false);
  const { data } = useLiveData<CockpitData>("/api/v1/decision-cockpit", 60_000, refreshSignal);

  const q = data?.discharge_cms?.p50 ?? null;
  const thr = data?.flood_thresholds_cms ?? null;
  const status = classify(q, thr);
  const s = STATUS_STYLE[status];

  return (
    <>
      <Marker longitude={longitude} latitude={latitude} anchor="bottom" onClick={(e) => { e.originalEvent.stopPropagation(); setOpen((v) => !v); }}>
        <div style={{ cursor: "pointer", display: "flex", flexDirection: "column", alignItems: "center" }}>
          {/* status chip */}
          <div style={{
            fontSize: 9.5, fontWeight: 800, letterSpacing: "0.04em", color: "#fff", background: s.color,
            padding: "2px 6px", borderRadius: 4, marginBottom: 2, whiteSpace: "nowrap",
            boxShadow: "0 1px 3px rgba(0,0,0,0.4)", textTransform: "uppercase",
          }}>
            Gauge · {s.label}
          </div>
          {/* teardrop pin */}
          <svg width="26" height="34" viewBox="0 0 26 34" aria-label={`River gauge: ${s.label}`}>
            <path d="M13 33 C13 33 24 18 24 11 A11 11 0 1 0 2 11 C2 18 13 33 13 33 Z"
                  fill={s.color} stroke="#fff" strokeWidth="2" />
            {/* little wave glyph */}
            <path d="M7 11 q1.5 -1.6 3 0 t3 0 t3 0" stroke="#fff" strokeWidth="1.6" fill="none" strokeLinecap="round"/>
            <path d="M7 14.5 q1.5 -1.6 3 0 t3 0 t3 0" stroke="#fff" strokeWidth="1.6" fill="none" strokeLinecap="round" opacity="0.7"/>
          </svg>
        </div>
      </Marker>

      {open && (
        <Popup longitude={longitude} latitude={latitude} anchor="top" onClose={() => setOpen(false)} closeOnClick={false} maxWidth="280px">
          <div style={{ fontFamily: "var(--font-sans)", minWidth: 210 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 4 }}>
              <span style={{ width: 11, height: 11, borderRadius: "50%", background: s.color, flexShrink: 0 }} />
              <strong style={{ fontSize: 13, color: "#14202f" }}>River gauge — {s.label}</strong>
            </div>
            <div style={{ fontSize: 11.5, color: "#333", marginBottom: 6 }}>{s.blurb}</div>
            <div style={{ fontSize: 11.5, color: "#14202f" }}>
              {q != null
                ? <>Today's forecast flow: <strong>{fmtCfs(q)}</strong></>
                : "No live forecast flow available."}
            </div>
            {thr && (
              <div style={{ fontSize: 10.5, color: "#555", marginTop: 5, lineHeight: 1.5 }}>
                Flood begins ≈ {fmtCfs(thr["2"])} (2-yr) ·
                serious ≈ {fmtCfs(thr["5"])} (5-yr) ·
                severe ≈ {fmtCfs(thr["25"] ?? thr["50"])} (25-yr)
              </div>
            )}
            <div style={{ fontSize: 10, color: "#777", marginTop: 6, borderTop: "1px solid #eee", paddingTop: 5 }}>
              {gaugeName} (USGS {gaugeId}). Same Normal / Warning / Danger / Extreme scale Google Flood Hub uses.
            </div>
          </div>
        </Popup>
      )}
    </>
  );
}
