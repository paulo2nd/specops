# Internal API Contracts: Hardening II

**Feature**: 019-api-state-robustness | **Date**: 2026-07-27

SpecOps' supported external surface remains the CLI (byte-identical — see
[cli-output note](#cli-output-contract) below). These contracts are the
maintainer-facing internal APIs this feature creates or changes; stability is governed
by changelog discipline, not semver (same posture as Feature 018).

## New

### `specops.records` (research D4)

TypedDict schemas: `LedgerDocument`, `TaskRecord`, `ReviewCycleRecord`,
`HandoffRecord`, `FindingRecord`, `EvidenceRecord`, `ContextProvenance`.
Stdlib-only module; no intra-package imports; importable from every layer without
cycles. Static contract only — never runtime validation.

### `gitops.parse_name_status(raw: str) -> list[tuple[str, str]]` (research D6)

The single `--name-status` parse loop. Blank lines skipped; `status = parts[0][:1]`;
`path = parts[-1]` (new path for rename lines).

### `gitops.name_status_diff(repo, start_sha, end_sha="HEAD", *, rename_aware: bool, cached: bool = False) -> list[tuple[str, str]]` (research D6)

The single `--name-status` invocation. `rename_aware=False` → `--no-renames`
(decomposed renames); `True` → `-M` (single `R` on new path). `cached=True` → staged
diff (`--cached`, no commit range). Raises `GitCommandError`; error-degradation policy
belongs to callers (`effective_diff_status` returns `[]`; lane suppresses).

### `ledger.HUMAN_COMMIT` / `ledger.is_human_commit(sha) -> bool` (research D7)

The single definition of the `(human)` ledger convention. Consumers: `reconcile`
(baseline warn + task commits), `ledger.validate_identity` (baseline), `handoff.
cmd_validate` (finding commits). `gitops` MUST NOT reference it.

### `fsutil.render_template(text: str, mapping: dict[str, str]) -> str` (research D8)

Replaces every `{{key}}`; raises `SpecopsError` naming any `{{...}}` residue left after
substitution (template drift → loud failure, FR-010). Extra mapping keys are ignored
(additive templates never break old code). Consumers: `status.cmd_init_spec`,
`status.synthesize_ledger_at_plan`, `lane.cmd_start`.

### `status._require_approved_cycle(cycles) -> None` (research D2)

The single Feature 006 DONE cycle gate: raises `SpecopsError` with today's exact
"no review cycles recorded" / "latest review cycle result is …" messages. Called by
both DONE branches of the transition flow. (Module-private: single-implementation
guarantee, not a cross-module API.)

### `handoff.LoadedLedger` + `HandoffLoadRefused` (research D5)

`_load_write(root) -> LoadedLedger`, raising `HandoffLoadRefused(status, human)` on
refusal; the `_handoff_command` decorator is the one exception→`HandoffResult`
conversion point. Post-condition: zero `isinstance(loaded, HandoffResult)` probes
(SC-004).

## Changed

### `gitops.is_ancestor(repo, sha)` — sentinel removed (research D7)

Now a pure git ancestry predicate: `(human)` returns `False` like any unresolvable
ref. Every caller passing ledger-sourced values filters via `ledger.is_human_commit`
first (audit table in research D7) — command-level behavior is unchanged.

### `gitops.effective_diff_status` — thin wrapper

Same name, signature, semantics (`--no-renames`, `[]` on `GitCommandError`); body
delegates to `name_status_diff(rename_aware=False)`. Consumers (`trace`, `safety`)
unchanged.

### `lane._parse_name_status` / `lane._diff_status`

`_parse_name_status` **deleted**; `_diff_status` composes
`gitops.name_status_diff(rename_aware=True, …)` keeping its `contextlib.suppress`
degrade and staged-diff union.

### `gateprofiles` — declarative field table (research D9)

Field names/types/defaults/defect-messages live in one module-level table consumed by
the lenient parser and the validator. `parse`, `validate`, `profiles_for`,
`resolve_suite` signatures and all outputs unchanged.

### `doctor._domain_cli_extension` / `_domain_legacy` — no `state_error` parameter (research D10)

The shared-read failure is converted by `_error_domain(domain, exc)` in `diagnose`;
no exception objects travel as arguments. Output byte-identical.

### `status` / `handoff` / `evidence` / `findings` signatures adopt `records.*` types (research D4)

`findings.new_finding -> FindingRecord`, `evidence.build_record -> EvidenceRecord`,
`handoff._iter_findings -> Iterator[tuple[ReviewCycleRecord, FindingRecord]]`, D3
sub-step signatures, etc. Runtime values and serialization unchanged.

## CLI output contract

Unchanged in full — human output, JSON envelopes, exit codes, ledger bytes. This
feature has **no** sanctioned delta (SC-001), which is the contract's entire content;
the existing test suite plus the quickstart capture procedure enforce it.
