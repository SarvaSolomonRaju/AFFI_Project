---
name: full-check
description: Run this project's full verification sequence (backend tests, frontend typecheck/tests, Docker rebuild, live smoke check) before calling any backend or frontend change done. Use after any edit to src/, scripts/, tests/, or frontend/src/.
---

# Full check

This project's bar for "done" on any backend or frontend change, run in this
order. Don't skip steps because an earlier one passed — a green pytest run
does not mean the Docker image running in the background has the fix, and a
clean `tsc` does not mean `vitest` passes.

## 1. Backend tests

```bash
python3 -m pytest tests/ -q
```

All tests must pass. Note the pass count — this project's README/STATUS.md
badges are kept in sync with it (see `.claude/skills/refresh-status-docs` if
the count changed).

## 2. Frontend typecheck + unit tests

```bash
cd frontend
npx tsc --noEmit
npx vitest run
cd ..
```

`tsc --noEmit` catches type errors; it does NOT catch everything `tsc -b`
(the real production build) catches — see the `npm run build` gap noted in
`STATUS.md`'s history. If you changed anything nontrivial in `frontend/src`,
also run `npm run build` inside `frontend/` to be sure.

## 3. Rebuild and redeploy Docker (only if src/, scripts/, or frontend/src changed)

`config/`, `data/`, `models/`, and `outputs/` are live-mounted volumes in
`docker-compose.yml` — editing those needs no rebuild, just a container
restart (`docker compose restart api scheduler`) if a running process cached
old values in memory. But `src/`, `scripts/`, and `frontend/` are baked into
the image at build time — a code edit there is invisible to the running
stack until you rebuild:

```bash
docker compose up --build -d api scheduler frontend
```

## 4. Live smoke check

Confirm the change actually reached the running system, not just the image:

```bash
curl -s http://localhost:8000/health
curl -s http://localhost:8000/api/v1/alert/current
```

For a change to a scheduled pipeline step (Task 1/4), also manually trigger
it rather than waiting for the next cron cycle, and read its exit code:

```bash
docker compose exec scheduler python scripts/07_task4_probabilistic.py --library real
echo "exit: $?"
```

An `rc=-9` here means the process was SIGKILL'd (usually OOM under the
container's memory ceiling) — treat that as a failure requiring
investigation, not a flaky retry.
