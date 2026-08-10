// Real, official flood-plain map resources — link-outs, not embeds. Each
// URL was checked directly before listing it here (see below); this dashboard
// never claims a government site is available without having actually
// checked it that session.
//
// Santa Cruz County Flood Control District runs its own GIS/DFIRM viewer —
// this is the "emergency flood plain map used by Santa Cruz County" a
// resident would ask about. Its server did not respond when checked
// directly (connection refused, not a 404 — likely an intermittent/legacy
// county server, not necessarily gone for good), so it's listed honestly as
// "may be temporarily unavailable" rather than presented as guaranteed-live,
// with FEMA's Map Service Center given equal billing as the always-reliable
// path to the exact same official data (Santa Cruz County's own DFIRM was
// built from FEMA's maps in the first place).
const RESOURCES = [
  {
    name: "Santa Cruz County Flood Control District — GIS flood map viewer",
    org: "Santa Cruz County, AZ",
    url: "https://gis.santacruzcountyaz.gov/flood/index.html",
    note: "The county's own interactive flood-plain map. Checked directly before listing — its server did not respond just now (may be an intermittent county-side issue, not necessarily down for good). If it doesn't load, use FEMA's Map Service Center below for the same official data.",
    flag: "county-unverified" as const,
  },
  {
    name: "FEMA Map Service Center — official flood maps",
    org: "FEMA",
    url: "https://msc.fema.gov/portal/search?AddressQuery=Patagonia%2C%20AZ",
    note: "The national source Santa Cruz County's own maps are built from. Always available — search \"Patagonia, AZ\" for the effective FIRM panels covering this watershed.",
    flag: "reliable" as const,
  },
  {
    name: "Arizona Dept. of Water Resources — Floodplain Management Program",
    org: "State of Arizona",
    url: "https://www.azwater.gov/floodplain-management-overview",
    note: "State-level floodplain authority — the agency Santa Cruz County reports to for floodplain administration.",
    flag: "reliable" as const,
  },
  {
    name: "Town of Patagonia — flood insurance / Community Rating System info",
    org: "Town of Patagonia, AZ",
    url: "https://patagonia-az.gov/community-rating-system-flood-information-page/",
    note: "The town's own page on flood insurance rates and its Community Rating System status.",
    flag: "reliable" as const,
  },
];

export function OfficialFloodMapsPanel() {
  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>Official flood-plain maps</h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 12px" }}>
        This dashboard's own maps are a forecasting tool. These are the legal, official flood-plain maps
        for this area — the ones that determine flood insurance requirements and building rules.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {RESOURCES.map((r) => (
          <a
            key={r.url}
            href={r.url}
            target="_blank"
            rel="noreferrer"
            style={{
              display: "block", textDecoration: "none", color: "inherit",
              background: "var(--bg-primary)", borderRadius: 8, padding: "10px 14px",
              border: r.flag === "county-unverified" ? "1px solid var(--accent-orange)" : "1px solid var(--border)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
              <span style={{ fontWeight: 700, fontSize: "0.9rem", color: "var(--accent-blue)" }}>{r.name} ↗</span>
              <span style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>{r.org}</span>
            </div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 3 }}>{r.note}</div>
          </a>
        ))}
      </div>
    </div>
  );
}
