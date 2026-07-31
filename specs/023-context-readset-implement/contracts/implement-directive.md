# Contract: Implement Directive — Context Read Set section (Feature 023)

**Artifact**: `src/specops/templates/directives/implement.md` (single source
for the native `after_implement` hook prompt and the legacy marker-block
inject). This contract fixes what the new section MUST instruct; the exact
prose is an implementation detail, asserted by
`tests/unit/test_implement_directive.py`.

## Placement

A new `### Context Read Set (Feature 023)` section, placed with the other
context-related sections (adjacent to "Context Provenance (Feature 009)" and
"Discovered Paths (Feature 010)"). No existing section is removed or
reworded beyond a cross-reference; the existing Graceful Degradation section
continues to cover the CLI-absent case for the whole block.

## Required instructions (MUST all be present)

| # | Instruction | Spec trace |
|---|-------------|-----------|
| C1 | At session start, **before the first task** (with the other session-start steps), read the `**SpecOps-Contexts**:` line from the active feature's `plan.md`; for each declared context id run `specops context resolve --id <cid> --phase implement` | FR-001 |
| C2 | The literal flag value is lowercase `implement` (the uppercase ledger phase name is a usage error here) | FR-001, research R2 |
| C3 | Scope the session's reads to the union of the resolved packages (`read_set` + `expanded_read_set` across declared contexts); reading less is always fine | FR-001, FR-002 |
| C4 | The read set is guidance plus record, **never a gate**: an out-of-set read is permitted, blocks nothing, and requires no acknowledgement by itself | FR-003 |
| C5 | A genuine out-of-set discovery that leads to a **changed** undeclared path follows the existing "Discovered Paths (Feature 010)" flow (`specops trace acknowledge …`) — cross-reference, not restatement | FR-004 |
| C6 | "no map present" (exit 0) → the step is a supported no-op; **any non-zero exit** of the resolution step → proceed without read-set scoping, never halt | FR-005, FR-006 |
| C7 | No new commands, flags, records, or outputs are introduced or implied; only existing surfaces are named | FR-002, FR-009 (declined per research R3) |

> **Note — spec edge case "no matching context"**: the `no_match` state (valid
> map, selector resolves to nothing — exit 0) is unreachable by construction on
> this path: the directive resolves by `--id` taken from the plan's declared
> context line, and `context plan-check` already blocked unknown declared ids
> at plan time (`S_UNKNOWN_DECLARED_CONTEXT`). No dedicated directive
> instruction is required; if it ever occurs (e.g. the map was edited
> mid-feature), the outcome is covered by C6's non-blocking rule — the package
> is simply absent and reads proceed normally for that selector.

## Delivery invariants

- Native path: `extension._build_hooks()["after_implement"]` prompt contains
  the section (sourced automatically from the file — no wiring change).
- Legacy path: `initializer.inject_block` of the updated content stays
  idempotent (`created` → `unchanged` on re-run; exactly one implement block).
- Both paths byte-identical in content (same source file).

## Out of contract (MUST NOT appear)

- Any wording that makes the read set blocking, or that instructs halting on
  resolution failure.
- Any new acknowledgement type for reads.
- Any reference to `status start-task` surfacing the read set (declined, R3).
