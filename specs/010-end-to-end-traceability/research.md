# Phase 0 Research — End-to-End Traceability

All decisions are grounded in the **current worktree** (not memory): `src/specops/{ledger,status,review,gitops,contextmap,consistency,speckit,outcome,errors}.py`, the directive templates under `src/specops/templates/`, and the existing test/fixture layout. No `NEEDS CLARIFICATION` remain; the nine `/speckit-clarify` answers and the deferred `traceability.md` items are resolved below.

---

## R1 — Effective-diff derivation and baseline resolution

**Decision**: The effective diff is `git diff --name-only --no-renames <baseline>..HEAD`. The **baseline** resolves to the ledger-recorded `baseline` commit (`data["baseline"]`, already set at `status.cmd_init_spec` and read by `status.read_baseline`); when no ledger baseline exists, fall back to the merge-base of the current branch with the default branch. Explicit `--path` arguments bypass Git derivation entirely. A rename is thereby **decomposed** into a removed old path + an added new path (no similarity threshold); mode-only/permission changes with no content delta are still listed.

**Rationale**: `review._working_tree_gate` and `status.cmd_complete_task`/`cmd_transition_phase` already compute the effective diff via `gitops.name_only_diff(repo, baseline, "HEAD")` and already treat `data["baseline"]` as authoritative — R1 reuses that exact anchor so classification matches what review already sees. The current `gitops.name_only_diff` calls `git diff --name-only` **without** `--no-renames`, so Git's default rename detection can collapse a rename to a single path — which would violate the clarified rename-decomposition rule. Therefore a **new** helper `gitops.effective_diff(repo, baseline, end="HEAD")` adds `--no-renames`, leaving `name_only_diff` unchanged for its existing callers.

**Alternatives considered**: (a) Reuse `name_only_diff` as-is — rejected: rename collapsing is non-deterministic across Git versions/config and contradicts the clarification. (b) Similarity-threshold rename tracking (classify the pair as one "moved" unit) — rejected in clarification: non-reproducible and needs a heuristic. (c) Diff the working tree instead of `baseline..HEAD` — rejected: review requires a clean tree (`_working_tree_gate` FAILs on dirty), so the committed range is the authoritative change set.

---

## R2 — Path-class model and precedence

**Decision**: Three classes, computed per effective-diff path in this precedence:
1. **`discovered-and-acknowledged`** — the path has an acknowledgement record in the ledger (checked **first**; discovery precedence, spec FR-003).
2. **`planned`** — the path is declared in `plan.md` (via `speckit.parse_plan_path_action`) **or**, when a map is present, owned by a context the plan declared (`speckit.parse_plan_context_ids` + `contextmap._candidates_for_path` ownership).
3. **`unexplained`** — none of the above.

**Rationale**: The clarification fixed *discovery wins* so execution-time provenance is preserved for review; checking the acknowledgement set first is the literal implementation. `planned` reuses the two existing plan parsers (`parse_plan_path_action` already used by `consistency.py`; `parse_plan_context_ids` added by Feature 009) and Feature 008's ownership engine, so no new declaration surface or ownership logic is invented. FR-007's no-op guard (acknowledging an already-planned, never-discovered path creates nothing) ensures the discovery label is never fabricated, so precedence only ever preserves a *real* discovery.

**Alternatives considered**: (a) `planned` wins — rejected in clarification (masks discoveries, costs review control). (b) Overlap as a conflict defect — rejected: needless friction for a benign, auditable state.

---

## R3 — Acknowledgement record + Ledger v3 → v4

**Decision**: Add a top-level ledger list `acknowledgements: [{path, task, reason, map_digest, at}]`. Bump `ledger.CURRENT_SCHEMA` **3 → 4**; `migrate_to_current` backfills `acknowledgements: []` (mirroring `backfill_context_provenance`); `validate_invariants` checks each record is a mapping with non-empty `path`/`task`/`reason` and that `task` matches a known (non-orphaned) task id. `cmd_acknowledge` routes through `status._load_for_write` (identity gate + migrate) and `_finalize` (revision-CAS, atomic). Semantics: identical `(path, task, reason)` → idempotent no-op (`ACK_IDEMPOTENT`, exit `0`); same path + different task/reason → `ACK_CONFLICT` (exit `2`, prior record untouched); unknown task id → `ACK_UNKNOWN_TASK` (exit `2`, nothing written); path already `planned` and never acknowledged → `ACK_ALREADY_PLANNED` (exit `0`, no record created).

**Rationale**: This is the exact pattern Feature 009 used for the v2→v3 provenance bump (`CURRENT_SCHEMA`, `backfill_*`, `_provenance_violations`), so migration, read-compat, CAS, and interruption-safety come for free from the existing `save`/`_LedgerLock`/`atomic_write` machinery (FR-005/FR-006/FR-017). `map_digest` at acknowledge time is provenance only (does not gate classification — clarification).

**Alternatives considered**: (a) A separate `acknowledgements.yaml` file — rejected: a second persisted state file breaks the single-ledger repo-as-state model (Principle II) and its atomic/CAS guarantees. (b) Within-v3 additive field (no bump) — rejected: the field carries an invariant (task must resolve), so the Global Definition of Done ("persisted formats are versioned and have forward migration tests") requires the bump.

---

## R4 — Trace-graph materialization

**Decision**: Build the graph purely from in-memory state:
- **SC → tasks**: `speckit.extract_sc_ids(spec.md)` × `speckit.extract_coverage_tags` / `extract_task_ids(tasks.md)` (the same mechanism as `consistency.run`).
- **task → commits**: `task["commits"]` (+ `task["started_commit"]`).
- **task → evidence**: `task["evidence"]` (the `<CLASS>:<summary>` string).
- **task → contexts/paths**: `task["context_provenance"]` (`context_ids` + `digest`); the paths attributed to a task are the effective-diff paths owned by those contexts (or, absent a map, the task's own commit-range diff).
- **findings → paths / cycles**: parse `specs/<feature>/revisions/revision-*.md` lines matching `[File]:[Line] - <text>`; link a finding to its path by the `[File]` token and to its review cycle by `revision-X` ↔ `review_cycles[round==X]`.
- **corrections → commits**: the commits recorded on the corrective round's tasks after a `REVIEW → IMPLEMENT (REJECTED)` transition.

**Rationale**: Every edge already exists in the ledger or the revision files; the trace is a *read*, satisfying "never re-derive state from agent narration" (Principle II). Reusing `consistency`'s SC-coverage helpers keeps the SC→task edge identical to the plan-time check it extends.

**Alternatives considered**: Re-parsing Git history to reconstruct task→commit links — rejected: the ledger already records commits authoritatively and reconcile verifies them.

---

## R5 — Trace validation defects

**Decision**: `trace.validate()` returns four defect kinds, all exit `1`:
1. **`uncovered-sc`** — a success criterion with zero covering tasks (independent of completion; reuses `consistency`'s coverage map).
2. **`missing-link`** — a completed task with no `evidence`, **or** a user-story-final task with no commit (per-task completeness clarification; intermediate tasks legitimately have no commit).
3. **`dangling-reference`** — a ledger reference (commit, task, finding, acknowledgement) that cannot be resolved; for commits, the defect is *surfaced* but authoritative existence enforcement is **deferred to `specops reconcile`** (FR-010) to avoid duplicating/contradicting Principle II's gate.
4. **`contradictory-ownership`** — a changed path whose task associates it (via `context_provenance.context_ids`) with one context while the map (`_candidates_for_path`) owns it under a different, undeclared context.

**Rationale**: The completed-SC definition (R12) plus the per-task completeness rule make cases 1–2 mechanically checkable. Case 4 reuses Feature 008 ownership and Feature 009 provenance without a new parser. Deferring commit existence to reconcile keeps the two gates non-overlapping (Rule 8 spirit).

**Alternatives considered**: Making commit-existence blocking inside `trace validate` — rejected: it would duplicate `reconcile` (Principle II) and could diverge from it.

---

## R6 — Drift gate wiring (and digest drift stays non-blocking)

**Decision**: Append a terminal **`drift`** gate to `review.GATE_ORDER` (`reconcile → lint → test → working-tree → drift`). It reuses `_working_tree_gate`'s already-computed effective diff, classifies each path (R2), and returns `FAIL` (exit `1`) listing only `unexplained` paths; `planned` and `discovered-and-acknowledged` pass. The existing `review.digest_drift_warning` stays a **non-blocking** appended warning (spec SC-008): 010 enforces *path* drift, not *map-digest* drift. The stale comment in `review.py` ("enforcement is deferred to Feature 010") is corrected to reflect that digest drift remains advisory.

**Rationale**: Placing the gate last means the cheaper reconcile/lint/test/working-tree gates still short-circuit first (cheapest-first invariant), and the drift gate only runs on an otherwise-clean, diffable tree. This makes "review blocks only unexplained drift" a real lifecycle behavior, not just a standalone command.

**Alternatives considered**: A separate parallel review path or a pre-`review` hook — rejected: forking the gate engine duplicates the reconcile/lint/test pipeline and risks contract drift.

---

## R7 — Findings and corrections linkage (no finding IDs)

**Decision**: Link a finding to a path by the `[File]` token in its `revisions/revision-X.md` line and to its review cycle by `X == review_cycles[].round`; link corrections via the corrective round's task commits. Introduce **no** per-finding identifier (deferred to Feature 011). A finding whose `[File]` matches no effective-diff path is reported as a **stale/misaligned finding** note (non-blocking) rather than a defect.

**Rationale**: The `revision-X.md` format (`[File]:[Line] - <rule/action>`) and the `revision-X ↔ round X` numbering are already fixed by the injected review directive (`templates/review.md` Step 4). Reusing them keeps 010 within the Feature 011 boundary while still connecting findings into the trace.

---

## R8 — Exit/`status` taxonomy and versioned JSON

**Decision**: `trace.py` defines a `TraceResult` (mirroring `contextmap.CommandResult`) with `S_*` statuses mapped to outcome classes and the `0/1/2` taxonomy: `0` — `TRACE_OK`, `DRIFT_CLEAN`, `ACK_RECORDED`, `ACK_IDEMPOTENT`, `ACK_ALREADY_PLANNED`, empty-diff, no-map; `1` — `DRIFT_BLOCKED` (unexplained present), `TRACE_INCOMPLETE` (any validation defect); `2` — `USAGE_ERROR` (not a Git repo / no baseline / bad args), `ACK_CONFLICT`, `ACK_UNKNOWN_TASK`. Every JSON payload embeds `output_version: 1` (a trace-local constant) plus the `status` field (CHK004 resolved: the enumeration is the `S_*` set above).

**Rationale**: Reuses the established read-command contract shape (`CommandResult.cls()/exit_code()` + `_CLASS_FOR_STATUS`) so the CLI bridge is identical to `_emit_context`. The explicit `output_version` satisfies the versioned-JSON clarification and gives Features 011–014 a stable surface.

---

## R9 — Determinism

**Decision**: All read outputs are byte-for-byte reproducible: effective-diff paths and every list (classes, defects, findings, contexts) are sorted by Unicode codepoint; JSON uses canonical key order; **no timestamps** appear in read-command output (the acknowledgement's `at` is stored in the ledger but not emitted by read commands). Classification/validation are pure functions of (ledger, map, diff, plan) with no wall-clock or environment input.

**Rationale**: Matches Feature 008/009 determinism (SC-001) and the ledger's own no-`Date.now` discipline; enables golden-file fixture assertions.

---

## R10 — CLI surface and outcome bridge

**Decision**: A new `trace_app = typer.Typer(...)` registered via `app.add_typer(trace_app, name="trace")` in `cli.py`, with `report`, `validate`, `classify` (read-only; `--path` repeatable, `--json`), and `acknowledge` (`<path>`, `--task`, `--reason`). A shared `_emit_trace(result)` bridges `TraceResult` → stdout/exit, mirroring the existing `_emit_context`.

**Rationale**: Consistent with the `context_app` registration and emission pattern already in `cli.py`; no change to global CLI wiring.

---

## R11 — Directive wiring + MINOR constitution amendment

**Decision**: `templates/review.md` (the `/specops-review` directive asset; there is no `templates/directives/review.md`) gains a step to run the deterministic drift gate / `specops trace validate` and to honor recorded acknowledgements; `templates/directives/implement.md` gains a note that a genuine discovered path is cleared with `specops trace acknowledge … --task … --reason …` (degrading to a no-op where SpecOps is not initialized). Because these change Principle IV directives, the constitution is amended **MINOR 1.5.0 → 1.6.0** (additive; no principle removed/redefined), submitted for explicit human approval in the same change set.

**Rationale**: Governance §"when a Principle IV directive changes" mandates the bump and template propagation; Feature 009 set the identical precedent (1.4.0→1.5.0).

---

## R12 — Completion semantics

**Decision**: A success criterion is **completed** iff *every* task tagged `[SC-xxx]` with it has ledger status `DONE` (mechanical; no human flag). Per-task completeness: every task must carry `evidence`; only the **user-story-final** task must additionally carry a commit — intermediate tasks close with evidence and no commit (Constitution Principle III one-commit-per-user-story). The user-story-final task is identified as the last task of a user story that carries commits, consistent with how `status.cmd_complete_task` records `commits` only when present.

**Rationale**: Both are direct encodings of the two clarifications and align with the existing `validate_invariants` rule (`DONE` requires `evidence`) — 010 adds the *final-task-needs-commit* refinement at the trace level without changing the ledger's per-task invariant.

**Alternatives considered**: SC completion as a human flag / any-task-complete — rejected in clarification (non-mechanical / too weak).
