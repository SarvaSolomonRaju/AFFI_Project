import { useEffect, useRef, useState } from "react";
import { apiGet } from "../api/client";
import type { Bulletin } from "../types/api";

type CopyStatus = "idle" | "copied" | "blocked";

export function BulletinPanel() {
  const [bulletin, setBulletin] = useState<Bulletin | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copyStatus, setCopyStatus] = useState<CopyStatus>("idle");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    apiGet<Bulletin>("/api/v1/bulletin")
      .then(setBulletin)
      .catch((err) => setError(String(err)));
  }, []);

  async function copy() {
    if (!bulletin) return;
    try {
      await navigator.clipboard.writeText(bulletin.text);
      setCopyStatus("copied");
    } catch {
      // Clipboard permission can be blocked (locked-down government
      // browsers, non-HTTPS deployments, headless testing) — this is
      // not a hypothetical, it happened during dev testing of this
      // exact button. Fall back to selecting the text so the user can
      // still copy manually with Ctrl/Cmd+C, instead of failing silently.
      textareaRef.current?.select();
      setCopyStatus("blocked");
    }
    setTimeout(() => setCopyStatus("idle"), 3000);
  }

  if (error) return <p>Could not load bulletin: {error}</p>;
  if (!bulletin) return <p>Loading bulletin…</p>;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h3 style={{ margin: 0 }}>Bulletin — official format, ready to relay</h3>
        <button onClick={copy} style={{ padding: "6px 14px", borderRadius: 6, border: "none", cursor: "pointer", background: "var(--accent-blue)", color: "white" }}>
          {copyStatus === "copied" ? "Copied" : copyStatus === "blocked" ? "Selected — press Ctrl/Cmd+C" : "Copy"}
        </button>
      </div>
      <textarea
        ref={textareaRef}
        readOnly
        value={bulletin.text}
        style={{
          width: "100%",
          height: 220,
          marginTop: 12,
          fontFamily: "monospace",
          fontSize: "0.85rem",
          whiteSpace: "pre-wrap",
          background: "var(--bg-primary)",
          color: "var(--text-primary)",
          border: "1px solid var(--border)",
          borderRadius: 6,
          padding: 10,
          resize: "vertical",
        }}
      />
    </div>
  );
}
