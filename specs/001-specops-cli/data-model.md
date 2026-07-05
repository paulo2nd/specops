# Data Model: SpecOps CLI

**Date**: 2026-07-05 | **Plan**: [plan.md](plan.md) | **Research**: [research.md](research.md)

## Entity Overview

```text
ClientConfig (specops.json, repo root)
SpecWorkspace (feature dir from .specify/feature.json)
 └── StateLedger (status.yaml)
      ├── TaskEntry[]      ←(id sync)— Speckit tasks.md checklist lines (T001…)
      │    └── EvidenceEntry (string field, <CLASS>:<summary> format)
      ├── ReviewCycle[]    — corrective-round history
      └── Recovery         — resumption pointer
DirectiveBlock[] — marker-delimited regions inside Speckit prompt files
PackagedAssets — files bundled in the wheel, source of everything installed
RevisionReport — revisions/revision-X.md produced by /specops.review
```

## StateLedger (`<feature_dir>/status.yaml`)

Single source of truth for execution state. Written exclusively by `specops status`.
Full field-level schema with validation rules: [contracts/ledger-schema.md](contracts/ledger-schema.md).

| Field | Type | Notes |
|---|---|---|
| `feature` | string | Feature directory name (e.g., `001-specops-cli`) |
| `branch` | string | Branch at ledger creation; reconcile warns on mismatch |
| `baseline` | string | Commit hash at ledger creation |
| `current_phase` | enum | `SPECIFY…DONE`; transitions per state machine below |
| `recovery` | Recovery | Resumption pointer |
| `tasks` | TaskEntry[] | Mirrored from `tasks.md` on every command (R5) |
| `review_cycles` | ReviewCycle[] | One entry per REVIEW entry/corrective round |
| `created_at` / `updated_at` | date | ISO YYYY-MM-DD |

### TaskEntry

| Field | Type | Rules |
|---|---|---|
| `id` | string | Speckit id verbatim (`T001`); unique |
| `status` | enum | `PENDING → IN_PROGRESS → DONE`; only one IN_PROGRESS at a time |
| `started_commit` | string\|null | HEAD at `start-task`; basis for evidence harvest |
| `commits` | string[] | Filled at completion from `started_commit..HEAD`; non-empty required for DONE |
| `evidence` | string\|null | Required for DONE (any mode); `<CLASS>:<summary>[; …]` |
| `completed_at` | date\|null | Set at completion |
| `orphaned` | bool (optional) | True when id no longer exists in `tasks.md`; reported, never auto-deleted |

**State transitions**: `PENDING→IN_PROGRESS` (`start-task`; fails if another task is
IN_PROGRESS); `IN_PROGRESS→DONE` (`complete-task`; fails without evidence or with
failing/absent `test_command` in `--auto`; an empty `commits[]` is allowed when
`--evidence` is used — intermediate tasks within a user story may have no commits
of their own); no other transitions. DONE is terminal (corrective work tracks in
ReviewCycle, not by reopening tasks).

### Recovery

| Field | Type | Notes |
|---|---|---|
| `active_task` | string\|null | IN_PROGRESS task id; null when none |
| `last_commit` | string\|null | Latest harvested commit |
| `blockers` | string[] | Free-form, set by agents on stop-and-ask |

### ReviewCycle

| Field | Type | Notes |
|---|---|---|
| `round` | int | 1, 2, 3… |
| `started_at` / `completed_at` | date\|null | |
| `result` | enum\|null | `APPROVED` \| `REJECTED` \| null while open |

### Phase state machine

`SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE`, forward-only, plus the single
exception `REVIEW → IMPLEMENT` requiring result `REJECTED` (appends ReviewCycle with
round+1). `DONE` requires latest `review_cycles[].result == APPROVED`. Invalid
transition: exit 1, file untouched.

## ClientConfig (`specops.json`, repo root)

| Field | Type | Required | Notes |
|---|---|---|---|
| `test_command` | string | for `--auto` | Client's test runner; exit code is the gate |
| `lint_command` | string | for review | Referenced by the review prompt |
| `skills_dir` | string | for review | Default `.specify/skills` |

Validation: unknown keys preserved (R10); missing file → exit 1 pointing to
`specops init`; missing `test_command` during `--auto` → exit 1.

## DirectiveBlock

Marker-delimited region appended to a Speckit prompt file. Grammar, block ids,
versioning, idempotency and corruption rules: [contracts/directive-blocks.md](contracts/directive-blocks.md).
Owned by SpecOps; content between markers replaced on re-init; everything outside
markers is never touched (SC-010).

## PackagedAssets (`src/specops/templates/`)

`review.md`, `status.yaml` scaffold, `specops.json` template, `directives/plan.md`,
`directives/implement.md`. Bundled via package data; installed verbatim (R10). The
package is the sole source of installed content (FR-017).

## RevisionReport (`<feature_dir>/revisions/revision-X.md`)

Produced by the review agent, not by the CLI. Numbering: max existing X + 1.
Non-conformity line format: `[File]:[Line] - [rule violated and short action]`.

## Cross-artifact identifiers (read-only inputs)

| Token | Source | Pattern |
|---|---|---|
| Task id | `tasks.md` checklist lines | `^\s*-\s*\[[ xX]\]\s*(T\d+)\b` |
| SC id | spec Success Criteria bullets | `-\s*\*\*(SC-\d+)\*\*:` |
| Coverage tag | task line labels | `\[(SC-\d+(?:,SC-\d+)*)\]` |
| Action suffix | plan path declarations | `\((create|modify|remove)(?:\s+OR\s+(extend|modify))?\)` |

These structural tokens are the ONLY things parsed from client artifacts — prose
language is irrelevant (FR-014a).
