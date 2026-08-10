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
4. Update `STATUS.md`'s `**Last verified:**` date to today.
5. If any file this session deleted or renamed is still linked from
   `STATUS.md` or `README.md` (check with
   `grep -rn "outputs/\|docs/AFFI_whitepaper" README.md STATUS.md`), fix or
   remove that reference in the same pass — a dangling link found later reads
   worse than an outdated number does.
6. Re-run `python3 -m pytest tests/ -q` once more after edits (these are docs
   changes, so it should still be the same count) as a final sanity check.
