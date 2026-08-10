import { useEffect, useState } from "react";
import { useLiveData } from "../hooks/useLiveData";
import type { ContactRosterResponse } from "../types/api";
import { StaleBadge } from "./StaleBadge";

const CATEGORY_ICON: Record<string, string> = {
  shelter: "🏠",
  hospital: "🏥",
  fire_station: "🚒",
  police: "🚓",
  water_supply: "💧",
  wastewater: "🚰",
  power: "⚡",
  public_works: "🏗️",
};

const NOTES_STORAGE_KEY = "affi_contact_notes";

function loadNotes(): Record<string, string> {
  try {
    const raw = localStorage.getItem(NOTES_STORAGE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

function saveNotes(notes: Record<string, string>): void {
  try {
    localStorage.setItem(NOTES_STORAGE_KEY, JSON.stringify(notes));
  } catch {
    // localStorage unavailable — the note just won't survive a reload.
  }
}

// Real facility data (data/local_assets/infrastructure.geojson), but real
// phone numbers only where actually documented — most are null rather than
// a fabricated placeholder, since a wrong number during an actual flood
// response is worse than an honest blank. The "your note" field lets a
// manager fill in a real number they've looked up themselves; it's stored
// only in this browser's localStorage (never sent anywhere), so it's a
// personal scratch-pad, not a shared/synced roster.
export function ContactRosterPanel({ refreshSignal }: { refreshSignal?: number }) {
  const { data, error, lastUpdated } = useLiveData<ContactRosterResponse>(
    "/api/v1/contacts",
    300_000, // slow poll — this roster changes rarely, if ever
    refreshSignal,
  );
  const [notes, setNotes] = useState<Record<string, string>>({});

  useEffect(() => {
    setNotes(loadNotes());
  }, []);

  function updateNote(name: string, value: string) {
    const next = { ...notes, [name]: value };
    setNotes(next);
    saveNotes(next);
  }

  if (error && !data) return <p>Could not load contact roster: {error}</p>;
  if (!data) return <p>Loading contact roster…</p>;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      {error && <StaleBadge error={error} lastUpdated={lastUpdated} />}
      <h3 style={{ marginTop: 0 }}>On-Call Contact Roster</h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 14px" }}>
        Real facilities from the infrastructure layer. Phone numbers are shown only where actually
        documented — "Not on file" means exactly that, not a guess. "Your note" is saved in this
        browser only, for jotting down a real number once you've confirmed it.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
        {data.contacts.map((c) => (
          <div key={c.name} style={{ background: "var(--bg-primary)", borderRadius: 6, padding: "10px 12px" }}>
            <div style={{ fontWeight: 700, marginBottom: 2 }}>
              {CATEGORY_ICON[c.category] ?? "📍"} {c.name}
            </div>
            <div style={{ color: "var(--text-secondary)", fontSize: "0.78rem", marginBottom: 4 }}>
              {c.category_label}{c.address ? ` · ${c.address}` : ""}
            </div>
            <div style={{ fontSize: "0.85rem", marginBottom: 6 }}>
              {c.phone ? (
                <>📞 {c.phone}</>
              ) : (
                <span style={{ color: "var(--text-secondary)", fontStyle: "italic" }}>Not on file — verify locally</span>
              )}
            </div>
            <input
              type="text"
              placeholder="Your note (e.g. confirmed number, contact person)"
              value={notes[c.name] ?? ""}
              onChange={(e) => updateNote(c.name, e.target.value)}
              style={{
                width: "100%", boxSizing: "border-box", padding: "5px 8px", borderRadius: 4,
                border: "1px solid var(--border)", background: "var(--bg-card)", color: "var(--text-primary)",
                fontSize: "0.8rem",
              }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
