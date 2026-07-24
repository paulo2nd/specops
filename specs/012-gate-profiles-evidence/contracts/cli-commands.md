# Contract: CLI commands (Feature 012)

New/changed `specops` surfaces. Exit codes follow the fixed taxonomy (`outcome.py`):
`0` ok, `1` blocking/fail-closed, `2` usage/input error. Read-only commands never
mutate state (FR-015). `--json` emits a stable, `output_version`-stamped object.

## New sub-app: `specops gate` (read-only inspection)

Registered like the `context`/`trace`/`handoff` sub-apps (`app.add_typer(gate_app,
name="gate")`). **No** `run` command — profiles execute inside `specops review`
(clarify decision).

### `specops gate list [--json]`
Resolve and display the selected suite for the current effective diff: every declared
gate with `selected` + `reason` + order. No config file ⇒ shows the synthesized
default profile and says so.
- `0` always (a missing map / no baseline is a reported degrade, not an error);
- `2` only on an unreadable/malformed invocation.

### `specops gate validate [--json]`
Validate `.specify/specops/gate-profiles.yaml` (FR-014). Distinct diagnostic per
defect: duplicate name, empty command, non-positive timeout, unknown/unparseable
predicate key, dangling `contexts`/`gate_ref` reference, unsupported `output_version`.
(Ordering-cycle detection is reserved for a future ordering hint — not a v1 defect.)
- `0` valid (including "no profile file — default profile in effect");
- `1` one or more validation defects (each named);
- `2` unreadable file / bad arguments.

### `specops gate report [--json] [--sarif]`
Report the last verdict's provenance from the ledger (FR-011/FR-012): each gate's
`disposition`, `reason`, covered `commit_range`/`affected_paths`, and supporting
`evidence_id`; plus the structured `evidence[]` records. `--sarif` additionally emits
the SARIF 2.1.0 projection of Feature 011 findings (opt-in, FR-013).
- `0` on success; `2` on unreadable ledger. Read-only.

## Changed: `specops review [--json] [--soft] [--sarif]`
Pipeline becomes `reconcile → [selected profile suite] → working-tree → drift`
(replacing `lint`/`test`). Behavior otherwise unchanged: hard mode exits `1` on
REJECTED; `--soft --json` keeps exit `0` for the do-while loop; the map-digest drift
warning still appends. `--json` gate objects gain `disposition`, `commit_range`,
`affected_paths`, `evidence_id`. `--sarif` emits the findings projection alongside.
The verdict class (`pass|gate-rejection|infra-error`) and exit contract are unchanged.

## Changed: `specops status complete-task --auto`
Still harvests mechanically and writes the legacy `<CLASS>:<summary>` string; **also**
appends a `StructuredEvidence` record (`producer="auto"`) and sets the task's
`evidence_refs`. `--evidence <string>` path likewise records a structured record
parsed from the string. No CLI-signature change; additive behavior. Atomic via
Feature 006 `save(base_revision=…)`.

## Determinism & idempotency
- Every command: identical recorded ledger + config + branch ⇒ byte-identical output
  (FR-017/FR-018).
- `gate validate`/`list`/`report` and `review` (evaluation) are read-only.
- Re-recording identical evidence is idempotent (same cache-key id ⇒ reused, not
  duplicated).
</content>
