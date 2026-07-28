# Data Model: Frozen-Surface Inventory

This is the authoritative enumeration of every frozen surface's shape — the concrete
answer to "what does *frozen* mean" for each. Contract tests (Phase 2) assert against these
tables; the stability policy (`docs/stability.md`) publishes the adopter-facing summary.

**Legend** — `req` required · `opt` additive-optional (absence is valid) · a **frozen
field** may not be removed, renamed, or retyped without a MAJOR release + version bump; a
**new optional field** may be added at any time (additive, non-breaking).

**Stability class of all seven surfaces: FROZEN at 1.0** (spec FR-001/FR-003).

---

## Entity 1 — `specops.json` (project config)

- **Definition site**: `config.py` (`_DEFAULTS:12-17`, `load:28-43`, `merge_preserve:46-57`, `create_or_merge:78-98`, `lane_safety_overrides:60-75`).
- **Version field**: **none.** Stability mechanism = additive-only + **preserve-unknown** (`merge_preserve:54-56`).
- **Frozen baseline**: the four written keys + the optional `lane` block.

| Key | Type | req/opt | Notes |
|---|---|---|---|
| `test_command` | str | opt (default `"pytest"`) | |
| `lint_command` | str | opt (default `""`) | |
| `skills_dir` | str | opt (default `".specify/skills"`) | |
| `min_cli_version` | str | opt (default `"0.3.0"`) | CLI-compat gate, **not** a file-schema version |
| `lane` | mapping | opt | `lane.safety: dict[str, list[str]]` extra safety globs (F013); malformed ⇒ ignored |

**Frozen rules**: the four keys' names/types are frozen; `lane.safety` shape is frozen;
unknown keys MUST be preserved on write. No `schema_version` is introduced (would be a
second code delta — forbidden by FR-012).

---

## Entity 2 — `status.yaml` (ledger, schema **v7**)

- **Definition site**: `records.py` (TypedDicts) + `ledger.py` (`CURRENT_SCHEMA=7:35`, `OLDEST_SUPPORTED=1:36`).
- **Version field**: `schema_version: int` (**frozen baseline = 7**; absent ⇒ v1).
- **Authoritative baseline** = `records.LedgerDocument` / `CURRENT_SCHEMA`, **not** the template literal (`templates/status.yaml:1` still says `4` and migrates up — see research D7).

**Top-level (`LedgerDocument`, `records.py:141-162`, all additive-optional):**
`schema_version, revision, feature, branch, baseline, workflow_lane, created_at, updated_at,
current_phase, active_artifact, recovery, tasks[], review_cycles[], acknowledgements[],
evidence[], workflow, promoted_from_lane, lane_provenance`.

**Nested record shapes (frozen field sets):**

| Record | Required fields | Additive-optional fields |
|---|---|---|
| `TaskRecord` (`:34-49`) | `id, status, started_commit, commits[], evidence, completed_at` | `orphaned, context_provenance, evidence_refs[]` |
| `FindingRecord` (`:51-79`) | `id, severity, rule, file, line, action, expected_evidence, closure_criteria, state, task, commits[], evidence, fixed_at, verified_at` | `imported, producer, reviewed_digest, promotion` (v7), `dismiss_reason, evidence_id` |
| `ReviewCycleRecord` (`:89-97`) | *(all opt, `total=False`)* `round, started_at, completed_at, result` | `context_provenance, handoff` |
| `HandoffRecord` (`:81-86`) | *(all opt)* | `authorized_paths[], closed_at, findings[]` |
| `EvidenceRecord` (`:100-115`) | `id, producer, command, exit_code, timestamp, commit_range, affected_paths[], summary, superseded_by` | `artifact_digest` |
| `AcknowledgementRecord` (`:118-125`) | validation trio `path, task, reason` (`ledger.ACK_FIELDS:46`) | `map_digest, at` |
| `ContextProvenance` (`:25-31`) | *(all opt)* | `map, digest, context_ids[], output_version` |
| `RecoveryBlock` (`:128-134`) | | `active_task, last_commit, blockers[], last_consistent_revision, last_consistent_at, migrated_from_backup` |
| `WorkflowBlock` (`:137-138`) | | `skipped_steps[]` |

**Frozen rules**: the required-field set of each record is frozen (removal/rename/retype ⇒
MAJOR + schema bump + forward migration). New optional fields ⇒ additive. `schema_version`
values advance only via the ledger migration mechanism (`ledger.migrate_to_current`), each
bump covered by a migration test (FR-008). The `evidence` legacy string on tasks/findings
is retained for compatibility (not removed).

---

## Entity 3 — `lane.yaml` (lightweight-lane state, schema **v1**)

- **Definition site**: `lane.py` (`LANE_SCHEMA=1:27`, `STATES:28`, `load:94`, `validate:116-132`, `save:109-113`) + `templates/lane.yaml`.
- **Version fields**: `schema_version` (**frozen = 1**; `validate` rejects mismatch), `eligibility.criteria_version` (**1**).

| Key | Type | req/opt | Notes |
|---|---|---|---|
| `schema_version` | int | req | =1 |
| `lane_id, feature, branch, baseline, created_at, updated_at` | str | req | `updated_at` refreshed each save |
| `state` | str | req | OPEN / CLOSED / PROMOTED |
| `eligibility` | mapping | req | `confirmed:bool, criteria_version:int, answers[]{key,confirmed}, bundled:bool, bundle_note:str?` |
| `decisions` | list | req | attestation entries `{seq, kind, category, signal, answer, at}` |
| `closure` | mapping\|null | req key | null unless CLOSED (INV-2); `{at, commit_range, gate_evidence{verdict,gates[]}, retrospective{...}}` |
| `promotion` | mapping\|null | req key | null unless PROMOTED (INV-2); `{at, reason, synthesized_ledger, imported_commits[], resumed_phase}` |

**Frozen rules**: top-level key set + the `eligibility`/`closure`/`promotion` sub-shapes are
frozen; `state` enum is frozen; the null-until-transition invariant (INV-2) is frozen.

---

## Entity 4 — Gate-profile file (`.specify/specops/gate-profiles.yaml`)

- **Definition site**: `gateprofiles.py` (`PROFILES_RELPATH:29`, `OUTPUT_VERSION=1:30`, `parse:235`, `validate:407`, `_PROFILE_FIELDS:83`, `_APPLIES_FIELDS:72`).
- **Version field**: `output_version: int` (**frozen = 1**; validated `_validate_output_version:391`). *This is a persisted-format version, distinct from the CLI envelope version (Entity 6).*

| Top-level | Type | req/opt |
|---|---|---|
| `output_version` | int (==1) | opt (absent ⇒ current) |
| `profiles` | list of profile mappings | opt (empty/absent ⇒ synthesized `lint`→`test` default) |

**Per-profile fields** (`GateProfile`): `name` (req, unique) · `command` (req, non-empty) ·
`timeout` (opt int>0, default 600) · `required` (opt bool, default `True` — the failure-
semantics knob) · `applies` (opt predicate). **Applicability predicate** keys: `always:bool`,
`contexts:list`, `paths:list[glob]`, `risk:mapping`, `gate_ref:str`.

**Frozen rules**: profile field names/types/defaults, the `applies` predicate key set, and
`output_version==1` are frozen. Existing contract doc: `specs/012-…/contracts/gate-profiles.config.md`.

---

## Entity 5 — Findings-input contract (external review ingestion, **v1**)

- **Definition site**: `ingestion.py` (`INPUT_CONTRACT_VERSION=1:23`, `parse_contract:119`, `_norm_contract_finding:157`, `parse_sarif:195`) + schema `specs/015-…/contracts/findings-input.schema.json` + SARIF output `sarif.py` (`SARIF_VERSION="2.1.0":17`).
- **Version field**: `contract_version: int` (**frozen = 1**; `const:1` in schema).

| Top-level | Type | req/opt |
|---|---|---|
| `contract_version` | int (==1) | req |
| `producer` | object `{name(req), version?}` | req |
| `reviewed_commit` | str | opt (default HEAD-at-import) |
| `findings` | array (empty = supported no-op) | req |

**Per-finding**: `rule` (req) · `file` (req, repo-relative) · `action` (req) · `line` (opt int≥1) ·
`severity` (opt, **informational only** — always imported advisory) · `producer`/`reviewed_commit`
(opt per-finding overrides).

**Frozen rules**: `contract_version==1`, the top-level and per-finding required fields, the
"always advisory on import" semantics, and the identity key `(producer, rule, file, line,
action)` are frozen. SARIF input adapter checks `version=="2.1.0"`. Existing contract docs:
`specs/015-…/contracts/{findings-input.schema.json,ingestion-cli.md}`, `specs/012-…/contracts/sarif-output.md`.

---

## Entity 6 — JSON output envelope (base command-result, **output_version → 1 after this feature**)

- **Definition site**: `outcome.py` (`render:78-93`; status/class constants `:30-40`; exit map `:40`).
- **Version field**: **NEW** `output_version: int` — added by this feature (`outcome.OUTPUT_VERSION=1`), always emitted by `render()`. This is the feature's single sanctioned code delta (FR-009/FR-012).

**Frozen base envelope keys (every `--json` output):**

| Key | Value domain | Notes |
|---|---|---|
| `command` | str | the command name |
| `outcome` | `ok` \| `blocked` \| `error` | derived from status (`_STATUS_FOR_CLASS`) |
| `class` | `pass` \| `gate-rejection` \| `infra-error` | the outcome class |
| `output_version` | int (==1) | **NEW/frozen** — single-sourced envelope version |

Plus **documented per-command extension keys** carried in `extra` (dropped when `None`) —
e.g. `warnings` (reconcile), `verdict`/`gates` (preflight), `paths`/`counts` (trace classify),
`package` (context resolve), `imported`/`ids` (handoff import), `profiles`/`selection`
(gate list). These are documented per command; the contract test locks the four base keys
**without** forbidding documented extensions (FR-004/FR-007).

**Frozen rules**: the four base keys, the `outcome` and `class` value enums, and their
status→class→exit derivation are frozen. Per-command extension keys are additive.

**`output_version` is two independent axes, not one global value** (FR-009/SC-010):
- The **base** `output_version` (= `outcome.OUTPUT_VERSION` = `1`) versions the thin envelope
  and is the default `render()` stamps for families with no richer payload (`consistency`,
  `reconcile`, error paths). It increments only when the base envelope shape changes.
- Command families with a richer payload (context/trace/handoff/gate/lane/doctor) carry their
  **own** `output_version` (each `1` at 1.0), **retained unchanged** by this feature; each
  bumps independently per the versioning policy. `render()` emits a caller-supplied version
  verbatim and never overrides it.

*Not part of this envelope* (separate frozen persisted-format versions): gate-profile file
`output_version` (Entity 4), context-map `schema_version` (Entity 8), and ledger
`context_provenance.output_version` (Entity 2). **Known pre-1.0 coupling**:
`gateprofiles.OUTPUT_VERSION` currently serves both the gate-profile *file* and the `gate`
command output; `contextmap.OUTPUT_VERSION` both the context command output and the ledger
provenance record — pre-existing conflations left intact by the freeze, to be split post-1.0
if either side needs an independent bump.

---

## Entity 7 — Exit-code contract (**0 / 1 / 2**)

- **Definition site**: `outcome.py:25-27,40,73-75`; `errors.py`.

| Code | Constant | Meaning | Maps from |
|---|---|---|---|
| `0` | `EXIT_OK` | success | class `pass` |
| `1` | `EXIT_BLOCKED` | blocking gate result / review `REJECTED` | class `gate-rejection`; `SpecopsError`, `StaleLedgerError` |
| `2` | `EXIT_ERROR` | infrastructure / data / usage error | class `infra-error`; `LedgerParseError` |

**Frozen rules**: the three codes and their meanings are frozen; no command may emit a code
outside `{0,1,2}` (all funnel through `outcome.exit_for`). **Governance dependency**:
constitution Principle VI (currently names only `0`/`1`) is amended to document code `2`
(FR-014) so principle and contract agree.

---

## FR-003 observable-surface sweep result (T004, 2026-07-28)

The sweep over the CLI/persisted surfaces found **two additional adopter-facing surfaces**
beyond the roadmap's named seven. Per FR-003 both default to **FROZEN**; total frozen
surfaces = **9**. No observable surface is left unclassified (SC-001).

### Entity 8 — Context-map file (`.specify/specops/context-map.yaml`, schema **v1**)

- **Definition site**: `contextmap.py` (`MAP_RELPATH:33`, `CURRENT_SCHEMA=1:36`, `classify:164`, `validate:477`).
- **Version field**: `schema_version: int` (**frozen = 1**; `validate` rejects unsupported).
- **Why frozen**: a user-authored persisted format adopters bind to (contexts, ownership,
  read-sets, gates, dependencies). Same freeze rules as the ledger: required-field set frozen;
  new optional fields additive; schema bump requires a migration + test.
- **Frozen baseline** = `contextmap.CURRENT_SCHEMA==1`. Contract test: `test_frozen_contextmap.py`.

### Entity 9 — SARIF output (`--sarif`, **2.1.0**)

- **Definition site**: `sarif.py` (`SARIF_VERSION="2.1.0":17`, `project:23`, `from_ledger:59`).
- **Version field**: `version` (**frozen = "2.1.0"**, the external SARIF standard).
- **Why frozen**: an opt-in output format adopters consume in CI. Additive = new optional
  SARIF properties permitted by the standard; breaking = a SARIF version change or a change to
  the `{blocking→error, advisory→warning}` level mapping (`sarif.py:20`).
- **Frozen baseline** = `sarif.SARIF_VERSION=="2.1.0"`. Contract test: `test_frozen_sarif.py`.

## Cross-cutting: version-field map (what "bump" means where)

| Surface | Version field | Baseline | Bump mechanism |
|---|---|---|---|
| `specops.json` | *(none)* | — | additive-only + preserve-unknown |
| `status.yaml` | `schema_version` | 7 | `ledger.migrate_to_current` + migration test |
| `lane.yaml` | `schema_version` (+`criteria_version`) | 1 (1) | lane load/validate; migration test if bumped |
| gate-profile file | `output_version` | 1 | validate against const; migration/compat note |
| findings-input | `contract_version` | 1 | schema `const` bump + adapter update |
| JSON envelope | `output_version` (**new**) | 1 | single-sourced `outcome.OUTPUT_VERSION` |
| exit codes | *(the set is the contract)* | {0,1,2} | MAJOR only; principle VI kept in sync |
