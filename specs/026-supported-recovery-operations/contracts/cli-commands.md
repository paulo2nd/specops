# CLI Contract: Supported Recovery Operations

**Feature**: 026 | **Phase**: 1

Three new commands and four modified outputs. Exit codes stay inside the frozen
closed set `{0, 1, 2}` (constitution Principle VI); every refusal exits non-zero
(FR-021, the #72 invariant).

---

## `specops status amend-task <TASK_ID> --evidence <STR> --reason <STR>`

Appends a corrected evidence record to a task already `DONE`.

| Option | Required | Notes |
|---|---|---|
| `TASK_ID` | yes | positional |
| `--evidence` | yes | must satisfy `evidence.validate_string` (`<CLASS>:<summary>[; …]`) |
| `--reason` | yes | non-empty; content never validated (FR-007) |

**Success (exit 0)**, stdout:

```
Task 'T027' amended. Evidence: TEST_REPORT: 1795 passed
Superseded 1 prior record (EV-a1b2c3d4e5f6). Reason: original close recorded no gate run
```

**Refusals (exit 1)** — each writes nothing:

| Condition | Message |
|---|---|
| task unknown | `Task 'T099' not found in tasks.md.` |
| task not `DONE` | `Task 'T027' is not DONE (status: IN_PROGRESS). Use 'complete-task' to close it.` |
| `--reason` empty/missing | `A reason is required to amend a task.` |
| evidence grammar violation | `Invalid evidence format. Expected '<CLASS>:<summary>'…` |

**Exit 2**: unparseable ledger, unsupported/too-new schema, not a Git repository
(inherited from `load_for_write` / `LedgerParseError`).

**Guarantees**: task `status`, `completed_at`, `commits`, `started_commit`, and
`context_provenance` are untouched; no prior evidence record's content changes;
`reconcile` accepts the result (FR-008).

---

## `specops feature use <DIR>`

Repoints the active feature.

**Success (exit 0)**:

```
Active feature: specs/025-review-round-integrity → specs/026-supported-recovery-operations
Not yet present: plan.md, tasks.md, status.yaml
Outgoing feature has unfinished work: task T041 IN_PROGRESS, review round 2 open
```

Lines 2 and 3 appear only when they apply. Line 3 never fails the command
(FR-012a).

**Idempotent no-op (exit 0)**: `Active feature already: specs/026-… (no change)`

**Refusals (exit 1)**:

| Condition | Message |
|---|---|
| directory missing | `Feature directory not found: specs/026-x` |
| outside `specs/` | `Feature directory must live under 'specs/': /tmp/x` |
| no `spec.md` | `Not a feature directory (no spec.md): specs/026-x` |
| env override in effect naming elsewhere | `SPECIFY_FEATURE_DIRECTORY is set to 'specs/025-y' and takes precedence over .specify/feature.json; repointing would have no effect. Unset it, or run with the target you want.` |

**Exit 2**: not a Git repository; `.specify/feature.json` present but unparseable.

---

## `specops feature rename <OLD> <NEW> [--branch <NAME>]`

Renames/renumbers a feature.

**Success (exit 0)**:

```
Renamed: specs/026-y → specs/027-y
Ledger identity: feature 026-y → 027-y; branch 026-y → 027-y
spec.md: **Feature Branch** header updated
Active feature pointer followed the rename.
3 remaining references to the old name (not changed):
  specs/027-y/plan.md:14
  specs/027-y/tasks.md:8
  specs/027-y/checklists/requirements.md:5
```

Without `--branch`, line 2 reads `branch reference unchanged (026-y) — pass
--branch to update it`. When the renamed feature was not active, line 4 reads
`Active feature pointer unchanged (points at specs/024-z).`

**Refusals (exit 1)**:

| Condition | Message |
|---|---|
| source missing / not a feature dir | `Not a feature directory: specs/026-y` |
| target exists | `Target already exists: specs/027-y` |
| target outside `specs/` | `Feature directory must live under 'specs/': ../027-y` |
| override names the source | `SPECIFY_FEATURE_DIRECTORY is set to 'specs/026-y'; renaming it would leave the override pointing at a directory that no longer exists. Unset it and re-run.` |
| ledger revision advanced mid-write | inherited `StaleLedgerError` |

**Exit 2**: not a Git repository; unparseable ledger.

**Guarantees**: all-or-nothing per FR-020 — no half-moved directory, no pointer at
a non-existent path (research D9).

---

## Modified outputs

### `specops status show` (FR-014, FR-014a)

Gains a first line naming the resolved directory and, when the answer was
inferred, saying so:

```
feature directory: specs/026-supported-recovery-operations
feature: 026-supported-recovery-operations
…
```

Inferred case: `feature directory: specs/026-… (inferred — no SPECIFY_FEATURE_DIRECTORY and no .specify/feature.json)`

### `consistency` / `preflight` (FR-014a)

The existing `feature:` echo (shipped 0.12.0) gains the same inference suffix. The
`--json` `feature` key is unchanged; an additive `feature_source` key carries
`override` | `pointer` | `inferred`.

### `trace report` (FR-006)

Each task entry gains an additive optional `evidence_amended: true` when the
task's current evidence record is an amendment, and `evidence_history` — the
superseded record ids, oldest first, as defined in [data-model.md](../data-model.md). `output_version` is unchanged — both are documented
additive per-command keys under the frozen envelope policy.

---

## JSON envelope

No command here introduces a new outcome class or exit code. `feature use`,
`feature rename` and `status amend-task` are state-changing operator commands and
follow the established `status` subcommand precedent — `start-task`,
`complete-task` and `transition-phase` all emit human output only. The Definition
of Done's "automation surfaces have stable JSON" applies to the read-only
validation and reporting surfaces (`reconcile`, `consistency`, `preflight`,
`report`, `trace`, `gate`), which are what automation consumes; a state-changing
operator command is not one. Adding `--json` here would break the symmetry of the
task-lifecycle commands for no consumer that exists.
