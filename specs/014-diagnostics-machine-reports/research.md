# Research: Diagnostics and Machine Reports

All decisions below are grounded in an empirical read of the current worktree
(`file:line` references verified during planning). No NEEDS CLARIFICATION remains.

## D1 — Defer to native `specify` by *pointing*, not *wrapping* (FR-011 × FR-007)

**Decision**: `specops doctor` MUST NOT execute `specify check` or
`specify workflow status` (or any subprocess of the host engine). For engine and
integration health it reports what it can determine from **local** SpecOps/Spec Kit
artifacts (manifest, integration manifests, `has_speckit`) and emits a
`next_action_code` (`run_specify_check` / `run_specify_workflow_status`) directing the
user to the authoritative native command.

**Rationale**:
- The codebase has **zero** subprocess invocation of `specify` (grep over
  `src/specops/*.py`); the only mentions are docstrings describing the host context
  (`outcome.py:3-16`, `status.py:82,464`). There is no helper to reuse and adding one
  would couple doctor to the host binary being on PATH.
- Wrapping native stdout would embed **non-deterministic, version/time-varying** output
  into doctor's payload, directly violating FR-007/SC-005 (byte-identical output on
  unchanged inputs). Determinism is a hard requirement; "pointing" preserves it.
- "Complements … deferring to the native commands for engine and integration health"
  (roadmap non-goal) is satisfied by deference-as-reference: doctor never re-derives
  engine health, it names the native command as the next action.

**Alternatives considered**:
- *Shell out and embed results*: rejected — breaks determinism, adds a hard `specify`
  runtime coupling, and risks re-checking what the native command owns (Rule 8).
- *Parse native machine output if present*: rejected for v1 — same determinism/coupling
  risk; can be revisited if a stable machine contract for those commands is guaranteed.

## D2 — Report shape: every domain always yields a result; findings nest under domains (CHK006/CHK046)

**Decision**: The report always contains **one entry per diagnostic domain** (FR-003
lists them), each carrying its own severity and zero-or-more findings. An `ok` domain is
present with `severity: ok` and no problem findings. Consumers get the full domain set
every run (SC-002 = 100% domain coverage), and "report every finding in a single run"
(FR-013) is satisfied within that structure. This removes the apparent tension the
checklist flagged between "a result for each domain" and "surface problems."

**Rationale**: A stable, fully-populated domain list is far easier for CI to consume
(fixed keys) and makes "which domains were checked" auditable. Determinism is simpler
when the top-level shape does not vary with findings.

**Alternatives considered**: *Only emit non-`ok` findings* — rejected: makes "was this
domain checked or merely clean?" ambiguous and complicates SC-002 verification.

## D3 — Human output by default; `--json` for machine (CHK004)

**Decision**: Both `doctor` and `report` print a concise human-readable rendering by
default and a stable versioned JSON document under `--json`, matching every existing
read-only command (`trace report`, `gate report`, `handoff report`). Human text goes to
stdout on success and stderr when the outcome class is not PASS (the `_emit_*` idiom,
`cli.py:674-685`).

**Rationale**: Consistency with the established CLI contract; US1 (human) and US2
(machine) are both first-class.

## D4 — Output schema versioning & forward-compatibility (CHK025/CHK027/CHK028)

**Decision**:
- The machine document carries `output_version: 1` (integer), following the existing
  `OUTPUT_VERSION` convention (`trace`/`gateprofiles`/`contextmap` all `= 1`).
- **Compatible (no version bump)**: adding a new diagnostic domain, adding a new
  `next_action_code` value, adding a new optional field. Consumers MUST tolerate unknown
  domains and unknown `next_action_code` values (documented in the contract).
- **Breaking (bump `output_version`)**: removing/renaming a field, changing a field's
  type, or changing the meaning of an existing severity/verdict.
- The `next_action_code` enum is versioned **with** the output schema (same
  `output_version`); its documented values live in `contracts/doctor-output.schema.json`.

**Rationale**: Mirrors how downstream features already treat `OUTPUT_VERSION`; gives CI a
single integer to gate on while allowing additive growth (new domains land as SpecOps
grows) without churn.

## D5 — Gate-availability probe: read-only `shutil.which` over the first shell token

**Decision**: For each gate in `gateprofiles.profiles_for(root)` (returns the ordered
suite incl. the raw `command` shell string, never raises, never executes —
`gateprofiles.py:229`), extract the executable with `shlex.split(command)[0]` and resolve
it with `shutil.which`. Unresolvable ⇒ a gate-availability `warning` naming the profile
and the missing executable. Additionally run `gateprofiles.validate(root)` for config
defects.

**Rationale**: No `which`/PATH helper exists in the codebase (confirmed), so this is new
but stdlib-only and strictly read-only (resolution locates, never runs — FR-015a). It
catches the real "tool not installed" failure before a preflight run dies mid-gate.

**Alternatives considered**: *Static config-only validation* — rejected: misses the
stated failure mode (unavailable command). *Execute `--version` probes* — rejected:
violates the no-execution guarantee and determinism.

## D6 — Ledger schema health via `classify`, read-only for every schema (CHK029/CHK030)

**Decision**: Load with `ledger.load_raw(feature_dir)` (never mutates disk;
`ledger.py:646`) and classify with `ledger.classify(data)` (`ledger.py:130`):
- `current` (== 7) → `ok`.
- `migratable` (1..6, supported prior) → `warning` with `next_action_code:
  run_status_migrate` and `ledger.diagnostic_line(...)` text. Backward read compatibility
  is preserved (Feature 006); a supported prior version is not a failure.
- `too_new` (> `CURRENT_SCHEMA`) or `unsupported` (< floor / non-int) → `blocking`, using
  `ledger.refusal_message(...)`.
- Parse failure: `LedgerParseError` (corrupt YAML/structure, `errors.py:15`, exit-class
  2) → `execution-error`; missing ledger (`SpecopsError`, feature exists but no
  `status.yaml`) → reported per the active-feature state (D8), not a crash.

Additional integrity beyond version: `ledger.validate_invariants(data)` and
`ledger.finding_structural_defects(data)` (both pure) feed the ledger-integrity domain.

**Rationale**: `CURRENT_SCHEMA = 7` (verified — the spec/checklist "v6" was stale; note
recorded). `load_raw` does not raise on too-new/unsupported (only the *write* path
refuses), so doctor can inspect any schema read-only and classify it — exactly the
behavior FR-015/edge-cases require.

## D7 — Workflow/ledger divergence via reconcile, read-only (CHK011/CHK022)

**Decision**: Reuse `reconcile.run(root) -> (warnings, violations)` and
`reconcile.divergence(root) -> str | None` (`reconcile.py:106,117`), both pure reads that
apply the Principle II `is_ancestor` check per recorded commit and the
identity/workflow-state checks. Map: any **violation** ⇒ `blocking`; **warnings** ⇒
`warning`; `divergence(...)` non-None ⇒ `blocking` naming the diverged dimension.
Ambiguous/loaded identity failures surface here and in the identity domain as `blocking`
(fail-closed, FR-012).

**Rationale**: Divergence is exactly what `reconcile` already computes; doctor must not
re-implement it (Rule 8) — it consumes the tuples and classifies.

## D8 — "No active feature" and "missing context map" are `ok` (Clarifications; FR-009/FR-010)

**Decision**: `speckit.resolve_feature_dir(root)` returning `None` ⇒ a single `ok`
finding in the feature-identity domain with `next_action_code: start_or_select_feature`;
the overall verdict is unaffected. A missing context map ⇒ `contextmap.validate` returns
`S_NO_MAP` (PASS, `contextmap.py:462`) ⇒ `ok`. Both are valid resting states, never
warnings or errors.

**Rationale**: Directly encodes the two clarifications; aligns the two "absent-but-fine"
states consistently (CHK015).

## D9 — Overall verdict, severity ordering, and exit codes (FR-005/FR-008; CHK014/CHK032)

**Decision**: Severity order `ok < warning < blocking < execution-error`. Overall verdict
= max severity across all findings. Verdict → outcome class → exit code, via the existing
contract (`outcome.py:25-40`):
- `ok` / `warning` → `PASS` → exit `0`.
- `blocking` → `GATE_REJECTION` → exit `1`.
- `execution-error` → `INFRA_ERROR` → exit `2`.

Implemented as a `DoctorResult(outcome.CommandResult)` subclass whose `_CLASS_MAP` maps a
module-local status (`S_OK`/`S_WARNING`/`S_BLOCKING`/`S_EXECUTION_ERROR`) to the outcome
class, so exit derivation lives in exactly one place (the established subclass idiom used
by `gateprofiles.GateCommandResult` / `contextmap.CommandResult`).

**Rationale**: Reuses the Feature 007 outcome contract verbatim (FR-008 requirement, not
aspiration); the three CI-relevant classes stay mutually distinguishable by exit code
(SC-004). `warning` deliberately does not fail CI (recorded spec assumption).

## D10 — Determinism discipline (FR-007/SC-005; CHK008/CHK033)

**Decision**: The JSON payload contains **no** wall-clock timestamp, no absolute host
paths, no native-command output, and no set/dict iteration whose order is unstable.
Domains emit in a fixed declared order; findings within a domain sort by a stable key
(domain-local id, then message). All reused readers are already timestamp-free
(`map_digest` is content-only; `classify`/`diagnostic_line` are pure). Determinism is
covered by a `snapshot_tree` + byte-identical test (the `test_gate_readonly_determinism`
pattern).

**Rationale**: Byte-identical output is a hard requirement; the discipline is
enforceable and testable.

## D11 — Compact status report reuse (FR-014; CHK003)

**Decision**: `specops report` reuses the read path behind `status.cmd_show`
(`status.py:459`, read-only) — feature/branch/phase, task tallies
(pending/in_progress/done/orphaned/total), review-cycle count, workflow lane
(`data["workflow_lane"]`), and handoff state (`handoff._load_read` +
`blocking_approval_check`). The counting recipe is factored into a shared read-only
helper so `report` (human + `--json`) and `status show` do not duplicate it.

**Rationale**: Avoids re-deriving state that `status show` already computes; keeps a
single source of truth for the tallies.

## Summary of reused symbols (all pure reads, verified)

| Domain | Reused symbol | Path |
|---|---|---|
| Active feature identity | `speckit.resolve_feature_dir` | speckit.py:25 |
| CLI/extension version | `compat.installed_version`, `compat.check` | compat.py:40,75 |
| Install state / legacy | `migration.detect_state` | migration.py:49 |
| Manifest drift | `extension.read_manifest`, `semantically_equal` | extension.py:87,172 |
| Integration resolvability | `speckit.resolve_prompt_targets`, `host_prompt_paths` | speckit.py:161,346 |
| Config validity | `config.load` | config.py:28 |
| Ledger schema/integrity | `ledger.load_raw`, `classify`, `diagnostic_line`, `refusal_message`, `validate_invariants`, `finding_structural_defects` | ledger.py:646,130,146,164,343,414 |
| Identity divergence | `ledger.validate_identity` | ledger.py:590 |
| Workflow/ledger divergence | `reconcile.run`, `reconcile.divergence` | reconcile.py:106,117 |
| Context-map health | `contextmap.validate`, `map_digest`; `review.digest_drift_warning` | contextmap.py:459,773; review.py:324 |
| Gate availability | `gateprofiles.profiles_for`, `validate` + `shutil.which`/`shlex.split` | gateprofiles.py:229,356 |
| Review/handoff health | `handoff.cmd_validate`, `blocking_approval_check` | handoff.py:688,182 |
| Lane health | `lane.exists`, `lane.load` | lane.py:80 |
| Git reads | `gitops.find_repo`, `is_git_repo`, `is_ancestor` | gitops.py:10,18,43 |
| Output/exit contract | `outcome.render`, `exit_for`, `CommandResult` | outcome.py:78,73,43 |
