import { useState, useId } from "react";

/**
 * A small "?" that explains a technical term in plain language on hover, focus,
 * or tap. The whole product is meant to be understandable by a non-hydrologist
 * emergency manager, so every piece of jargon should be one click from a plain
 * explanation instead of assumed knowledge.
 *
 * Common definitions live in DEFINITIONS so the same term reads identically
 * everywhere it appears; pass `text` directly for one-off explanations.
 */
export const DEFINITIONS: Record<string, string> = {
  "return period":
    "How rare a flood is. A \"25-year flood\" has about a 1-in-25 (4%) chance of happening in any given year — it is NOT a countdown; two can happen close together.",
  discharge:
    "How much water is moving down the channel, measured as volume per second (cubic feet per second, cfs). Bigger discharge = bigger, deeper flood.",
  cfs:
    "Cubic feet per second — the standard measure of how much water is flowing. One cfs is about one basketball of water passing by every second.",
  "P90 / worst case":
    "The pessimistic scenario: only about a 1-in-10 chance the real flood is worse than this. Road-closure and evacuation calls default to it, to stay on the safe side.",
  "P50 / likely":
    "The most-likely, best single estimate of today's flood — the middle of the range.",
  "P10 / best case":
    "The optimistic scenario: things turn out this mild only if the storm underperforms.",
  "life-safety threshold":
    "Water 0.5 m (about 1.6 ft) deep — enough to sweep an adult off their feet or float a car. The map shows the chance each spot gets at least this deep.",
  "time to peak":
    "How long until the flood reaches its highest point — i.e. how much time you have to act before it is at its worst.",
  "probability of inundation":
    "The chance (0–100%) that a given spot gets any flood water today, given the forecast's uncertainty. Higher = more confident it floods.",
  NSE:
    "A hydrology accuracy score (1.0 = perfect). It is inherently harsh for flashy desert streams that are dry most of the year, which is why the system leans on flood detection — not exact size — for decisions.",
  "mean areal precipitation":
    "The average rainfall over the whole watershed (not just one gauge) — the physically correct input for predicting how a basin responds.",
  ensemble:
    "The weather model run many times with slightly different starting conditions (31 here). If the runs agree, confidence is high; if they scatter, the forecast is genuinely uncertain.",
};

interface InfoTipProps {
  term?: keyof typeof DEFINITIONS | string;
  text?: string;
  label?: string; // optional visible text before the ? (e.g. the term itself)
}

export function InfoTip({ term, text, label }: InfoTipProps) {
  const [open, setOpen] = useState(false);
  const id = useId();
  const body = text ?? (term ? DEFINITIONS[term] : undefined) ?? "No definition available.";

  return (
    <span style={{ position: "relative", display: "inline-flex", alignItems: "center", gap: 4, verticalAlign: "middle" }}>
      {label}
      <button
        type="button"
        aria-label={`What is ${label ?? term ?? "this"}?`}
        aria-describedby={open ? id : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={(e) => { e.preventDefault(); setOpen((v) => !v); }}
        style={{
          width: 15, height: 15, borderRadius: "50%", padding: 0, lineHeight: 1,
          border: "1px solid var(--accent)", background: open ? "var(--accent)" : "transparent",
          color: open ? "#fff" : "var(--accent)", cursor: "help", fontSize: "0.62rem",
          fontWeight: 800, display: "inline-flex", alignItems: "center", justifyContent: "center",
          flexShrink: 0,
        }}
      >
        ?
      </button>
      {open && (
        <span
          id={id}
          role="tooltip"
          style={{
            position: "absolute", bottom: "calc(100% + 8px)", left: "50%", transform: "translateX(-50%)",
            width: 260, zIndex: 50, background: "var(--bg-elevated)", color: "var(--text-primary)",
            border: "1px solid var(--border-strong)", borderRadius: "var(--radius-sm)",
            boxShadow: "var(--shadow-pop)", padding: "10px 12px", fontSize: "0.78rem",
            fontWeight: 400, lineHeight: 1.45, textAlign: "left", pointerEvents: "none",
          }}
        >
          {label && <strong style={{ display: "block", marginBottom: 3 }}>{label}</strong>}
          {body}
        </span>
      )}
    </span>
  );
}
