# Data Model: Lifecycle Recording Coverage

**Feature**: 022 | **Date**: 2026-07-31 | **Plan**: [plan.md](plan.md)

No ledger schema change — `status.yaml` stays at **schema v7**. This feature
adds one transient artifact, one new allowed value, and reuses two existing
record shapes.

## 1. Pre-ledger decision buffer *(new, transient)*

**Path**: `specs/<feature>/.specops-pending-steps.json`
**Owner**: SpecOps CLI (`status record-step` writes, `status init-spec`
drains and deletes). Never hand-edited, never read by any other command.

```json
{
  "version": 1,
  "steps": [
    { "step": "clarify", "decision": "run", "at": "2026-07-31T12:00:00+00:00" }
  ]
}
```

| Field | Type | Rules |
|---|---|---|
| `version` | int | `1`; unknown versions are ignored at drain (buffer discarded with a stderr note, never fatal) |
| `steps[].step` | string | one of the recordable steps (see §3); replace-by-step on re-record (no duplicates) |
| `steps[].decision` | string | `run` \| `skip` |
| `steps[].at` | string | timezone-aware UTC timestamp, same format as ledger records |

**Lifecycle**: created on first pre-ledger `record-step` → replaced-in-place on
re-records (atomic write via `fsutil`) → drained into
`workflow.skipped_steps` and **deleted** by `init-spec` → if the run is
abandoned before `init-spec`, the file is inert and disappears with the
feature directory (safe discard, spec Edge Cases). It lives in a committed
directory, so it may transiently appear in commits between record and drain —
harmless and documented (docs task T020).

**Drain merge rule**: buffer entries are appended to the freshly created
ledger's `workflow.skipped_steps` (which is empty at creation — no conflict
case). Post-drain, all recording goes directly to the ledger.

## 2. Optional-step decision record *(existing shape, unchanged)*

`workflow.skipped_steps[]` in `status.yaml` (Feature 007):
`{ step, decision, at }` — replace-by-step semantics
(`status.py:cmd_record_step`). Entry shape, field names, and semantics are
untouched; parity means both entry modes converge on identical records.

## 3. Recordable step values *(one additive value)*

`_OPTIONAL_STEPS` (`status.py:340`): `clarify | checklist | analyze` gains
**`converge`**. Validation-list change only — not a schema change; frozen
contract unaffected (the value set is CLI input validation, not a frozen
output shape).

## 4. Converge-appended task record *(existing shape, unchanged)*

Appended tasks enter `tasks[]` through `_sync_tasks` exactly like
tasks discovered at `init-spec`/`start-task`:

```yaml
- id: T042          # from tasks.md; [SC-xxx] tags live in tasks.md (directive obligation)
  status: PENDING
  started_commit: null
  commits: []
  evidence: null
  completed_at: null
```

Invariants preserved: existing entries (any status) preserved by ID; vanished
IDs → `orphaned: true`; re-running sync is idempotent (US1-4 determinism).
SC coverage is checked by the existing `consistency` surface against
`tasks.md` text — the ledger never stores tags.

## 5. Extension-manifest hook entries *(five additive registrations)*

`_HOOK_SPECS` (`extension.py:46`) gains:

| Directive stem | Hook point | optional | Purpose |
|---|---|---|---|
| `converge-pre` | `before_converge` | `false` | fail-closed recording-path precondition (no mutation on failure) |
| `converge` | `after_converge` | `false` | tag → `sync-tasks` → non-blocking consistency report |
| `clarify` | `after_clarify` | `false` | `record-step clarify --decision run` |
| `checklist` | `after_checklist` | `false` | `record-step checklist --decision run` |
| `analyze` | `after_analyze` | `false` | `record-step analyze --decision run` |

Same registration shape as existing entries (`extension: specops`, prompt
sourced from the directive template). No entry for `taskstoissues` — its
absence is contract, guarded by test (research R7).

## 6. State transitions touched

None. The phase state machine (SPECIFY → … → DONE) is unchanged; converge
recording happens within IMPLEMENT-phase corrective rounds (workflow) or at
whatever phase the human runs it (standalone — recording is phase-agnostic).
