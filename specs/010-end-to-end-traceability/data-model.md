# Phase 1 Data Model — End-to-End Traceability

Entities are **derived** from existing state (Ledger v3/v4, Feature 009 provenance, `revisions/*.md`) except the Acknowledgement Record, which is the sole new persisted object. All ordering is Unicode-codepoint; no timestamps appear in read-command output (R9).

---

## 1. Effective-Diff Path

The unit of classification.

| Field | Type | Source | Notes |
|---|---|---|---|
| `path` | str | `gitops.effective_diff(repo, baseline)` | repo-relative POSIX path |
| `change` | enum `added`\|`removed`\|`modified` | Git status of the path in `baseline..HEAD` | a rename yields a `removed` old + `added` new (R1, `--no-renames`); mode-only → `modified` |
| `class` | Path Class | classification algorithm | exactly one (§3) |
| `attribution` | str | classification | why this class (declared/owned-by/acknowledged/none) |

**Baseline resolution** (R1): `data["baseline"]` if present, else merge-base(branch, default). Explicit `--path` args replace Git derivation. Degenerate: clean tree / empty diff → empty set, exit `0`; not-a-repo / unresolvable baseline → exit `2`.

---

## 2. Path Class

Closed set of three; each effective-diff path gets exactly one (spec FR-003, SC-002).

| Class | Meaning | Blocks review? |
|---|---|---|
| `planned` | declared in `plan.md` **or** (map present) owned by a plan-declared context | no |
| `discovered-and-acknowledged` | covered by an Acknowledgement Record | no |
| `unexplained` | neither | **yes** (drift gate FAIL, exit `1`) |

**Precedence (R2)** — evaluate in order, first match wins:
1. acknowledgement exists for `path` → `discovered-and-acknowledged` *(discovery precedence)*
2. `path` ∈ plan-declared paths, or owned by a declared context → `planned`
3. otherwise → `unexplained`

---

## 3. Classification Algorithm (deterministic)

```
inputs: root
repo        = gitops.find_repo(root)              # None → USAGE_ERROR (exit 2)
baseline    = ledger.baseline or merge_base(...)  # unresolvable → USAGE_ERROR (exit 2)
diff        = gitops.effective_diff(repo, baseline)   # [] → empty result, exit 0
acks        = { a.path for a in ledger.acknowledgements }
plan_paths  = { p for (p, _action) in speckit.parse_plan_path_action(plan.md) }
declared    = speckit.parse_plan_context_ids(plan.md)      # [] when no map / none declared
for path in sorted(diff, key=codepoint):
    if path in acks:                        class = discovered-and-acknowledged
    elif path in plan_paths:                class = planned  (attribution: plan-declared)
    elif map_present and owned_by_declared(path, declared): class = planned (owned-by:<ctx>)
    else:                                   class = unexplained
```
`owned_by_declared` uses `contextmap._candidates_for_path(contexts, path)` and checks the owning context id ∈ `declared`. No-map repos skip the ownership branch (fallback to plan paths only, spec FR-013).

---

## 4. Acknowledgement Record *(new persisted object — Ledger v4)*

Stored as an element of the top-level ledger list `acknowledgements`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `path` | str | yes | repo-relative POSIX path acknowledged |
| `task` | str | yes | a known non-orphaned task id (else `ACK_UNKNOWN_TASK`, exit 2) |
| `reason` | str | yes | concise human reason; trimmed, non-empty, ≤ 200 chars (CHK010 bound) |
| `map_digest` | str \| null | yes | current map digest at acknowledge time, or `null` when no map — **provenance only**, never gates classification (clarification) |
| `at` | str (RFC3339 UTC) | yes | `ledger.now_utc()`; stored, **not** emitted by read commands |

**Write semantics** (`trace.cmd_acknowledge`, via `status._load_for_write`/`_finalize`):

| Situation | Status | Exit | Effect |
|---|---|---|---|
| new discovered path + valid task | `ACK_RECORDED` | 0 | append record (revision-CAS, atomic) |
| identical `(path, task, reason)` already present | `ACK_IDEMPOTENT` | 0 | no duplicate |
| same `path`, different `task`/`reason` | `ACK_CONFLICT` | 2 | prior record untouched |
| unknown/orphaned `task` | `ACK_UNKNOWN_TASK` | 2 | nothing written |
| `path` already `planned`, never acknowledged | `ACK_ALREADY_PLANNED` | 0 | no record (FR-007 no-op) |

Concurrent/stale writes fail closed via the existing `_LedgerLock` + revision compare in `ledger.save` (FR-005/FR-006).

---

## 5. Trace Graph

Materialized read structure (R4); no new storage.

```
SuccessCriterion(sc_id, completed)              # completed = all covering tasks DONE (R12)
  └─ covered_by → [ Task ]
Task(id, status, evidence, commits, started_commit, context_provenance, is_story_final)
  ├─ commits      → [ commit_sha ]
  ├─ evidence     → "<CLASS>:<summary>"
  ├─ contexts     → context_provenance.context_ids   (+ digest)
  └─ paths        → effective-diff paths owned by those contexts
ReviewCycle(round, result, context_provenance)
  ├─ findings     → [ Finding ]                       # from revision-<round>.md
  └─ corrections  → [ commit_sha ]                    # corrective-round task commits
Finding(file, line, text, round)                      # linked by [File] token; NO id (Feature 011)
```

**Completed-SC (R12)**: `all(task.status == "DONE" for task in covered_by)` and `covered_by` non-empty. **Per-task completeness (R12)**: `evidence` required for every DONE task; `commits` required only for the user-story-final task.

---

## 6. Trace Defect

Emitted by `trace.validate()`; any non-empty result → exit `1` (spec FR-009).

| Kind | Trigger | Notes |
|---|---|---|
| `uncovered-sc` | SC with zero covering tasks | independent of completion; reuses `consistency` coverage map |
| `missing-link` | DONE task with no `evidence`, or user-story-final task with no commit | intermediate tasks exempt from the commit rule (R12) |
| `dangling-reference` | unresolvable commit/task/finding/acknowledgement reference | commit-existence **surfaced only**; authoritative block deferred to `reconcile` (FR-010) |
| `contradictory-ownership` | task associates a path with context A while map owns it under undeclared context B | reuses `_candidates_for_path` + provenance |

A finding whose `[File]` matches no effective-diff path → **non-blocking** stale-finding note (R7), not a defect.

---

## 7. Trace Report

Rendering of §5 + §2 for the current effective diff. Human form: SC → chain, then a **Discoveries** section listing each `discovered-and-acknowledged` path with its `reason` + `task` (spec FR-011). JSON form: the same graph plus `output_version: 1` and per-path `class`/`attribution`.

---

## 8. Exit / status / version mapping (R8, single source of truth)

| `status` (`S_*`) | class | exit | Meaning |
|---|---|---|---|
| `TRACE_OK` / `DRIFT_CLEAN` | pass | 0 | complete trace / no unexplained path (incl. empty-diff, no-map) |
| `ACK_RECORDED` / `ACK_IDEMPOTENT` / `ACK_ALREADY_PLANNED` | pass | 0 | acknowledgement recorded / no-op |
| `DRIFT_BLOCKED` | gate-rejection | 1 | ≥1 `unexplained` path |
| `TRACE_INCOMPLETE` | gate-rejection | 1 | ≥1 validation defect |
| `USAGE_ERROR` | infra-error | 2 | not a Git repo / no baseline / bad args |
| `ACK_CONFLICT` / `ACK_UNKNOWN_TASK` | infra-error | 2 | conflicting / unknown-task acknowledgement |

Every JSON payload carries `status` + `output_version: 1`. Ledger persisted format advances **v3 → v4**; pre-v4 ledgers migrate by backfilling `acknowledgements: []` and remain readable (FR-016).
