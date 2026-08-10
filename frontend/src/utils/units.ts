// The backend/hydraulic model works in SI (meters, m³/s, km²) — that's the
// correct unit system for the physics (HEC-RAS, FEMA rasters, USGS gauge
// data are all metric under the hood). But this is a US county EOC
// dashboard: USGS publishes discharge in cfs, NWS publishes stage/depth in
// feet, and local flood-extent reporting in the US uses acres, not km².
// Convert at the display layer only — never touch the underlying SimState/
// API values, which stay SI so they match the model and the raster math.

export function cmsToCfs(cms: number): number {
  return cms * 35.314667;
}

export function metersToFeet(m: number): number {
  return m * 3.28084;
}

export function km2ToAcres(km2: number): number {
  return km2 * 247.10538;
}

export function km2ToSqMi(km2: number): number {
  return km2 * 0.386102;
}

// Acre-feet is the standard US unit for flood/reservoir storage volume
// (1 acre-ft = volume covering 1 acre to 1 ft depth).
export function m3ToAcreFt(m3: number): number {
  return m3 * 0.000810714;
}

export function fmtCfs(cms: number, digits = 0): string {
  return `${cmsToCfs(cms).toLocaleString(undefined, { maximumFractionDigits: digits })} cfs`;
}

export function fmtFeet(m: number, digits = 1): string {
  return `${metersToFeet(m).toFixed(digits)} ft`;
}

export function fmtAcres(km2: number, digits = 0): string {
  return `${km2ToAcres(km2).toLocaleString(undefined, { maximumFractionDigits: digits })} ac`;
}

export function fmtAcreFt(m3: number, digits = 1): string {
  return `${m3ToAcreFt(m3).toLocaleString(undefined, { maximumFractionDigits: digits })} ac-ft`;
}
