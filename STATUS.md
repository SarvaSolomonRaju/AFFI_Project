# FloodAI — Current Status

**Last verified:** 2026-06-30

This is the single source of truth for project state. Older status docs
(dashboard fix logs, manager briefings) are archived in
`_archive/status_docs_2026-06/` — kept for history, not for current facts.

## What's real vs what changed

Per the white paper's original design, Tasks 3–5 (flood map library,
probabilistic forecast, benchmarking) initially ran on **synthetic** terrain.
That was replaced ("Plan B") with real government data:

| Task | What it does | Data |
|---|---|---|
| 1 | Rainfall forecast ingest | Real — Open-Meteo GFS |
| 2 | Rainfall → discharge (Q) | Real — USGS gauge transfer learning |
| 3 | Flood map library (8 return periods) | Real — FEMA NFHL + FIS + USGS 3DEP DEM |
| 4 | Probabilistic forecast (today's map) | Real — built on Task 3 |
| 5 | Benchmarking vs historical events | Real Q, real depth residuals |
| 6 | Local assets (roads/buildings) | Real — OpenStreetMap |

Verified by checking `data/flood_library_real/*.tif` and
`data/terrain/dem_huc12_*.tif` mtimes (2026-06-29) against the Plan B
plan doc (2026-06-22) — the real-data rebuild actually ran.

Full deliverable-by-deliverable trace: [`outputs/whitepaper_deliverables_status.md`](outputs/whitepaper_deliverables_status.md).

## Known architecture gaps (as of this date)

1. **No real frontend.** `outputs/dashboard.html` is a static file generated
   by `scripts/build_dashboard.py` (~2000 lines of Python building HTML/CSS/JS
   as f-strings). No components, no frontend build step, no UI tests.
2. **Backend built but disconnected.** `src/api/server.py` is a working
   FastAPI app (auth, audit logging) but nothing in `main.py` or the
   `Makefile` starts it — it's not wired into the pipeline.
3. **No version control until today** — git initialized 2026-06-30.

Decision made 2026-06-30: rebuild the delivery layer as a real
frontend (calling the FastAPI backend live) rather than the static-HTML
generator. Core hydrology/ML code (`src/hydrology`, `src/hydraulics`,
`src/probabilistic`, `src/benchmarking`) is not being rewritten — it's sound.

## Tests

`tests/` — pytest, 1137 lines. Re-ran 2026-06-30: **102/102 passed**, 3.29s.

## How to reproduce data/outputs

See `README.md` sections 2 and 5–7.
