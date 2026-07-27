# Data Model: Hardening II — API & State Robustness

**Feature**: 019-api-state-robustness | **Date**: 2026-07-27

This feature persists **nothing new**: the ledger stays at schema v7 and every
serialized byte is unchanged (SC-007). The entities below are *static* shapes (typing
contracts) and *protocol* states (the lock), not storage changes.

## Typed record schemas (`src/specops/records.py`, research D4)

All are `TypedDict`s — plain dicts at runtime, key-checked statically. `total=False`
sections mark keys that legacy records may lack (added by later schema features and
back-filled only where migrations say so). No runtime validation is added anywhere;
the existing tolerant filters (`isinstance(t, dict)`) remain the runtime posture.

### `TaskRecord`

| Key | Type | Notes |
|---|---|---|
| `id` | `str` | Speckit task id (`T001` …) |
| `status` | `str` | `PENDING` / `IN_PROGRESS` / `DONE` |
| `started_commit` | `str \| None` | HEAD at `start-task` |
| `commits` | `list[str]` | may contain the `(human)` sentinel (D7) |
| `evidence` | `str \| None` | legacy `<CLASS>:<summary>` string |
| `completed_at` | `str \| None` | RFC3339 UTC |
| *(optional)* `orphaned` | `bool` | vanished from tasks.md |
| *(optional)* `context_provenance` | `ContextProvenance` | v3+ |
| *(optional)* `evidence_refs` | `list[str]` | v6+ (`EV-…` ids) |

### `FindingRecord`

The 14 base keys of `findings.new_finding` (id, severity, rule, file, line, action,
expected_evidence, closure_criteria, state, task, commits, evidence, fixed_at,
verified_at) plus optional: `imported`, `producer`, `reviewed_digest` (v7 ingestion),
`promotion`, `dismiss_reason`, `evidence_id` (v6).

### `ReviewCycleRecord`

| Key | Type |
|---|---|
| `round` | `int` |
| `started_at` / `completed_at` | `str \| None` |
| `result` | `str \| None` (`APPROVED`/`REJECTED`) |
| *(optional)* `context_provenance` | `ContextProvenance` |
| *(optional)* `handoff` | `HandoffRecord` |

### `HandoffRecord`

`authorized_paths: list[str]`, `closed_at: str | None`, `findings: list[FindingRecord]`.

### `EvidenceRecord`

Mirrors `evidence.build_record` output exactly (id, producer, command, exit_code,
timestamp, commit_range, affected_paths, summary, context_map_digest, subject,
optional artifact digest keys). `evidence.py` becomes the *producer* of this type; the
shape source of truth stays in `evidence.build_record` and a parity test guards the two
(quickstart §3).

### `ContextProvenance`

`map: str` (`none`/`invalid`/`present`); when `present`: `digest: str`,
`context_ids: list[str]`.

### `LedgerDocument`

Top-level `status.yaml` mapping: `schema_version`, `feature`, `branch`, `baseline`,
`current_phase`, `active_artifact`, `revision`, `updated_at`, `tasks:
list[TaskRecord]`, `review_cycles: list[ReviewCycleRecord]`, `evidence:
list[EvidenceRecord]`, `acknowledgements`, `workflow`, `recovery`, and the optional
lane-provenance keys (`promoted_from_lane`, `lane_provenance`).

**Casting boundary**: `yaml.safe_load` output enters as `dict`; the cast to
`LedgerDocument` happens once at the canonical load/classify points; downstream
signatures consume the typed forms. Hand-edited ledgers with alien keys/types remain a
*runtime* concern of the existing validation paths, untouched.

## `LoadedLedger` (research D5)

Frozen dataclass replacing `handoff._load_write`'s 5-tuple arm:

| Field | Type |
|---|---|
| `feature_dir` | `Path` |
| `data` | `LedgerDocument` |
| `base_revision` | `int` |
| `base_violations` | `list[str]` |
| `repo` | `git.Repo` |

Error path: `HandoffLoadRefused(status: str, human: str)` — raised instead of returned;
converted to a `HandoffResult` at exactly one point (the `_handoff_command` decorator).
State transition of a load: `refused` (exception) ⊕ `loaded` (dataclass) — never a union
value.

## `DiffEntry` (research D6)

The parsed `(status, path)` pair from one `--name-status` line — `status` is Git's
single-letter code (`A`/`M`/`D`/`R`/…), `path` the last tab field (the new path for a
rename under `-M`). Produced only by `gitops.parse_name_status`; consumed by
`gitops.effective_diff_status` (rename-decomposed mode), `lane._diff_status`
(rename-aware mode, committed + staged), and transitively `trace`/`safety`.

## Ledger lock protocol states (research D1)

The `.lock` sidecar's lifecycle after hardening:

| State | Held by | Transition out |
|---|---|---|
| **absent** | — | contender `O_CREAT\|O_EXCL` create → **held** (atomic; unchanged fast path) |
| **held (fresh)** | live process (token stamped) | owner `__exit__` token-checked unlink → **absent**; or holder dies → **stale** after 30 s |
| **stale** (mtime > 30 s) | dead process | one contender's `os.rename` to a unique reclaim name → **absent** for everyone else (atomic single-winner); loser's rename raises `FileNotFoundError` → retry loop |
| **reclaimed sidecar** (`.lock.reclaim.<pid>.<ns>`) | reclaim winner | winner unlinks it, then competes through the normal create path |

Invariants:
- **INV-L1 (single winner)**: at most one contender transitions a stale lock out — the
  property the old unlink+recreate protocol violated and the FR-002 test asserts.
- **INV-L2 (token release)**: `__exit__` deletes the lock only when it still carries the
  owner's token (unchanged from today).
- **INV-L3 (durable authority)**: `ledger.save`'s revision-CAS remains the final
  lost-update guard regardless of lock behavior (unchanged).

## Sentinel ownership (research D7)

`ledger.HUMAN_COMMIT = "(human)"` + `ledger.is_human_commit(sha)` — the single
definition of the human-commit convention. `gitops` becomes sentinel-free; the four
ledger-value call sites filter per the research D7 audit table.
