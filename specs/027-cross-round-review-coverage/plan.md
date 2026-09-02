# Implementation Plan: Cross-Round Review Coverage

**Branch**: `027-cross-round-review-coverage` | **Date**: 2026-09-02 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/027-cross-round-review-coverage/spec.md`

## Summary

Make multi-round review **accumulate** coverage instead of narrowing it.

Three slices, in priority order:

1. **`handoff record-scope` stops hiding the baseline.** It keeps leading with the
   round's priority set and additionally emits the full `baseline..HEAD` product
   set (the part outside the priority set labelled *not yet re-verified this
   round*) plus the never-reached set. The review directive stops telling a
   corrective round that already-reviewed code is out of scope. This is the slice
   that addresses the reported failures: a defect the anchor round was shown and
   missed is invisible to every later round only because the tool stops printing
   the file.
2. **Coverage becomes per-path.** `reviewscope.assess` replaces its coarse
   anchor/frontier verdict with `never_reached = product_paths(baseline..HEAD) −
   ⋃ product_paths(from..to)` over recorded ranges whose endpoints still resolve.
   On an intact chain this is empty by transitivity of tree comparison, so it
   introduces no false block; where it differs from today is the middle of the
   chain, which today is credited without being checked.
3. **Approval fails closed on it, by name.** `_gate_review_coverage` gains a
   per-path branch ahead of Feature 025's three chain checks, stating the count and
   naming up to 10 paths. *(Corrected during implementation: the plan originally had
   the three branches collapsing into one. They do not — a path re-touched after the
   last round stays a member of the reached set, so the set difference is blind to
   it. 027 adds a branch and removes none; the 025 messages are unchanged.)* The
   degradation rule for ledgers with no scope records is untouched.

Nothing is persisted; the ledger stays at v9. The only new dependency is on
records Feature 025 already writes.

## Technical Context

**Language/Version**: Python 3.10+ (`requires-python`, `target-version = py310`)

**Primary Dependencies**: Typer, PyYAML, `packaging`; `git` on PATH behind the
owned `gitops` seam. **No new dependency.**

**Storage**: `status.yaml` ledger, `schema_version: 9` — unchanged, no migration (R8)

**Testing**: pytest under `conda run -n specops`; ruff + mypy in the same env

**Target Platform**: any Spec Kit repository with git (macOS/Linux/Windows CI)

**Project Type**: single Python CLI package (`src/specops/`)

**Performance Goals**: coverage derivation adds ≤ `1 + N` `git diff --name-only`
calls where N is the recorded-round count, bounded by `review_round_cap`
(default 10). Constant-factor change on a path that already shells out.

**Constraints**: no new adopter-facing command (FR-001a); JSON additions must be
additive under the Feature 021 freeze; `preflight` stays byte-for-byte read-only;
this repository is never self-applied.

**Scale/Scope**: ~4 source files (`reviewscope.py`, `status.py`, `handoff.py`,
`templates/review.md`), 1 constitution amendment, 2 READMEs, CHANGELOG.

## Constitution Check

*Evaluated against constitution v1.12.0. Re-checked after Phase 1 — verdict unchanged.*

| Principle | Verdict | Notes |
|---|---|---|
| I — Speckit Extension, Never Replacement | **PASS** | No Spec Kit file touched. The directive change lands in `src/specops/templates/review.md`, a SpecOps-owned asset delivered through the registered extension surface. |
| II — Physical State Ledger | **VIOLATION — justified** | The Feature 025 carve-out states the coverage guard *"never blocks on a benign history rewrite."* Under FR-004 an unresolvable `reviewed_range` stops counting as coverage, so a squash/amend that orphans a review HEAD **does** block until one `record-scope` re-anchors. See Complexity Tracking. `reconcile` still exempts these endpoints — that half is unchanged. All ledger mutation stays behind CLI commands; nothing new is hand-editable. |
| III — Automated Evidence Collection | **PASS** | No change to evidence collection or `complete-task`. Coverage is derived from git, never narrated. |
| IV — Surgical Agent Behavior | **PASS, with amendments** | Two directive changes in two commits, so two amendments: the **emission** clause broadens with `templates/review.md` in US1 (`1.13.0`), the **coverage** clause with the gate rewrite in US3 (folded into `1.14.0`). Governance requires each directive change and its template edit in the *same* change set, which is why neither is deferred to the end. |
| V — Domain Agnosticism | **PASS** | No stack, framework, or client rule enters. No new config key — the message bound of 10 is a fixed presentation constant, not client-tunable behavior. |
| VI — Exit Codes as Gates | **PASS** | Blocking approval stays exit `1`. No new code introduced; the `0`/`1`/`2` set is untouched. |
| Technical Constraints | **PASS** | No new runtime dependency. Modules stay under `src/specops/`, scaffold assets under `src/specops/templates/`. |
| Development Workflow §3 | **PASS** | Every scenario is validated by fixtures under `tests/`; no `specops.json` or `status.yaml` is created in this repository. |

**Gate result**: proceed. One violation, justified below, resolved by a MINOR
constitution amendment landing with the implementation.

## Project Structure

### Documentation (this feature)

```text
specs/027-cross-round-review-coverage/
├── plan.md                      # this file
├── research.md                  # Phase 0 — R1..R8 + constitution deltas
├── data-model.md                # Phase 1 — derived entities, no persistence
├── quickstart.md                # Phase 1 — fixture validation guide
├── contracts/
│   ├── record-scope-output.md   # additive JSON + human output
│   └── coverage-guard.md        # approval guard behavior delta
├── checklists/
│   └── requirements.md          # spec quality checklist (16/16)
└── tasks.md                     # Phase 2 — /speckit-tasks, NOT created here
```

### Source Code (repository root)

```text
src/specops/
├── reviewscope.py               # CHANGED — product_paths widened (R5);
│                                #   Assessment reshaped to never_reached (R3);
│                                #   assess() rewritten as a per-path union (R1/R2)
├── status.py                    # CHANGED — _gate_review_coverage: three branches
│                                #   collapse into one bounded, path-naming block (R6)
├── handoff.py                   # CHANGED — cmd_record_scope emits baseline_paths,
│                                #   not_reverified_paths, never_reached_paths (R4);
│                                #   what it PERSISTS is unchanged (FR-002)
└── templates/
    └── review.md                # CHANGED — Step 3 corrective bullet (R7/FR-012)

tests/
├── unit/
│   ├── test_reviewscope.py      # EXTENDED — union derivation, unresolvable ranges,
│   │                            #   widened specs/ exclusion, no-false-block case
│   ├── test_handoff.py          # EXTENDED — the three emitted sets, anchor variant
│   ├── test_review.py           # EXTENDED — directive wording assertion
│   ├── test_trace.py            # ANCHOR — is_managed unchanged (drift gate untouched)
│   ├── test_frozen_ledger.py    # ANCHOR — schema stays v9, no new migration
│   └── test_config_round_cap.py # ANCHOR — round cap untouched
├── integration/
│   ├── test_review_coverage_guard.py  # EXTENDED — roadmap acceptance gate,
│   │                                  #   bounded message, recovery in one command
│   ├── test_corrective_scope.py       # EXTENDED — US1 end to end
│   ├── test_git_availability.py       # ANCHOR — frozen CLI command/group sets
│   │                                  #   unchanged (FR-001a: no new surface)
│   └── test_round_cap.py              # ANCHOR — round cap untouched
├── unit/test_reconcile_reviewed_range_exempt.py
│                                # ANCHOR — the reconcile half of the Principle II
│                                #   carve-out is NOT narrowed
└── golden/                      # ADDED — record_scope_human / record_scope_json
                                 #   scenarios (none exist today); every other
                                 #   family asserted byte-identical

.specify/memory/constitution.md  # CHANGED — 1.13.0 with US1 (Principle IV emission clause),
                                 #   1.14.0 with US3 (Principle II carve-out + IV coverage clause)
README.md / README.pt-br.md      # CHANGED — together, full parity
CHANGELOG.md                     # CHANGED — [Unreleased]
```

**ANCHOR** files are asserted *unchanged* — regression anchors for SC-007, not
edits. They are declared here because the task list touches them; the plan gate
verifies declared paths against the worktree, so an undeclared path a task names
is a gap in the plan, not in the task.

**Structure Decision**: single Python package, existing module boundaries. The
derivation stays in `reviewscope` (pure logic, no ledger or CLI I/O), the gate in
`status`, the emission in `handoff`, the directive in `templates` — the same
separation Feature 025 established. No new module: this feature changes what is
compared, not how a diff is computed.

## Implementation order

Follows the spec's user-story priorities; each slice is independently testable
and independently shippable.

1. **US1** — `product_paths` widening (R5) + `cmd_record_scope` emission of
   `baseline_paths` / `not_reverified_paths` (R4) + directive rewrite (R7). No
   gate change and no derivation change, so it lands with zero risk of a false
   block, and it is the slice that puts files back in front of the reviewer.
   Shippable on its own if the field needs relief before the gate is ready.
2. **US2** — `Assessment` reshape + per-path `assess` (R1/R2). `record-scope`
   picks up `never_reached_paths` as its third block; still nothing gates on it.
3. **US3** — `_gate_review_coverage` rewrite (R6) + constitution amendment. The
   derivation is already covered by fixtures before it becomes binding.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| **Principle II carve-out narrowed** — an unresolvable `reviewed_range` no longer counts as coverage, so a squash/amend that orphans a review HEAD blocks approval until one `record-scope` re-anchors. Requires constitution `1.13.0 → 1.14.0` (MINOR), landing with the gate rewrite in US3; the replacement text is drafted in research.md. | Silently crediting a range the tool can no longer verify **is** the silent-credit hole User Story 2 exists to close. The 025 wording was written when the guard only checked the anchor and the frontier; extending it to the middle of the chain necessarily makes an unverifiable middle range visible. | *Report but don't block* contradicts US3 acceptance scenario 2, accepted in the clarification session, and leaves the advisory-only state we are leaving. *Recover the orphaned range from reflog/`ORIG_HEAD`* makes coverage depend on local machine state, breaking SC-006 (reproducible from ledger + repo) in a fresh clone or CI checkout. **The narrowing is bounded and the bound is proved, not asserted** (research R2): orphaning is always a chain suffix, so `derive_range` always falls back to a full re-anchor — there is no orphaned-middle deadlock; the round is still open when the guard fires, because the guard raises before `finalize`; and `record-scope` runs every round anyway, so the block can only fire on a rewrite between the last `record-scope` and the approval attempt. A rewrite costs a re-scope, never a re-review. |

**Not violations, recorded for the reviewer:**

- ~~`Assessment` loses four fields.~~ **Did not happen.** All four are retained
  alongside `never_reached`; see the corrected table in research R1. Nothing was
  removed, so the Feature 021 freeze question never arose.
- The blocked-approval message is bounded at 10 paths. **Consistent with local
  precedent**, not a departure: `status.py:634` already renders a path list as
  count-plus-`files[:5]`, and every unbounded `join` in a message today is an
  identifier list that is small by construction — see research R6.
- `product_paths` excludes every `specs/*/` path, not only the active feature's.
  Scoped to coverage; `trace.is_managed` and the drift gate are untouched — see
  research R5.
