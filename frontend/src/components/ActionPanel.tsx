import { useLiveData } from "../hooks/useLiveData";
import type { ActionPlan, ActionItem, BuildingActionItem } from "../types/api";

function ActionList({
  title,
  items,
  totalCount,
}: {
  title: string;
  items: (ActionItem | BuildingActionItem)[];
  totalCount: number;
}) {
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
              {item.name}
              {"category" in item && (
                <span style={{ color: "var(--text-secondary)", fontSize: "0.8rem" }}> [{item.category}]</span>
              )}
              {" — "}<strong>{item.max_depth_m.toFixed(2)} m</strong>
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

interface ActionPanelProps {
  refreshSignal?: number;
}

export function ActionPanel({ refreshSignal }: ActionPanelProps) {
  const { data: plan, error } = useLiveData<ActionPlan>(
    "/api/v1/action-plan",
    60_000,
    refreshSignal,
  );

  if (error) return <p>Could not load action plan: {error}</p>;
  if (!plan) return <p>Loading action plan…</p>;

  const schoolCount = plan.schools_in_flood_zone.length;

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>Action Plan — {plan.reference_scenario}</h3>

      {/* Schools called out first, above the depth-sorted lists below —
          a school with any water at all outranks a deeper-flooded shed
          for evacuation urgency (children present). */}
      <div
        style={{
          background: schoolCount > 0 ? "var(--accent-purple)" : "var(--bg-primary)",
          color: schoolCount > 0 ? "white" : "var(--text-secondary)",
          borderRadius: 6,
          padding: "10px 14px",
          marginBottom: 16,
          fontWeight: schoolCount > 0 ? 700 : 400,
        }}
      >
        {schoolCount > 0
          ? `${schoolCount} school${schoolCount === 1 ? "" : "s"} in the flood zone — evacuate first: ${plan.schools_in_flood_zone.map((s) => s.name).join(", ")}`
          : "No schools in the flood zone at this reference scenario."}
      </div>

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
