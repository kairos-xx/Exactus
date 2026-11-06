# Handoff — lints crash, memory runaway, MergeKit, dev/stress, PLAN.md

Last updated 2026-11-05 ~02:10 WET. Nothing was committed or pushed. No publication,
tagging or privileged install was performed.

## 1. `exactus --lints` on another project: "no result" (FIXED)
- Not a memory leak in lints (peak ~760 MB, ~40 s). Cause: a pre-existing syntax error in
  `kairos-toolbox/tools/hartley/core.py` (untracked; blocks flattened onto one line, e.g. line 631).
  Ruff exits 2 for the whole batch -> the exception escaped -> "tool exited without writing a report".
- Lints did NOT write that file (`SourceJournal._resolve` compiles every `.py` proposal first).
  The writer is unknown (mtime 00:54). kairos-toolbox source was never modified by me;
  its previous LINTS results are backed up in the session scratchpad (`bak/LINTS`).
- Fix: `exactus/packages/all_lints/core.py` — `RuffStabilizer._compiles`, `_unparsable`
  (added to `_format_locked`), `_ordinary_unformatted` skips them, `_verify_policy` probes a
  parsable file, single-file path no longer formats an unparsable file. They are still reported
  as findings by `ruff check`.
- Tests: `test_stabilizer_survives_unparsable_file_in_batch`, `..._single_unparsable_file`.

## 2. Memory/process runaway (~01:23-01:39) — CONTAINED, TRIGGER NOT FOUND
- A chain of `python exactus/__main__.py --version` processes, each the child of the previous,
  ~1/s, 4500+ procs, 66 GB swap, load 340. Env had `EXACTUS_PROJECT_PYTHON=<kairos-toolbox venv>`
  + `EXACTUS_ORCHESTRATED=1`. Killed manually (all were `--version` probes; no work lost).
- Containment: `exactus/tools/common/nesting_guard.py` (`EXACTUS_NEST_DEPTH`, `EXACTUS_NEST_OWNER`,
  limit 32, counts process generations not calls), called first in `exactus/__main__.py::main`.
  On trip it prints parent pid + argv. Tests: `tests/tools/common/test_nesting_guard.py` (7).
- NOT identified: the launcher that re-execs itself. Ruled out in bounded tests: plain
  `--version`, `--external --version`, `self_test`, `tests/standalone` (strips `EXACTUS_*`).
  Next step: if the guard ever trips, read its message. `/usr/local/bin/exactus` is a frozen
  296 MB zipapp (Nov 4) WITHOUT the guard; reinstalling needs privileges -> not done.
- Safe repro tool (scratchpad): `guard.py` = process-group watchdog that kills at >8 procs.

## 3. MergeKit (`source_merger_incremental.zip`) — IMPLEMENTED
- Package `exactus/packages/source_merger/` (+ tests `exactus/tests/packages/source_merger/`, 70 pass).
  Added `tokens.py`: whitespace-insensitive token-level 3-way merge fallback (rules: line-start
  insertions are boundary-safe; insertions slide to whole-line boundaries; case-only tool changes
  such as hex colours yield to the user's value; guard distance 3 tokens, relaxed across line breaks).
- Integration (dependency injection, because `tools/common` may not import `packages`):
  `exactus/packages/source_merger/live.py::merge_live_edit(suffix, original, tool, user)` returns
  `LiveMerge(data, exact)`. `SourceJournal(..., merger=...)` (tools/common/source_transaction.py) calls the
  injected `LiveMerger` Protocol (tools/common/source_merge.py) on the `apply_and_preserve` verdict;
  `tools/lints/core.py` injects `merge_live_edit`. Structural merge -> exact, no forks. Token fallback ->
  merged bytes kept, A/B/C forks SAVED, file flagged dirty for review. Any failure/None -> previous
  behaviour. Result must parse (python compile / language parser).
- HANG GUARANTEE: the token diff (difflib) is quadratic on repetitive input (4k tokens took >120 s unbounded).
  `tokens.merge_tokens_bounded` runs it in a child (`python -m exactus.packages.source_merger.tokens`,
  15 s timeout, killed on expiry) -> pathological input costs the deadline then falls back (test: 2 s).
  Real code is fast: 9k-token file 0.75 s, 40k-token file 11 s with heavy transforms.
- Node deps added to root `package.json`/lock: typescript 5.9.3, postcss 8.5.6 (global TS is v7 = no JS API).
- Compliance: my own files are lint-clean; remaining ~230 findings are in the imported MergeKit code
  (parse_node.cjs ~83 eslint/ts, engine.py complexity C901/PLR, long lines, FBT003, TC001...).
  Re-check: `python exactus --lints --dry --include 'exactus/packages/source_merger/**'`.
  CAUTION: always pass explicit file/dir globs; `exactus/tools/common/**` touched an unrelated file (see §7).

## 4. dev/stress — MERGE ACCEPTED
- base=`dev/stress`, user=`dev/stress-edited`, tool=lints-formatted copy. All four files merge;
  merged == formatted + exactly the user lines (py 7, js 5, css 7, html 3 changed lines).
- Output for inspection: `dev/stress-merged-actual/` (NEW dir; no existing fixture was overwritten).
  CAVEAT: another process rewrote `dev/stress-merged-actual/stress.py` at 02:02 (keyword-argument rewrites),
  so that dir is NOT authoritative. Regenerate from the harness (scratchpad `harness.py`, inputs `fx2/`).
- `dev/stress-merged` is STALE vs current lints (py differs from formatted by 14 lines, e.g. string re-wrap);
  `dev/*.zip` derived archives (00:27) predate the new baseline `stress.zip` (01:24). `dev/` was being
  regenerated by another process during the session -> treated read-only.
- Lints itself on dev/stress: completes, second run changes 0 bytes; findings remain (annotations,
  docstrings, CSS tokens need semantic fixes) — that file set is a robustness fixture, not fixable to 0.
- Idempotence is now an automated test: `tests/tools/lints/test_lints.py::test_second_fixing_pass_changes_no_bytes`.

## 5. docs/todo/PLAN.md progress
- §12 DONE: README wording ("clears its output first"); retired `DEBUG.txt` `clean`/`clean::<age>`
  now reported on stderr and never clear (both byte-identical `sprint.py` copies); tests
  `tests/tools/common/test_retired_clean.py` (`--clean` exit 2, `clean = true` unknown option) and
  `test_sprint.py::test_retired_clean_directive_is_reported_and_never_clears`.
- §1 second bullet (second run changes no bytes): automated test added (above).
- §2/§4/§6/§7/§8/§9/§10/§11: NOT done. Reasons: real PyPI/GitHub publish, tags and privileged installs
  need explicit authorisation; native Windows/ARM/musl evidence cannot be produced on this macOS host;
  §4/§2 (full provenance records, all-stage journal) are multi-day designs. Mark these NOT RUN/BLOCKED.

## 6. Verify
```
cd /Users/joaolopes/Exactus
.venv/bin/python -m pytest -q exactus/tests/packages/source_merger exactus/tests/tools/common \
  exactus/tests/packages/all_lints exactus/tests/tools/lints/test_lints.py
```

## 7. Things the user should know / decide
- Orphan process: PID 64434 (my abandoned repetitive-diff benchmark, ~1 core). `kill 64434` if still running
  (my own kill was refused by the permission classifier; harmless otherwise).
- Pre-existing, unrelated test failure: `tests/tools/lints/test_lints.py::test_eslint_fix_preserves_mandatory_syntax`
  (expects `({value: 1})`, pipeline yields Prettier's `({ value: 1 })`; ESLint autofix not taking effect here;
  same symptom visible in the dev/stress scratch run). Not verified on a clean commit.
- `exactus/tools/common/templates/html/report.js` was reformatted by an over-broad autofix scope (parens
  around single arrow params). Unrelated to the task; restore with
  `git checkout -- exactus/tools/common/templates/html/report.js` (I was not permitted to run it).
- `kairos-toolbox/tools/hartley/core.py` is syntactically broken and untracked (no git copy): repair or
  restore it from your editor history/backups.
- Another agent (Devin "cotton-fear") was running the full pipeline in this repo; `dev/` and
  `artifacts/EXACTUS_RESULTS` may be changing under you.

## 8. Update 2026-11-05 ~20:00 — full-suite triage + speed
- Full run (4161 tests, 1048 s): 71 failed / 68 errors. Triage:
  - `tests/tools/record/*` (~120), `visual_cause/test_pipeline.py` (6): PASS when run per file
    (e.g. 33 record tests, 8 visual_cause) -> failures were load/cross-file contention while another
    agent used the machine. Not regressions.
  - `tools/lints/test_lints_report.py` (2): FIXED. Uncommitted work in `tools/lints/core.py` adds a leading
    `format` linter entry; test indices/expected list updated (+1 shift). 16 pass.
  - `tools/frontend/*` (4) + `test_parallel_flows` when run together: NOT FIXED, environmental. Playwright in
    the venv (1.64.1) wants chromium build 1243, but the activated `~/.cache/exactus-tools/<hash>/` cache
    (hash 8db51…) holds 1248 — the bundle in the working tree is mid-rebuild. Each file passes alone.
    Fix = finish/rebuild the bundle or `playwright install` matching builds; no test change.
- Added `tests/conftest.py` browser-env restore (PLAYWRIGHT_BROWSERS_PATH etc.) — harmless isolation, did
  not by itself cure the frontend failures (activation also happens at import in `frontend/core.py:211`).
- Speed: `SourceCache.read(mutable=True)` now re-parses cached source instead of `deepcopy` (measured
  58 ms vs 205 ms on 4 large files). `clear_conflict_copies` scandir rewrite REJECTED: 5/1500 differential
  mismatches (dir vs symlink, same-name file contents) — it moves user files, so left unchanged.
- Verified after last edit: tools/common + source_merger + lints_report + self_test = 728 passed.
