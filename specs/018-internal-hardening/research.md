# Phase 0 Research: Internal Hardening

**Date**: 2026-07-25 · **Input**: [spec.md](./spec.md)

No `NEEDS CLARIFICATION` markers existed in the Technical Context. Phase 0 therefore focused on (a) verifying the duplication inventories against the working tree at HEAD (`cb72e21`), so the plan operates on measured facts rather than review recollections, and (b) fixing the consolidation decisions the design phase depends on.

## Verified inventories (working tree, 2026-07-25)

### R1. Result-type duplication

- `trace.py:48` `_CLASS_FOR_STATUS` + `trace.py:93` `class TraceResult` and `handoff.py:63` `_CLASS_FOR_STATUS` + `handoff.py:95` `class HandoffResult` are structural copies (fields `command/status/human/extra`, `cls`/`exit_code` properties backed by the module-local map).
- The canonical pattern already exists: `outcome.py:57` `CommandResult._CLASS_MAP` (ClassVar), adopted by `contextmap.py:138` (`_CLASS_MAP = _CLASS_FOR_STATUS`) and by doctor/gateprofiles.

### R2. Emit duplication (cli.py)

Five per-family emit helpers: `_emit_context` (587), `_emit_trace` (725), `_emit_handoff` (790), `_emit_gate` (1001), `_emit_lane` (1096). (`_emit_sarif` at 971 is not part of the family — it writes a SARIF document, not the envelope.) Verified divergence: `_emit_lane` omits `output_version` and `status` from its JSON envelope and takes a `soft` flag; the other four are near-identical modulo their module's `OUTPUT_VERSION` constant.

### R3. Cross-module private call sites (production code)

**39 sites** across 23 distinct `module.attr` pairs (measured by AST-level grep over `src/specops/`, excluding dunders and same-module use):

| Consumer | Private target | Sites |
|---|---|---|
| handoff.py | `status._finalize` | 9 |
| lane.py | `ledger._ledger_path` | 5 |
| handoff.py | `trace._norm` | 3 |
| ingestion.py | `trace._norm` | 2 |
| lane.py | `trace._is_managed` | 2 |
| handoff.py | `status._get_feature_dir`, `status._load_for_write`, `status._validate_evidence`, `trace._FINDING_RE` | 1 each |
| trace.py | `status._finalize`, `status._get_feature_dir`, `status._load_for_write`, `contextmap._candidates_for_path`, `contextmap._RESOLVABLE` | 1 each |
| lane.py | `review._profile_gates` | 1 |
| cli.py | `review._existing_evidence` | 1 |
| review.py | `gateprofiles._affected_for` | 1 |
| gateprofiles.py | `contextmap._matches`, `contextmap._classify_pattern` | 1 each |
| doctor.py | `contextmap._CLASS_FOR_STATUS` | 1 |
| sarif.py | `handoff._canonical` | 1 |
| extension.py | `initializer._install_review` | 1 |
| migration.py | `initializer._scan_markers` | 1 |

### R4. Parallel ledger reads

- `status.py:533-538` (`cmd_show`) re-implements `yaml.safe_load` + mapping check + `LedgerParseError`; its counts (545-555) do not filter non-dict task entries, while `compact_status` (81-99) does — the verified show/report divergence on hand-edited ledgers.
- `reconcile.py:23-34` (`load_state`) re-implements existence + parse + mapping checks with its own error wording ("Cannot parse ledger") instead of `ledger.load_raw` (646-659).

### R5. Evidence grammar split

`_PART_RE`, `EVIDENCE_CLASSES`, `_validate_evidence` live in `status.py` (23-27, 155-167); `evidence.py` owns `parse_legacy_string` (consumed by `ledger.py:301`); `handoff.py:340` consumes `status._validate_evidence`. One grammar, two homes.

### R6. Finding record & line format

Base finding dict built in three places: `handoff.py:265-272` (authoring), `483-489` (import preview), `568-578` (import apply — already layering `imported`/`producer`/`reviewed_digest`). Line format: parse regex `trace.py:63` (`_FINDING_RE`), inverse renderer `handoff.py:804-820` (`render_revision_text`) — different modules, no shared round-trip test.

### R7. Test harness duplication

- `def _git(` defined **6×**: `tests/conftest.py:195`, `tests/unit/test_lane.py:19` (this copy lacks `check=True`), `tests/integration/test_context_consume_cli.py:35`, `test_preflight_cli.py:21`, `test_ledger_migration.py:17`, `test_lane_flow.py:31`.
- Ledger builders: `conftest.make_v1_ledger` (443), `conftest.ledger_in_review` (98, hard-coded v1 variant), `tests/unit/test_status.py:18` `_make_ledger` (local copy).
- 53 test files reference `subprocess` (CLI spawning + git setup); 27 files already use Typer's `CliRunner`, proving in-process invocation works in this suite.
- Test references to production privates: `s._validate_evidence` ×11, `ledger._finding_violations` ×8, `cm._is_catch_all` ×6, `review._run_profile_gate` ×5, `extension._merge_manifest` ×5, `s._sync_tasks` ×5, others smaller.

## Decisions

### D1. Result unification — extend the existing `outcome.CommandResult` pattern

**Decision**: make `TraceResult` and `HandoffResult` thin subclasses of `outcome.CommandResult` carrying only their `_CLASS_MAP`, exactly as `contextmap` does; delete the duplicated dataclass bodies and module-level maps-as-API.
**Rationale**: the pattern is already designed for this (`outcome.py:48` docstring), adopted by three families, and covered by existing tests; it is the smallest change that removes the copies.
**Alternatives considered**: a brand-new results module (rejected: invents a second canonical place; churn without benefit); keeping dataclasses and only deduplicating the maps (rejected: leaves the mirrored `cls`/`exit_code` properties in place).

### D2. Emit unification — one `_emit(result, json_out, *, output_version, soft=False)` in cli.py

**Decision**: single private helper in `cli.py` (it is CLI plumbing, consumed nowhere else — private is correct here); each command family passes its module's `OUTPUT_VERSION`. Lane adopts it, gaining `output_version` + `status` in JSON (the sanctioned FR-003 delta) and keeping its `soft` semantics via the keyword.
**Rationale**: the four non-lane bodies are already identical; the lane divergence is the acknowledged bug. Human-mode output paths are preserved byte-for-byte.
**Alternatives considered**: moving emit into `outcome.py` (rejected: `outcome` would import typer/json-printing concerns and stop being a pure taxonomy module).

### D3. Promotion policy — rename in place, no aliases, no new façade modules

**Decision**: each R3 target gets a public name in its current module (e.g. `status.load_for_write`, `status.finalize`, `status.get_feature_dir`, `ledger.ledger_path`, `trace.norm_path`, `trace.is_managed`, `contextmap.matches`, `contextmap.classify_pattern`, `contextmap.candidates_for_path`, `contextmap.RESOLVABLE`, `contextmap.CLASS_FOR_STATUS`, `review.profile_gates`, `review.existing_evidence`, `gateprofiles.affected_for`, `handoff.canonical_finding`, `initializer.install_review`, `initializer.scan_markers`), with a one-line documented contract at the definition site. Old underscore names are **removed**, not aliased; all consumers (production and tests) are updated in the same change.
**Rationale**: aliases would defeat SC-002 (zero cross-module private references) and preserve two names for one thing — the exact disease being treated. These names are internal contracts, not a supported external API (spec Assumptions).
**Alternatives considered**: a dedicated `internal/` package or `pathnorm.py` façade (rejected: moves create churn beyond renames and new import cycles to manage; in-place promotion achieves the contract with minimal diff). Exception: grammar/format owners that genuinely move — evidence grammar (D5) and finding line format (D6) — because co-location is their point.

### D4. Ledger reads — `ledger.load_raw` is the only loading path

**Decision**: `status.cmd_show` and `reconcile.load_state` delegate to `ledger.load_raw`; `cmd_show` renders counts from the `compact_status` snapshot, adopting the tolerant non-dict-filtering behavior (per spec Assumptions). Canonical `load_raw` diagnostics and exit codes win where wordings diverged.
**Rationale**: one authority, one error grammar (SC-004); the tolerant behavior matches what the machine report already does and what ledger validation reports separately.
**Alternatives considered**: preserving each command's legacy error wording behind the shared loader (rejected: keeps two error grammars alive, defeating SC-004; the wording differences are exactly the accidental divergence being removed — this is within FR-003's byte-identical scope only for *valid* inputs, and error-path wording converging on the canonical loader's messages is the intended unification).

### D5. Evidence grammar — `evidence.py` becomes sole owner

**Decision**: move `EVIDENCE_CLASSES`, the part regex, and validation into `evidence.py` (public `evidence.validate_string` alongside the existing `parse_legacy_string`); `status` and `handoff` import from there.
**Rationale**: `evidence.py` is the named owner of the format and already parses it; validation and parsing of one grammar belong side by side (FR-007).
**Alternatives considered**: promoting `status.validate_evidence` in place (rejected: leaves the grammar split across two modules, which is the R5 defect itself).

### D6. Finding factory + line format — new `findings.py` module

**Decision**: create `src/specops/findings.py` holding (a) `new_finding(...)` — the single base-shape factory with keyword extensions for import provenance, and (b) `parse_finding_line`/`format_finding_line` — the regex and its inverse f-string side by side, with a property-style round-trip test (FR-009). `trace`, `handoff`, and `sarif` consume it.
**Rationale**: three creation sites already diverging (R6) and a parse/render pair split across modules; a small dedicated module is the honest owner and avoids forcing `trace` ↔ `handoff` imports.
**Alternatives considered**: housing both in `handoff.py` (rejected: `trace` would import `handoff` for parsing, inverting the current dependency direction and risking cycles).

### D7. Test harness — conftest as the single source; in-process by default

**Decision**: export one `git(root, *args)` helper (with `check=True`) and the parametrized ledger builders from `tests/conftest.py`; delete the five local `_git` copies and `test_status._make_ledger`; re-express `ledger_in_review` via `make_v1_ledger`. Migrate subprocess-based CLI invocations to `CliRunner`, keeping an explicitly `@pytest.mark.subprocess`-marked smoke set (~one representative command per family) that still spawns the real binary for true exit codes, stream separation, and console encoding.
**Rationale**: the suite already proves both models work (27 CliRunner files); duplication is pure liability, and the unchecked `_git` copy hides setup failures (R7). The marked smoke set preserves the only coverage in-process invocation cannot give.
**Alternatives considered**: migrating 100% to in-process (rejected: loses real exit-code/stream/encoding coverage — the Windows-class regressions this project has actually shipped fixes for); migrating nothing (rejected: forfeits SC-005's wall-clock target).

### D8. Behavior-freeze verification — golden capture over fixture repos

**Decision**: before refactoring, record a golden capture: for each command family, run the representative scenarios from existing integration fixtures and store full stdout/stderr/exit-code triples (human and `--json` modes); after each consolidation story, re-run and diff. Expected diff: exactly the lane JSON envelope addition, nothing else. The capture harness lives with the feature's tests and runs against fixture repos only (No Self-Application).
**Rationale**: FR-003/SC-001 demand byte-level evidence, not reviewer judgment; the capture makes the freeze mechanically checkable per story rather than once at the end.
**Alternatives considered**: relying on the existing assertion suite alone (rejected: assertions sample fields, not full bytes; the lane divergence survived precisely because no test asserted envelope completeness).

## Risks

- **R-risk-1**: promoting names touches ~39 production sites + 60+ test references in one sweep; mitigated by doing it story-by-story with the full suite green between stories, and by D8's per-story capture diff.
- **R-risk-2**: `cmd_show`'s tolerant-filtering adoption and D4's error-wording convergence are deliberate micro-deltas on *invalid* inputs; both are documented here and bounded to corrupted/hand-edited ledgers (valid-input behavior stays byte-identical).
- **R-risk-3**: CliRunner migration can mask stream-separation bugs; mitigated by the mandatory subprocess smoke set (D7).
