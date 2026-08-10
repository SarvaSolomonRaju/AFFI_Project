// Shown when the most recent poll failed but a previous successful fetch's
// data is still on screen (useLiveData never clears `data` on error) —
// keeps the panel showing real, labeled-stale content instead of replacing
// it with a bare error message, which is what happens during exactly the
// power/network blip a flood is most likely to cause.
export function StaleBadge({ error, lastUpdated }: { error: string; lastUpdated: Date | null }) {
  return (
    <div
      style={{
        background: "rgba(243,156,18,0.12)",
        border: "1px solid #f39c12",
        color: "#f39c12",
        borderRadius: 6,
        padding: "6px 12px",
        marginBottom: 10,
        fontSize: "0.78rem",
        fontWeight: 600,
      }}
    >
      ⚠ Could not refresh ({error}) — showing last known data
      {lastUpdated ? ` from ${lastUpdated.toLocaleTimeString()}` : ""}.
    </div>
  );
}
