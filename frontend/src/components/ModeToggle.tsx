interface ModeToggleProps {
  mode: "live" | "sim";
  onChange: (mode: "live" | "sim") => void;
}

export function ModeToggle({ mode, onChange }: ModeToggleProps) {
  const base: React.CSSProperties = {
    padding: "11px 28px",
    border: "none",
    cursor: "pointer",
    fontWeight: 800,
    fontSize: "0.95rem",
    letterSpacing: "0.07em",
    transition: "background 0.15s, color 0.15s",
  };

  return (
    <div style={{ display: "flex", gap: 0, borderRadius: 8, overflow: "hidden", border: "2px solid var(--border)", width: "fit-content" }}>
      <button
        onClick={() => onChange("live")}
        style={{
          ...base,
          background: mode === "live" ? "#1b7340" : "var(--bg-card)",
          color: mode === "live" ? "white" : "var(--text-secondary)",
        }}
      >
        LIVE FORECAST
      </button>
      <button
        onClick={() => onChange("sim")}
        style={{
          ...base,
          borderLeft: "2px solid var(--border)",
          background: mode === "sim" ? "#b35900" : "var(--bg-card)",
          color: mode === "sim" ? "white" : "var(--text-secondary)",
        }}
      >
        SIMULATION
      </button>
    </div>
  );
}
