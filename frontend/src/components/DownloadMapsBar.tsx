import { useState } from "react";
import { apiRasterUrl } from "../api/client";

// The real deliverable: a labeled, readable flood map per storm size —
// real streets (named), real building footprints, named critical facilities
// with exact depth in feet, a legend, scale bar, north arrow. Not the raw
// depth grid alone (no context, no names, unusable to anyone but a GIS
// analyst) — this is what a manager can actually open and understand.
// The raw GeoTIFF is still offered underneath for whoever needs it in
// QGIS/ArcGIS, clearly labeled as the technical/secondary option.

const RETURN_PERIODS = [5, 10, 25, 50, 100, 200];

function referenceMapUrl(rp: number): string {
  return apiRasterUrl(`/outputs/reference_maps/flood_reference_map_${rp}yr.png`);
}

export function DownloadMapsBar() {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <div style={{ background: "var(--bg-card)", padding: 16, borderRadius: 8, marginTop: 20 }}>
      <h3 style={{ marginTop: 0 }}>Flood reference maps — by storm size</h3>
      <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", margin: "0 0 12px" }}>
        A real, labeled map for each storm size: named streets, real building footprints, and every
        critical facility called out with its exact flood depth in feet. In this method the affected
        area is similar at every size — <strong>darker red means deeper water</strong>, which is what
        actually changes as the storm gets bigger. Click a map to view it full-size.
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
        {RETURN_PERIODS.map((rp) => (
          <div key={rp} style={{ background: "var(--bg-primary)", borderRadius: 8, overflow: "hidden", border: "1px solid var(--border)" }}>
            <a href={referenceMapUrl(rp)} target="_blank" rel="noreferrer" title={`Open the full-size ${rp}-year reference map`}>
              <img
                src={referenceMapUrl(rp)}
                alt={`${rp}-year flood reference map: streets, buildings, and critical facilities with flood depth`}
                style={{ width: "100%", height: 150, objectFit: "cover", objectPosition: "center 60%", display: "block", background: "#fbfaf6" }}
                loading="lazy"
              />
            </a>
            <div style={{ padding: "8px 10px" }}>
              <div style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: 6 }}>{rp}-year event</div>
              <div style={{ display: "flex", gap: 6 }}>
                <a href={referenceMapUrl(rp)} target="_blank" rel="noreferrer"
                   style={{ flex: 1, textAlign: "center", padding: "5px 8px", borderRadius: 5, fontSize: "0.76rem", fontWeight: 600, textDecoration: "none", background: "var(--accent-blue)", color: "black" }}>
                  View map
                </a>
                <a href={referenceMapUrl(rp)} download
                   style={{ flex: 1, textAlign: "center", padding: "5px 8px", borderRadius: 5, fontSize: "0.76rem", fontWeight: 600, textDecoration: "none", border: "1px solid var(--border)", color: "var(--text-primary)" }}>
                  ⬇ Save
                </a>
              </div>
            </div>
          </div>
        ))}
      </div>

      <button
        onClick={() => setOpen(open === null ? -1 : null)}
        style={{
          marginTop: 14, background: "none", border: "1px solid var(--border)", color: "var(--text-secondary)",
          fontSize: "0.78rem", padding: "5px 12px", borderRadius: 6, cursor: "pointer",
        }}
      >
        {open === null ? "▼ Raw GIS data (for GIS analysts / QGIS / ArcGIS)" : "▲ Hide raw GIS data"}
      </button>
      {open !== null && (
        <div style={{ marginTop: 10 }}>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.8rem", margin: "0 0 8px" }}>
            The underlying georeferenced depth grid behind each map above (FEMA base-flood elevations +
            USGS 3DEP terrain, EPSG:32612) as a raw GeoTIFF — no streets, buildings, or labels, just the
            depth data itself for GIS software.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {RETURN_PERIODS.map((rp) => (
              <a
                key={rp}
                href={apiRasterUrl(`/api/v1/download/flood-map/${rp}`)}
                download
                style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  padding: "6px 12px", borderRadius: 6, textDecoration: "none",
                  background: "var(--bg-primary)", border: "1px solid var(--border)",
                  color: "var(--text-secondary)", fontWeight: 600, fontSize: "0.78rem",
                }}
              >
                ⬇ {rp}yr GeoTIFF
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
