# FloodAI — Current Status

**Last verified:** 2026-08-10

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

Full deliverable-by-deliverable trace: `docs/AFFI_whitepaper_2026-08-10.md` Section 5 (per-task Status lines) — the old `outputs/whitepaper_deliverables_status.md` used a superseded May-11 deliverable numbering scheme that no longer matches the current D-numbering and was deleted 2026-08-10.

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
The static `dashboard.html` generator stays as an offline fallback
(no server required) — not being retired.

**2026-06-30, backend phase done:** `src/api/server.py` now serves map
layers (`/api/v1/map/*`) and simulation scenarios (`/api/v1/simulation/*`)
— data the static dashboard/Folium map previously only read from disk
directly. Run it with `make serve-api` (docs at `/docs`). CORS now reads
`AFFI_CORS_ORIGINS` instead of a wildcard.

**2026-06-30, frontend (React) built:** `frontend/` — Vite + React + TS,
MapLibre GL JS map (real 3D building extrusion), simulation slider, Action
Panel (`/api/v1/action-plan` — named roads/buildings to barricade/evacuate,
cites ARS 28-910), NWS-style bulletin generator (`/api/v1/bulletin`). Run
with `npm run dev` in `frontend/` alongside `make serve-api`.

**Known gap surfaced while building the bulletin:** the alert packet's
`watershed.huc` field (from `config/settings.py`, used by Task 1/2) holds
the HUC-8 code (`15050301`, 510 km²), not the HUC-12 pilot watershed code
(`150503010204`, 143.6 km²) that Task 3-5's real flood library actually
uses. This is the same divergence noted in the archived
`HONEST_ASSESSMENT_AND_REAL_DATA_PLAN.md` (2026-06-22) — still present,
not yet reconciled. `src/api/routes_bulletin.py` now prints whatever value
is actually there rather than mislabeling it "HUC-12."

**2026-06-30, dashboard content built out:** Decision Cockpit
(time-to-peak/life-safety/uncertainty — whitepaper D4.2.c/d/f, computed
but never surfaced before), historical event comparison
(`data/historical_events/sonoita_events.json`, existed unused since
early in the project), auto-refresh (60s polling + manual "Refresh
now" — `frontend/src/hooks/useLiveData.ts`), and building categories
(School/Public-Civic/Residential/Commercial-Industrial/Agricultural-
Outbuilding — `src/common/building_categories.py`, a pure lookup over
the OSM `building` tag already on disk, no new data acquisition).

**2026-06-30, Docker wiring:** `frontend/Dockerfile` (multi-stage,
nginx serves the build + reverse-proxies `/api` and `/health` to the
`api` container — same-origin, no CORS needed in this path).
`docker-compose.yml` `dashboard` (Streamlit) service commented out —
superseded by `frontend/`, not deleted. `AFFI_AUTH_DISABLED=true` in
compose is intentional, not an oversight: `frontend/` has no login UI
yet, so there's nowhere to enter a per-operator API key — flip once
that exists. **Not verified end-to-end** — no `docker` CLI available
in this environment; verified the build output itself (`npm run
build` + served + confirmed real data renders) but not the actual
`docker compose up` cycle. Run `make docker-up` yourself to confirm
before relying on it.

Real bug found and fixed while building this: `npm run build` (the
actual production build, via `tsc -b`) failed on a missing `GeoJSON`
type that `npx tsc --noEmit` (what had been used for typechecking all
session) never caught — the bare command was silently checking nothing
(root `tsconfig.json` has `"files": []`, only real target is `tsc -b`
against the project references). Fixed the missing type
(`tsconfig.app.json` "types" array) and added `npm run typecheck`
(`tsc -b --force`), now wired into `make test`, so this can't
silently pass again.

## Tests

`tests/` — pytest. Re-ran 2026-08-10: **196/196 passed** (up from 149 on
2026-06-30 — new coverage added for Task 4/6 map features and the two
critical bugs fixed 2026-08-10, see `docs/AFFI_whitepaper_2026-08-10.md`
Changelog).
`frontend/` — Vitest: 17/17 passed. `tsc --noEmit`: clean.
`make test` runs pytest + frontend typecheck + frontend unit tests together.

## Critical fixes (2026-08-10)

Two severe bugs were found and fixed in the live pipeline this session —
see the whitepaper Changelog for full detail:

1. **Rainfall unit mismatch** (`map_calculator.py`, `alert_engine.py`) —
   Open-Meteo's mm precipitation was never converted to inches before
   comparing against inch-based alert thresholds, causing a permanent
   false WARNING / "Severe flooding" state for about a week regardless
   of actual weather.
2. **OOM crash in population-at-risk** (`population_exposure.py`) — the
   entire CONUS-scale WorldPop raster (6.8GB peak RSS) was loaded to
   serve one small watershed grid, SIGKILLing the Task 4 refresh on
   nearly every scheduled cycle and silently freezing "live" data on a
   stale snapshot for six days.

Both are fixed, tested, and committed (`7f56691`).

## How to reproduce data/outputs

See `README.md` sections 2 and 5–7.
