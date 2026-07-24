# Contract: Composed Corrective Loop (`workflow.yml`)

Authoritative step contract for the Feature 016 edit to
`src/specops/templates/workflows/specops/workflow.yml`. This is a **definition
contract**, not a code API: it fixes step ids, ordering, guards, the condition, and
the fail-closed/degrade semantics that the structural and integration tests assert.
The exact YAML is produced during implementation; this document is the acceptance
shape.

## Scope

Only the corrective loop and the steps around it change. The specify → clarify →
checklist → plan → readiness-gate → tasks → analyze prefix is unchanged.

## Loop body — ordered steps

Within `corrective-loop` (`type: do-while`, `max_iterations` unchanged):

1. **`reconcile-pre-impl`** — `shell: specops reconcile --json` *(existing)*
   Fail-closed precondition of the corrective transition.
2. **`implement`** — `command: speckit.implement` *(existing)*
3. **`review-soft`** — `shell: specops review --json --soft`, `output_format: json`
   *(existing)*
   Mechanical gate. Exit 0 always; verdict in `output.data.verdict`.
4. **`semantic-review-round`** — `type: if` *(new)*
   - condition: `{{ steps.review-soft.output.data.verdict != 'REJECTED' }}`
   - then:
     - **`semantic-review`** — `command: specops.review` *(new)*
       Reads the effective diff, records structured findings, verifies fixed
       findings, and executes its owned outcome transition (`DONE`/`IMPLEMENT`).
       Hard step — an unresolvable command **aborts** the run (FR-016).
5. **`handoff-report`** — `shell: specops handoff report --json`,
   `output_format: json` *(new)*
   Read-only. Exposes `output.data.remaining_blocking: list[str]`.
6. **`open-corrective-round`** — `type: if` *(existing, guard unchanged)*
   - condition: `{{ steps.review-soft.output.data.verdict == 'REJECTED' }}`
   - then: `shell: specops status transition-phase IMPLEMENT -r REJECTED --if-needed`
   Mechanical-reject corrective round only; the semantic reject is owned by
   `semantic-review`.

### Loop condition

```
condition: >-
  {{ steps.review-soft.output.data.verdict == 'REJECTED'
     or steps.handoff-report.output.data.remaining_blocking }}
```

Re-iterate while the mechanical verdict is `REJECTED` **or** any unverified blocking
finding remains. Empty `remaining_blocking` (no findings / legacy repo) ⇒ condition
driven by the mechanical verdict alone ⇒ **auto-degrade** (FR-006). Fallback forms if
the engine sandboxes Jinja2 list-truthiness are documented in `research.md` R2; the
`test_definition_parses_in_real_speckit_engine` test gates the final form.

## After the loop — unchanged

7. **`terminal-gate`** — `shell: specops review` (hard, no `--soft`) *(existing)*
   Fails closed (exit 1) unless the mechanical verdict is `APPROVED`; an
   exhausted-loop still-rejecting feature halts here (engine abort).
8. **`done`** — `shell: specops status transition-phase DONE -r APPROVED --if-needed`
   *(existing)*
   Idempotent completion. The transition itself **fails closed while any blocking
   finding is unverified** (Feature 011), delivering FR-004/FR-005 without a new gate.

## Behavioral acceptance (maps to spec)

| Contract property | Requirement | How verified |
|---|---|---|
| Semantic review runs when mechanical passes | FR-001, FR-002 | Unit: body contains guarded `command: specops.review` after `review-soft` |
| Semantic review skipped on mechanical reject | FR-002, Story 4 | Unit: `semantic-review` guard is `verdict != 'REJECTED'` |
| Loop reacts to unverified blocking | FR-003 | Unit: condition references `remaining_blocking`; Integration: report is read-only |
| Bounded loop | FR-010 | Unit: `max_iterations` unchanged |
| No new transitions | FR-009 | Integration: only corrective `IMPLEMENT -r REJECTED` + `done` present |
| Terminal fail-closed on blocking | FR-004, FR-005 | `transition-phase DONE` blocks on unverified blocking (011 test); terminal hard gate present |
| Native steps only | FR-007 | Unit: every step type ∈ native set |
| Fail closed on unavailable review | FR-016 | Integration: co-installation invariant (review command installed with workflow) |
| Auto-degrade, no toggle | FR-006, FR-015 | Unit: no config-gated skip of the review; empty `remaining_blocking` completes |

## Non-contract (explicitly out)

- No change to `specops handoff` CLI, finding schema, or lifecycle (non-goal).
- No new workflow engine/loop/gate/resume primitive (Rule 8).
- No parallel fan-out (consistent with Feature 007).
- No external-review ingestion (Feature 015).
