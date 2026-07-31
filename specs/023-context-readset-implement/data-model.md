# Data Model: Context Read-Set Consumption in IMPLEMENT

**Feature**: 023-context-readset-implement | **Date**: 2026-07-31

This feature **persists nothing new**. No ledger schema change (ledger stays at
v7), no context-map schema change, no new file formats. The entities below are
*consumed* — their shapes are owned by Features 008/009/010 and are frozen
(Feature 021); this feature reads them and must not alter them.

## Consumed Entities

### Context package (per resolved context)

Produced by `specops context resolve --id <cid> --phase implement` (owner:
Feature 008, `contextmap.cmd_resolve`, `OUTPUT_VERSION = 1`). Fields, as
frozen:

| Field | Type | Meaning for this feature |
|-------|------|--------------------------|
| `context_id` | string | The declared context this package belongs to |
| `phase` | string \| null | Echo of the requested phase (`implement`) |
| `read_set` | list[string] | The context's direct, ordered, phase-specific read set |
| `read_set_source` | string | `phase` \| `base` \| `empty` — which key supplied the set |
| `dependencies` | list[string] | Direct dependency context ids |
| `expanded_read_set` | list[object] | Cycle-safe, deduplicated reads drawn from dependencies (each with contributing context) |
| `gates`, `risk` | list / object | Present in the package; not consumed by this directive |

**Session context package (derived, in-prompt only)**: the union of
`read_set` ∪ `expanded_read_set` files across all declared contexts. This
union exists only in the agent's working context during the session — it is
**never written anywhere**.

### Plan context declaration

The `**SpecOps-Contexts**: id1, id2, …` line in the active feature's `plan.md`
(owner: Feature 009, parsed by `speckit.parse_plan_context_ids`). This feature
reads the same line the plan directive already requires; format unchanged.

### Discovered-path acknowledgement

Ledger record written by `specops trace acknowledge <path> --task <id>
--reason <text>` (owner: Feature 010). Unchanged shape; this feature only
*routes* to it: an out-of-set discovery that results in a **changed** path is
acknowledged exactly as today. An out-of-set *read* that changes nothing
produces **no record** — there is deliberately no "read acknowledgement"
entity (see research.md R6).

### Context provenance snapshot

Ledger fields written automatically at task close / review open (owner:
Feature 009): resolved context ids + map digest, or `{map: none}` /
`{map: invalid}` markers. Unchanged; noted here because it is the existing
record that makes the read-set consumption auditable after the fact.

## State Transitions

None. The directive step is read-only; every map state maps onto an existing,
already-supported outcome (research.md R4):

```text
no map            → resolve exits 0 ("no map present")   → session proceeds as today
invalid map       → resolve exits 1 (frozen contract)    → directive: proceed without scoping
valid, no match   → resolve exits 0 ("no matching ctx")  → read normally for that selector
valid, resolved   → package returned                     → scope session reads to union
CLI absent        → (no invocation)                      → existing Graceful Degradation
```

## Validation Rules

- The directive must never derive a blocking outcome from any row above
  (FR-003; spec SC-002/SC-004).
- The union computation is set-union with the map's deterministic ordering
  preserved per package; duplicates across contexts are read once.
- Coverage invariant (acceptance gate, proven by test): for every
  plan-declared path `p`, `resolve --path p --phase implement` yields a
  package contained in the union of the declared contexts' packages — holds
  because `plan-check` blocked undeclared owners at plan time (research.md R1).
