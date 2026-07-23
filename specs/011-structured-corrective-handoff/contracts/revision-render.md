# Contract: Revision Rendering, Trace Re-sourcing & Legacy Import

## Authoritative state → rendered Markdown (FR-013)

The review directive **authors structured findings first** (`handoff finding add`); the ledger is
authoritative. `revisions/revision-X.md` is a **deterministic projection** rendered from the
round's handoff, never hand-authored (except pre-existing legacy prose).

Rendered line format — **unchanged** from the current convention so prior consumers and Feature
010's `trace._FINDING_RE` still match byte-for-byte (SC-006):

```
<file>:<line> - <action>
```

- Findings rendered in canonical order (round, severity, file codepoint, line, id).
- `APPROVED` (zero blocking findings) and `Skipped gate: <name> (<reason>)` lines preserved.
- Stable finding **IDs are not in the human line** — they live in the ledger and are surfaced by
  `handoff report`; this is what keeps the Markdown format compatible.
- Byte-for-byte reproducible from identical structured state (SC-006).

## Feature 010 trace re-sourcing (FR-015, CHK033)

`trace._findings(feature_dir)`:

1. **If any review cycle has a `handoff`** → emit each structured finding as
   `{id, file, line, round, text: action}` (adds the stable `id` the 010 report deferred).
2. **Else** → fall back to the current behavior: parse `revisions/revision-*.md` via
   `trace._FINDING_RE`, linked to round X.

The 010 report/graph contract is unchanged except finding nodes now carry `id` when structured
(additive). Legacy 010 fixtures (no handoffs) hit path 2 unchanged → no regression (SC-009).

## Legacy import (FR-014)

`handoff import [--round N]` reads existing `revision-X.md` `<file>:<line> - <action>` lines (same
regex) and creates structured findings preserving `file`/`line`/`action` verbatim, assigning
`R<round>-F<NN>` ids, `severity: advisory`, `state: OPEN`.

- **Explicit/opt-in** — never runs implicitly.
- Zero loss of location or action text (SC-007).
- `advisory` default guarantees import cannot retroactively block an already-approved feature
  (Rule 5, FR-008); a maintainer may deliberately escalate a finding to `blocking`.
- Repos that never import keep reading legacy prose via the FR-014 supported-prior-shape path;
  such repos degrade to the Feature 006 approval gate (no structured findings).
