import { useState, useRef, useEffect } from "react";
import { apiPost } from "../api/client";

/**
 * Floating "Ask about this dashboard" assistant. A visitor who doesn't
 * understand a panel opens this and asks in plain words; a Claude model
 * behind the backend (/api/v1/chat — key stays server-side) explains it,
 * grounded in what AFFI is and aware of today's live alert. It never makes
 * a personal evacuate/stay decision (enforced server-side).
 */

interface Msg { role: "user" | "assistant"; content: string }

const SUGGESTIONS = [
  "What does the current alert level mean?",
  "What is a return period?",
  "Why does the map show flooding when it's dry?",
  "How accurate is this forecast?",
];

const GREETING: Msg = {
  role: "assistant",
  content:
    "Hi — I can explain anything on this flood dashboard in plain language: what a panel means, why a color is what it is, or how the forecast works. Ask me anything. (For a real emergency, always follow the National Weather Service, your county EOC, and 911.)",
};

export function ChatAssistant() {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<Msg[]>([GREETING]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [msgs, busy]);

  async function send(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    setError(null);
    const next = [...msgs, { role: "user" as const, content: q }];
    setMsgs(next);
    setInput("");
    setBusy(true);
    try {
      // Send only the real turns (skip the canned greeting).
      const history = next.filter((m) => m !== GREETING).map((m) => ({ role: m.role, content: m.content }));
      const res = await apiPost<{ reply: string }>("/api/v1/chat", { messages: history });
      setMsgs((m) => [...m, { role: "assistant", content: res.reply }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {/* Launcher */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          aria-label="Open the dashboard assistant"
          style={{
            position: "fixed", right: 22, bottom: 22, zIndex: 1000,
            display: "flex", alignItems: "center", gap: 9, padding: "12px 18px",
            borderRadius: 999, border: "none", cursor: "pointer",
            background: "var(--accent)", color: "#fff", fontWeight: 700, fontSize: "0.9rem",
            boxShadow: "var(--shadow-pop)",
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M4 5h16v11H8l-4 4V5z" stroke="#fff" strokeWidth="1.8" strokeLinejoin="round" fill="none"/>
            <circle cx="9" cy="10.5" r="1.1" fill="#fff"/><circle cx="12" cy="10.5" r="1.1" fill="#fff"/><circle cx="15" cy="10.5" r="1.1" fill="#fff"/>
          </svg>
          Ask about this dashboard
        </button>
      )}

      {/* Panel */}
      {open && (
        <div
          className="rise-in"
          style={{
            position: "fixed", right: 22, bottom: 22, zIndex: 1000,
            width: "min(390px, calc(100vw - 32px))", height: "min(560px, calc(100vh - 48px))",
            display: "flex", flexDirection: "column",
            background: "var(--bg-card)", border: "1px solid var(--border-strong)",
            borderRadius: 14, boxShadow: "var(--shadow-pop)", overflow: "hidden",
          }}
        >
          {/* Header */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "12px 14px", background: "var(--accent)", color: "#fff",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="live-dot" style={{ background: "#fff" }} />
              <strong style={{ fontSize: "0.92rem" }}>Dashboard assistant</strong>
            </div>
            <button onClick={() => setOpen(false)} aria-label="Close assistant"
              style={{ background: "transparent", border: "none", color: "#fff", cursor: "pointer", fontSize: "1.2rem", lineHeight: 1, padding: 4 }}>
              ×
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} style={{ flex: 1, overflowY: "auto", padding: "12px 12px 4px", display: "flex", flexDirection: "column", gap: 10 }}>
            {msgs.map((m, i) => (
              <div key={i} style={{
                alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                maxWidth: "88%", padding: "9px 12px", borderRadius: 12,
                fontSize: "0.84rem", lineHeight: 1.45, whiteSpace: "pre-wrap",
                background: m.role === "user" ? "var(--accent)" : "var(--bg-secondary)",
                color: m.role === "user" ? "#fff" : "var(--text-primary)",
                borderBottomRightRadius: m.role === "user" ? 3 : 12,
                borderBottomLeftRadius: m.role === "user" ? 12 : 3,
              }}>
                {m.content}
              </div>
            ))}
            {busy && (
              <div style={{ alignSelf: "flex-start", padding: "9px 12px", color: "var(--text-secondary)", fontSize: "0.82rem" }}>
                thinking…
              </div>
            )}
            {error && (
              <div style={{ alignSelf: "stretch", padding: "8px 10px", borderRadius: 8, fontSize: "0.78rem", background: "var(--status-warning-bg)", color: "var(--status-warning-ink)", border: "1px solid var(--status-warning)" }}>
                {error}
              </div>
            )}
            {/* Starter suggestions, only before the first question */}
            {msgs.length === 1 && !busy && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 2 }}>
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)}
                    style={{ fontSize: "0.74rem", padding: "6px 10px", borderRadius: 999, cursor: "pointer",
                      border: "1px solid var(--accent)", background: "transparent", color: "var(--accent)" }}>
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Input */}
          <form
            onSubmit={(e) => { e.preventDefault(); send(input); }}
            style={{ display: "flex", gap: 8, padding: 10, borderTop: "1px solid var(--border)" }}
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about any panel…"
              aria-label="Ask the assistant"
              style={{
                flex: 1, padding: "9px 12px", borderRadius: 9, fontSize: "0.85rem",
                border: "1px solid var(--border-strong)", background: "var(--bg-elevated)", color: "var(--text-primary)",
              }}
            />
            <button type="submit" disabled={busy || !input.trim()}
              style={{
                padding: "9px 15px", borderRadius: 9, border: "none", cursor: busy || !input.trim() ? "default" : "pointer",
                background: busy || !input.trim() ? "var(--border-strong)" : "var(--accent)", color: "#fff", fontWeight: 700, fontSize: "0.85rem",
              }}>
              Send
            </button>
          </form>
          <div style={{ fontSize: "0.66rem", color: "var(--text-faint)", padding: "0 12px 10px", textAlign: "center" }}>
            AI assistant · can be wrong · not a substitute for NWS / EOC / 911
          </div>
        </div>
      )}
    </>
  );
}
