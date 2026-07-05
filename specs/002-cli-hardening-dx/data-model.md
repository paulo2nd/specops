# Data Model: CLI Hardening & Developer Experience

**Feature**: `specs/002-cli-hardening-dx` | **Date**: 2026-07-05

This feature modifies behavior around the existing ledger schema (defined in
`specs/001-specops-cli/contracts/ledger-schema.md`); it does not change the
schema itself. Entities below describe the touched structures and the new
error vocabulary.

## Review Cycle (existing — behavior clarified)

One entry in the ledger's `review_cycles[]` list.

| Field | Type | Notes |
|---|---|---|
| `round` | int | 1-based, assigned when the cycle is opened |
| `started_at` | date string \| null | set when REVIEW is entered; null on corrective placeholder cycles until the next REVIEW entry |
| `completed_at` | date string \| null | set when a result is recorded |
| `result` | `"APPROVED"` \| `"REJECTED"` \| null | **vocabulary now closed** — free text no longer accepted anywhere |

**State transitions (as fixed by this feature)**:

- `IMPLEMENT → REVIEW`: appends a new open cycle (`result: null`) — unchanged.
- `REVIEW → DONE -r APPROVED`: writes `result: APPROVED` + `completed_at` on
  the latest open cycle, **then** evaluates the DONE gate — both land in one
  ledger write.
- `REVIEW → DONE` (no result): allowed only if the latest cycle is already
  APPROVED (pre-recorded state) — unchanged behavior, now reachable honestly.
- `REVIEW → DONE -r REJECTED`: rejected (exit 1), ledger untouched; error
  message names the corrective path.
- `REVIEW → IMPLEMENT -r REJECTED`: closes the cycle as REJECTED and appends
  the next-round placeholder — unchanged.
- Any transition with `-r` outside {APPROVED, REJECTED} (case-insensitive):
  rejected before any ledger read/write.

**Invariant**: a ledger in phase DONE has `review_cycles[-1].result ==
"APPROVED"`. No CLI path can reach DONE otherwise.

## Ledger file (existing — persistence hardened)

`<feature_dir>/status.yaml`. Schema unchanged. New persistence contract:

- Every save writes the full document to `<feature_dir>/status.yaml.tmp`,
  flushes, then atomically replaces `status.yaml` (`os.replace` semantics).
- Crash outcome space: {previous complete file, new complete file} — a
  partial file is unreachable.
- A stale `status.yaml.tmp` may exist after a crash; it is never read and is
  overwritten by the next save.
- Legacy tolerance (read side): missing `review_cycles` key ≡ empty list;
  missing/empty `tasks` ≡ empty list. `status show` renders zero counts.

## Evidence String (existing — grammar closed)

Attached to DONE tasks. Grammar (single validation path, R5):

```
evidence      = part *( "; " part )
part          = class ":" summary
class         = "CLI_LOG" | "TEST_REPORT" | "SCREENSHOT_PATH" | "CODE_DIFF"
summary       = non-empty text, first char not whitespace
```

- `"; "` is **always** a part separator (strict split); a segment that is not
  a valid `part` invalidates the entire string.
- Rejections (exit 1, task stays IN_PROGRESS): empty summary (`CLI_LOG:`),
  unknown class (`LOG:x`), separator-orphaned text (`CLI_LOG:a; done`),
  missing colon.

## Status Summary (new — derived, read-only)

Output of `specops status show`; computed from the ledger, never persisted.

| Fact | Source |
|---|---|
| feature | ledger `feature` (fallback: feature dir name) |
| branch | ledger `branch` |
| phase | ledger `current_phase` |
| active task | first task with status `IN_PROGRESS`, else `none` |
| task counts | tally of `tasks[].status` + `orphaned: true` flags |
| review cycles | one line per cycle: round, result (`open` when null), dates |

## SpecopsError hierarchy (new — in-process failure vocabulary)

| Class | Exit code | Meaning |
|---|---|---|
| `SpecopsError` | 1 | Blocking failure (precondition, validation, gate) |
| `LedgerParseError(SpecopsError)` | 2 | Unexpected/parse error (corrupt ledger YAML, invalid structure) |
| `ConfigError(SpecopsError)` | 1 | Missing/unparseable `specops.json` (existing class, re-parented) |
| `ManifestResolutionError(SpecopsError)` | 1 | Prompt-target resolution failure (existing class, re-parented) |

Mapping happens in exactly one place (CLI boundary): message → stderr,
`exit_code` → process exit. Business modules never terminate the process.
Full contract: [contracts/errors.md](contracts/errors.md).
