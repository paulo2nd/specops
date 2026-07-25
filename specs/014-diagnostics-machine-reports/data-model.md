# Data Model: Diagnostics and Machine Reports

All types are **in-memory only** — the feature persists nothing. They exist to render a
deterministic human view and a versioned JSON document. Field names below are the JSON
keys (stable contract); the Python representation is `@dataclass`es in `src/specops/doctor.py`.

## Enums

### Severity

Ordered `ok < warning < blocking < execution-error`. Drives per-finding classification,
per-domain rollup, and the overall verdict.

| Value | Meaning | Contributes verdict → exit |
|---|---|---|
| `ok` | Domain healthy or a valid resting state (no active feature, no context map). | 0 |
| `warning` | Attention advised; does not block (e.g. migratable ledger, unavailable gate command, legacy artifacts, reconcile warnings). | 0 |
| `blocking` | Workflow cannot safely continue (schema too-new/unsupported, ledger↔git divergence, invalid context map, ambiguous identity, unverified blocking handoff findings). | 1 |
| `execution-error` | The diagnostic itself could not evaluate a domain (unreadable/corrupt input). | 2 |

### DiagnosticDomain (identifier enum — fixed, ordered)

Emitted in this exact order every run (determinism, D10):

1. `environment` — git repo present, Spec Kit repo present.
2. `cli_extension` — SpecOps CLI/extension presence & version compatibility.
3. `integration` — integration resolvability (defers to `specify check`).
4. `legacy_artifacts` — marker-injected legacy install detection.
5. `configuration` — `specops.json` parseability/validity.
6. `feature_identity` — active-feature resolution & identity divergence.
7. `ledger` — ledger schema classification + structural integrity.
8. `context_map` — context-map validity + digest drift.
9. `workflow_divergence` — ledger vs git tree / workflow-state (Principle II).
10. `gate_availability` — preflight profile config + command-on-PATH probe.

> Adding a new domain is a **compatible** change (D4); consumers must tolerate unknown
> domain ids.

### next_action_code (versioned with `output_version`)

Stable machine-actionable codes; the human text is separate. Initial v1 set (extensible —
consumers must tolerate unknown codes, D4):

`none` (only on `ok`), `initialize_repository`, `install_specops`, `upgrade_cli`,
`run_specify_check`, `run_specify_workflow_status`, `migrate_legacy_install`,
`fix_config`, `start_or_select_feature`, `resolve_identity_conflict`,
`run_status_migrate`, `ledger_schema_unsupported`, `fix_context_map`,
`refresh_context_provenance`, `reconcile_repository`, `install_gate_command`,
`fix_gate_profiles`, `verify_blocking_findings`, `repair_unreadable_input`.

## Entities

### Finding

A single diagnosed fact within a domain.

| Field (JSON) | Type | Notes |
|---|---|---|
| `severity` | Severity | Required. |
| `message` | string | Human-readable statement of the fact. Deterministic. |
| `next_action_code` | next_action_code | Required. `none` iff `severity == ok`. |
| `next_action` | string | Human next-action text. Empty iff `next_action_code == none`. |
| `id` | string | Stable domain-local key used for deterministic sort; not globally unique. |

Validation rules:
- `severity == ok` ⇔ `next_action_code == none` ⇔ `next_action == ""`.
- Every non-`ok` Finding MUST have a non-`none` code and non-empty text (FR-004).
- No field derives from wall-clock or environment order (FR-007).

### DomainResult

| Field (JSON) | Type | Notes |
|---|---|---|
| `domain` | DiagnosticDomain | Required; one of the fixed ids. |
| `severity` | Severity | Rollup = max severity of its findings (or `ok` if none problematic). |
| `findings` | Finding[] | Ordered by `id` then `message`. A healthy domain has exactly one `ok` finding. |

### DiagnosticReport (the `doctor` output)

| Field (JSON) | Type | Notes |
|---|---|---|
| `command` | string | `"doctor"`. |
| `output_version` | integer | `1`. |
| `outcome` | string | `ok` / `blocked` / `error` (from the outcome contract, `status_for`). |
| `class` | string | `pass` / `gate-rejection` / `infra-error`. |
| `verdict` | Severity | Overall = max severity across all domains' findings. |
| `domains` | DomainResult[] | All domains, in the fixed order above. |

Derivation:
- `verdict = max(severity over all findings)`; `ok` when everything is `ok`.
- `class`: `verdict ∈ {ok, warning}` → `pass`; `blocking` → `gate-rejection`;
  `execution-error` → `infra-error`. `outcome`/`class`/`exit_code` all flow from a
  `DoctorResult(outcome.CommandResult)` `_CLASS_MAP` (D9), so exit derivation is single-sourced.

### StatusReport (the `report` output)

Compact project/feature status (FR-014). Read from the active-feature ledger.

| Field (JSON) | Type | Notes |
|---|---|---|
| `command` | string | `"report"`. |
| `output_version` | integer | `1`. |
| `outcome` / `class` | string | `ok`/`pass` normally; `error`/`infra-error` if the ledger can't be read. |
| `active_feature` | string \| null | Feature id/dir; `null` when none active. |
| `branch` | string \| null | Ledger `branch`. |
| `phase` | string \| null | Ledger `current_phase` (one of `PHASES`). |
| `tasks` | object | `{pending, in_progress, done, orphaned, total}` integer counts. |
| `active_task` | string \| null | The single `IN_PROGRESS` non-orphaned task id, if any. |
| `review` | object | `{cycles: int, blocking_open: int}` from handoff read state. |
| `workflow_lane` | string | `data["workflow_lane"]` (default `"full"`). |

Rules: read-only; `null`/empty fields when no active feature (an `ok` state, not an error).

## State & transitions

None. Both commands are pure functions of repository state at invocation time. There is no
lifecycle, no persisted record, and no mutation (SC-003).

## Relationship to existing persisted formats

The model **reads** existing versioned formats (ledger v7, context-map schema 1,
gate-profiles `output_version` 1, handoff findings) but introduces **no** new persisted
schema. Its own `output_version` governs only the transient stdout document (D4). Backward
compatibility with prior ledger versions is delegated to `ledger.classify` (D6), not
re-implemented here.
