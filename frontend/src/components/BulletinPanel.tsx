import { useRef, useState } from "react";
import { useLiveData } from "../hooks/useLiveData";
import type { Bulletin, SimState } from "../types/api";
import { generateSimBulletin } from "../utils/simulation";
import { StaleBadge } from "./StaleBadge";

type CopyStatus = "idle" | "copied" | "blocked";

interface BulletinPanelProps {
  refreshSignal?: number;
  simState?: SimState | null;
  isSimulationMode?: boolean;
}

function CopyableText({ text }: { text: string }) {
  const [copyStatus, setCopyStatus] = useState<CopyStatus>("idle");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopyStatus("copied");
    } catch {
      textareaRef.current?.select();
      setCopyStatus("blocked");
    }
    setTimeout(() => setCopyStatus("idle"), 3000);
  }

  return (
    <>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
        <button onClick={copy} style={{ padding: "6px 14px", borderRadius: 6, border: "none", cursor: "pointer", background: "var(--accent-blue)", color: "white" }}>
          {copyStatus === "copied" ? "Copied" : copyStatus === "blocked" ? "Selected — Ctrl/Cmd+C" : "Copy"}
        </button>
      </div>
      <textarea
        ref={textareaRef}
        readOnly
        value={text}
        style={{
          width: "100%",
          height: 240,
          fontFamily: "monospace",
          fontSize: "0.85rem",
          whiteSpace: "pre-wrap",
          background: "var(--bg-primary)",
          color: "var(--text-primary)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          padding: 10,
          resize: "vertical",
          boxSizing: "border-box",
        }}
      />
    </>
  );
}

export function BulletinPanel({ refreshSignal, simState, isSimulationMode = false }: BulletinPanelProps) {
  const inSimMode = simState !== undefined;
  const { data: bulletin, error, lastUpdated } = useLiveData<Bulletin>(
    "/api/v1/bulletin",
    60_000,
    inSimMode ? undefined : refreshSignal,
  );

  if (inSimMode) {
    return (
      <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
        <h3 style={{ marginTop: 0 }}>
          {isSimulationMode ? "Simulation Bulletin" : "Reference Scenario Bulletin"}
          <span style={{ marginLeft: 10, fontSize: "0.75rem", fontWeight: 400, color: "var(--accent-orange)" }}>
            {isSimulationMode ? "NOT A REAL FORECAST" : "REAL DATA, HYPOTHETICAL EVENT"}
          </span>
        </h3>
        {simState ? (
          <CopyableText text={generateSimBulletin(simState, isSimulationMode)} />
        ) : (
          <p style={{ color: "var(--text-secondary)" }}>
            Increase rainfall above 1" to generate a simulation bulletin.
          </p>
        )}
      </div>
    );
  }

  if (error && !bulletin) return <p>Could not load bulletin: {error}</p>;
  if (!bulletin) return <p>Loading bulletin…</p>;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>Bulletin — official format, ready to relay</h3>
      <CopyableText text={bulletin.text} />
    </div>
  );
}
