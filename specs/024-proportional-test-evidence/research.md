# Phase 0 Research: Test Execution Only at the Review Gate

All Technical Context items were resolvable from the existing codebase; there were no open `NEEDS CLARIFICATION` markers (the three design ambiguities were closed in `/speckit-clarify`, Session 2026-08-01). This document records the load-bearing decisions and the code facts they rest on.

## R1 — Where the redundant executions live today

**Finding**: Three code paths shell out the client's test command in one workflow run.

- `src/specops/status.py::_auto_evidence` (~line 602) calls `shell.run_client_command(test_cmd, root)` on the final task of each user story via `complete-task --auto` → **U** runs.
- `src/specops/review.py::_run_profile_gate` (line 187) runs the `test` profile gate; reached from `review.evaluate` → `profile_gates`. Invoked by the `review-soft` workflow step and again by `terminal-gate` → **2** runs.

**Decision**: Remove the `--auto` test run entirely (US2) and make `terminal-gate` reuse `review-soft`'s result (US1).

## R2 — Cache machinery already exists but is inert

**Finding**: `_run_profile_gate` already builds `producer = f"gate:{name}@{version}"`, computes `evidence.cache_key(...)` / `derive_id(...)`, and calls `_cached_record(existing, eid)` (review.py:177-186). `evidence.append_record(..., supersede=True)` (evidence.py:165-187) already supersedes the prior non-superseded record sharing the same producer. `existing_evidence` (review.py:114-132) reads the ledger's `evidence` list.

**Why inert**: No production path ever *writes* a `gate:<name>@<ver>` record — the only producer persisted is `"auto"` (status/handoff). The `existing_evidence` docstring (review.py:120-122) states this explicitly. So `_cached_record` never matches and the gate always falls through to execution.

**Decision**: Activate it — persist a passing gate-run via `append_record(..., supersede=True)`. Do **not** build a new cache; reuse Feature 012's id/supersede path.

## R3 — Cache-hit branch returns PASS unconditionally (latent bug)

**Finding**: On a cache hit, `_run_profile_gate` returns `GateResult(p.name, "PASS", …, disposition="cached")` **without inspecting the cached record's `exit_code`** (review.py:183-186). If a *failing* gate record were ever persisted, a later identical run would wrongly report PASS.

**Decision**: Persist **only passing** gate runs (`exit_code == 0`), and additionally harden the cache-hit branch to treat a cached record as PASS only when its `exit_code == 0` (defensive; reproduces the failure disposition otherwise). Persisting only passes fully covers the reuse scenario because `terminal-gate` runs only after `review-soft` reaches a non-REJECTED verdict (workflow condition `steps.review-soft.output.data.verdict != 'REJECTED'`, workflow.yml:175) — i.e. after all required gates already passed.

**Rationale**: We only ever skip re-running work we have proven green; failures re-run (and the corrective loop is actively changing the tree anyway, which invalidates the key).

## R4 — Working-tree digest for cache-key invalidation (Clarify Q1)

**Finding**: `evidence.cache_key` keys on `producer`/`command`/`commit_range`/`affected_paths`/`context_map_digest`/`subject` — **not** on uncommitted working-tree content (evidence.py:61-81). The `test` gate runs *before* the `working-tree` cleanliness gate in the suite order (review.py:308-318), so the tree can legitimately be dirty when `test` executes. A key without a tree dimension could serve a stale hit after an uncommitted edit.

**Decision**: Add an optional `worktree_digest` to `cache_key`, included in the key **only when provided** (so existing `auto` records — which pass nothing — keep byte-identical ids and need no migration). Gate records pass a digest from a new `gitops.worktree_digest(repo)`.

**`worktree_digest` definition**: `"sha256:" + sha256( git diff HEAD bytes  +  "\0"  +  "\n".join(sorted(porcelain -uall lines)) )`. The `git diff HEAD` component captures tracked modifications; the porcelain-with-untracked component captures added/untracked files that could affect a run. Deterministic for identical tree state; changes on any committed or uncommitted edit. A clean tree yields a stable digest (empty diff + empty status).

**Alternatives considered**:
- *Only reuse when tree is clean* — rejected: denies reuse in legitimately-dirty-but-identical states and still needs a tree signal to be safe.
- *Rely on commit range only* — rejected: fragile against uncommitted edits between the two gates; the whole point of US1 is a safe reuse, not a hopeful one.

## R5 — Which gates are cacheable (Clarify Q2)

**Finding**: The suite is `reconcile` → `lint` → `test` → `working-tree` → `drift` (review.py). `reconcile`, `working-tree`, and `drift` are computed from the *current* tree/diff (not from running a client command); caching them would risk serving a stale view of "now."

**Decision**: Only the command-executing profile gates (`lint`, `test`) persist and reuse evidence. `reconcile`/`working-tree`/`drift` always recompute. In practice this is automatic: persistence lives inside `_run_profile_gate` (the profile-suite path), and the state-derived gates are separate functions (`_reconcile_gate`, `_working_tree_gate`, `_drift_gate`) that never touch the evidence cache. The plan makes this explicit and asserts it in tests, rather than leaving it implicit.

## R6 — Supersede vs append (Clarify Q3)

**Decision**: Supersede by cache key/producer using the existing `append_record(supersede=True)`: retain the latest run per gate, mark the prior with `superseded_by`, never mutate history. Bounded growth, full audit trail. No new mechanism.

## R7 — Narrowing the read-only contract (FR-004)

**Finding**: `tests/integration/test_gate_readonly_determinism.py::test_review_and_gate_report_read_only` asserts `snapshot_tree(repo) == before` after `review --json`, and byte-identical output across two runs (`r1 == r2`). Activating self-persistence breaks both literally: the first run now appends an evidence record, and the second run legitimately reports the `test`/`lint` gate as `cached` (different disposition than the fresh `required`).

**Decision**:
- Narrow the read-only assertion from whole-tree equality to **append-only-evidence**: everything except the ledger's `evidence` list stays byte-identical; the `evidence` list may only *grow* (and supersede markers may flip on prior records) — task, phase, findings, recovery, and config are unchanged.
- Reframe determinism: identical *input ledger state* yields identical output. The fresh run mutates state, so `fresh != cached` is correct and intended. Test structure: (a) two consecutive runs on a fresh ledger → first is fresh, second is `cached`, both individually reproducible; assert the second is stable across further repeats (`cached == cached`). `gate report`/`gate list`/`gate validate` remain **fully** read-only (they never execute gates).
- Update the `existing_evidence` note (review.py:120-122) and the Feature 004 read-only references so the narrowed contract is documented where the old one was asserted.

## R8 — `--auto` without a test run (US2)

**Finding**: `_auto_evidence` requires `test_command` (raises if unset), runs it, fails the close on non-zero, then builds `TEST_REPORT:…; CODE_DIFF:…`. `_record_completion` (status.py) stores the string and a structured `auto` record with `command=evidence_command`.

**Decision**:
- Drop the `test_command` lookup, the `shell.run_client_command` call, and the non-zero fail path from `_auto_evidence`. Keep commit harvesting (`gitops.commits_in_range`) and the `CODE_DIFF:` summary. The evidence string becomes `CODE_DIFF:<n files across m commits: …>` (a valid single-part grammar — `CODE_DIFF` is in `EVIDENCE_CLASSES`).
- The structured `auto` record's `command` field becomes `"(auto)"` (was the test command). `exit_code` stays `0`. Auto-record ids therefore change *for new closes* (different `command`), which is fine — ids are per-record and not back-referenced; **existing** records are untouched (no migration).
- Keep the existing "no commits since task start → commit first" guard (unchanged behavior).
- `test_command` remains required only by the `test` gate; when unset the gate SKIPs (empty command → benign skip, gateprofiles.py default), so `--auto` on a repo without tests simply records diff evidence.

## R9 — Ledger schema impact

**Decision**: No schema migration. The `worktree_digest` lives only inside gate records' cache-key derivation (it affects the `id`, not a new stored top-level field beyond what evidence records already carry). Evidence records already carry `exit_code`, `superseded_by`, etc. If a stored marker for scope were needed it would be additive — but per the resolved spec, no scope field is required (all recorded test evidence now originates from full-suite gate runs). Schema stays **v7**.

## R10 — Constitution amendment (governance)

**Decision**: Bump 1.10.0 → **1.11.0** (MINOR: broadening two non-removed principles). Update the Sync Impact Report comment, Principle III (drop the "runs `test_command` at close" clause; test verification is the gate's job), and Principle IV (preflight is read-only *except* append-only gate evidence). Because a Principle IV directive's *supporting behavior* changes, verify whether any `src/specops/templates/` directive text asserts "preflight is read-only" or "`--auto` runs the tests"; update those in the same change set (implement directive Ledger Loop wording at minimum).
