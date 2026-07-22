# Contract — Trace Graph & Validation

## Edges (all read from existing state)

| Edge | Source |
|---|---|
| SC → task | `speckit.extract_sc_ids(spec.md)` × `extract_coverage_tags`/`extract_task_ids(tasks.md)` |
| task → commits | `task["commits"]`, `task["started_commit"]` |
| task → evidence | `task["evidence"]` (`<CLASS>:<summary>`) |
| task → contexts | `task["context_provenance"].context_ids` (+ `digest`) |
| task → paths | effective-diff paths owned by the task's contexts |
| cycle → findings | parse `revisions/revision-<round>.md` lines `[File]:[Line] - <text>` |
| finding → path | the `[File]` token (no per-finding id — Feature 011) |
| cycle → corrections | corrective-round task commits after `REVIEW→IMPLEMENT(REJECTED)` |

## Completion (R12)

- **SC completed** ⇔ covering tasks non-empty **and** every covering task `status == DONE`.
- **Per-task completeness**: every DONE task has `evidence`; only the **user-story-final** task additionally requires ≥1 commit (intermediate tasks legitimately commitless).

## Validation defects (exit `1`)

| Kind | Rule |
|---|---|
| `uncovered-sc` | SC has zero covering tasks (any completion state) |
| `missing-link` | DONE task without `evidence`; or user-story-final task without a commit |
| `dangling-reference` | commit/task/finding/acknowledgement reference does not resolve; commit-existence **surfaced**, authoritative block deferred to `specops reconcile` (FR-010) |
| `contradictory-ownership` | task associates path with context A; map owns it under undeclared context B |

Non-defect notes (non-blocking): a finding whose `[File]` matches no effective-diff path (stale finding).

## Acceptance-gate property (SC-006)

For every completed SC and every effective-diff path, `trace validate` yields **either** a resolved chain / non-`unexplained` class **or** a specific blocking diagnostic — never silence.
