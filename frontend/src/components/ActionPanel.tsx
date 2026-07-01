import { useEffect, useState } from "react";
import { apiGet } from "../api/client";
import type { ActionPlan } from "../types/api";

function ActionList({ title, items, totalCount }: { title: string; items: { name: string; max_depth_m: number }[]; totalCount: number }) {
  return (
    <div>
      <h4 style={{ marginBottom: 4 }}>{title} ({totalCount} total)</h4>
      {items.length === 0 ? (
        <p style={{ color: "var(--text-secondary)" }}>None at this reference scenario.</p>
      ) : (
        <ol style={{ paddingLeft: 20, margin: 0 }}>
          {items.map((item, i) => (
            // Index in the key, not just name: "Unnamed building" is a
            // real, expected duplicate (~95% of flooded buildings have
            // no OSM name tag), so name alone isn't unique.
            <li key={`${item.name}-${i}`}>
              {item.name} — <strong>{item.max_depth_m.toFixed(2)} m</strong>
            </li>
          ))}
        </ol>
      )}
      {totalCount > items.length && (
        <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: 4 }}>
          + {totalCount - items.length} more, sorted by depth
        </p>
      )}
    </div>
  );
}

export function ActionPanel() {
  const [plan, setPlan] = useState<ActionPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiGet<ActionPlan>("/api/v1/action-plan")
      .then(setPlan)
      .catch((err) => setError(String(err)));
  }, []);

  if (error) return <p>Could not load action plan: {error}</p>;
  if (!plan) return <p>Loading action plan…</p>;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>Action Plan — {plan.reference_scenario}</h3>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
        <ActionList
          title="Roads to barricade"
          items={plan.roads_to_barricade.top}
          totalCount={plan.roads_to_barricade.total_count}
        />
        <ActionList
          title="Buildings to evacuate"
          items={plan.buildings_to_evacuate.top}
          totalCount={plan.buildings_to_evacuate.total_count}
        />
      </div>
      <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
        {plan.legal_note}
      </p>
    </div>
  );
}
