---
name: refresh-status-docs
description: Sync README.md and STATUS.md's test-count badges and "last verified" date against the actual current test suite. Use after full-check reports a different pass count than what README/STATUS.md currently claim.
---

# Refresh status docs

`README.md` and `STATUS.md` hardcode the pytest pass count in several places
(a badge, a table cell, an ASCII diagram, a directory-tree comment, `make
test` comments). These go stale silently — nothing fails CI when they drift,
so they only get caught by manual audit (this is exactly what the 2026-08-10
completeness review found: badges still said "102/102" when the real count
was 190+).

## Steps

1. Get the real current count: `python3 -m pytest tests/ -q` and read the
   final line (`N passed`).
2. Find every occurrence of the old count in `README.md` and `STATUS.md`:
   `grep -n "<old-count>" README.md STATUS.md`
3. Replace all of them with the new count — every occurrence, not just the
   badge. Watch for the shields.io badge URL specifically: it's percent-
   encoded (`tests-190%2F190-brightgreen`, not `tests-190/190-...`), so a
   plain string replace of `190/190` will miss the badge unless you also
   handle `190%2F190`.

   **Do not do a blind global string replace of the bare number** (e.g.
   `s.replace("193", "196")`) — it will also corrupt any unrelated number
   that happens to contain that substring. This has actually happened:
   replacing `"193"` silently turned a gauge-record year range
   `1930–1983` into `1960–1983`, and a DEM pixel dimension `1778×1933`
   into `1778×1963`, elsewhere in the same file. Grep the old count first
   and inspect every match's context before replacing, or replace only
   the specific known phrases (`"193/193"`, `"193 unit tests"`, etc.),
   never the bare digits alone.
4. Update `STATUS.md`'s `**Last verified:**` date to today.
5. If any file this session deleted or renamed is still linked from
   `STATUS.md` or `README.md` (check with
   `grep -rn "outputs/\|docs/AFFI_whitepaper" README.md STATUS.md`), fix or
   remove that reference in the same pass — a dangling link found later reads
   worse than an outdated number does.
6. Re-run `python3 -m pytest tests/ -q` once more after edits (these are docs
   changes, so it should still be the same count) as a final sanity check.
