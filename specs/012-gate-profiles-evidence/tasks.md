---

description: "Task list for Gate Profiles and Structured Evidence (Feature 012)"
---

# Tasks: Gate Profiles and Structured Evidence

**Input**: Design documents from `/specs/012-gate-profiles-evidence/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Mandatory per Constitution (Development Workflow & Quality Gates — task
gate: no task is complete without passing automated tests). Each user story includes
unit + integration + error-path coverage against fixtures/sample repos (never by
running `specops` against this repository — No Self-Application).

**SC tagging**: Per roadmap Rule (Tasks & analysis), every task carries one or more
`[SC-xxx]` tags mapping to `spec.md` Success Criteria (SC-001…SC-010).

**Organization**: Grouped by user story (US1–US4) for independent implementation and
testing. Story priorities from spec.md: US1 = P1 (MVP), US2 = P2, US3 = P2, US4 = P3.

## Format: `[ID] [P?] [Story] Description [SC-xxx]`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 / US4 (Setup, Foundational, Polish carry no story label)
- Exact file paths are included in every task.

## Path Conventions

Single project (Constitution "Structure"): modules under `src/specops/`, tests under
`tests/` (`tests/unit`, `tests/integration`, `tests/fixtures`). New modules:
`gateprofiles.py`, `evidence.py`, `sarif.py`. Modified: `review.py`, `shell.py`,
`ledger.py`, `status.py`, `cli.py`, `handoff.py`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new module surfaces and shared test scaffolding.

- [X] T001 Create stub modules `src/specops/gateprofiles.py`, `src/specops/evidence.py`, `src/specops/sarif.py` (module docstrings + `__all__`, no logic) so imports resolve across stories [SC-001] [SC-005] [SC-009]
- [X] T002 [P] Add shared test scaffolding in `tests/fixtures/` and `tests/conftest.py`: a sample-repo builder and a context-map fixture whose contexts carry `gates` + free-form `risk` (used by US1/US3) [SC-001]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared surfaces every story composes. **No user story starts until these
are complete.**

- [X] T003 Create the `gate_app` Typer group and register it in `src/specops/cli.py` via `app.add_typer(gate_app, name="gate")` (no subcommands yet — commands land in their stories) [SC-008]
- [X] T004 [P] Add a read-only/determinism test helper in `tests/conftest.py` (before/after ledger+config byte-compare + byte-identical-output assertion) reused by every story [SC-008]

**Checkpoint**: New module files import; `specops gate` group exists; shared helpers ready.

---

## Phase 3: User Story 1 - Define and deterministically select ordered gate profiles (Priority: P1) 🎯 MVP

**Goal**: A versioned `.specify/specops/gate-profiles.yaml` declaring an ordered gate
set; deterministic, fully-explained selection from config + context impact + changed
paths; a synthesized default profile when no config exists; read-only `gate
list`/`validate`.

**Independent Test**: From a profile fixture with mixed predicates and a known changed
set, `specops gate list --json` returns the exact selected set + order + per-gate
reason, byte-identical across runs; with no config, the default profile is synthesized
and selection still runs; seeded config defects each fail `validate` with a distinct
diagnostic. No evidence/ledger work required — US1 stands alone.

### Tests for User Story 1 (mandatory) ⚠️

- [X] T005 [P] [US1] Unit tests for profile config parse + `validate` — duplicate name, empty command, non-positive/non-int timeout, unparseable predicate, dangling `contexts`/`gate_ref`, unsafe `paths` pattern, unsupported `output_version`, each a distinct diagnostic; a well-formed config passes with no false positives (ordering-cycle is **not** a v1 defect — FR-014) — in `tests/unit/test_gateprofiles_validate.py` [SC-006]
- [X] T006 [P] [US1] Unit tests for deterministic `select` — `always`/`contexts`/`paths`/`risk` named-key/`gate_ref` implicit-match branches, machine-readable reasons, byte-identical selection across runs, and the no-map/no-baseline degrade (only `always`+`paths` match) — in `tests/unit/test_gateprofiles_select.py` [SC-001]
- [X] T007 [P] [US1] Integration test: default-profile synthesis from `specops.json` (`test_command` always/required, optional `lint`) when no config file, and `gate list`/`validate` exit `0` in the no-config state — in `tests/integration/test_gate_default_profile.py` [SC-006]

### Implementation for User Story 1

- [X] T008 [US1] Implement `profiles_path`, the `GateProfile`/`ApplicabilityPredicate` dataclasses, and the YAML parser (mirroring `contextmap` idioms; `output_version` gate; default `timeout=600`, default `required=true`) in `src/specops/gateprofiles.py` [SC-001] [SC-006]
- [X] T009 [US1] Implement `validate(root)` returning a `CommandResult`-style report with a distinct diagnostic per defect; path patterns validated syntactically/safety-only (reuse `contextmap._classify_pattern`, no filesystem access) in `src/specops/gateprofiles.py` [SC-006]
- [X] T010 [US1] Implement deterministic `select(root)` — compute the effective diff via `gitops.name_only_diff(baseline, HEAD)`, call `contextmap.cmd_impact(paths=…)` for affected contexts (`gates`+`risk`), evaluate each predicate, and emit a `SelectedGate{selected, reason}` per declared gate with the canonical sort order (FR-021) in `src/specops/gateprofiles.py` [SC-001]
- [X] T011 [US1] Implement default-profile synthesis (absent config ⇒ `lint`→`test` from `specops.json`, empty `test_command` ⇒ that gate SKIPPED/unavailable as today) in `src/specops/gateprofiles.py` [SC-006]
- [X] T012 [US1] Wire read-only `specops gate list [--json]` and `specops gate validate [--json]` commands into `gate_app` in `src/specops/cli.py` (exit `0`/`1`/`2` per contract; `--json` stamps `output_version`) [SC-001] [SC-006] [SC-008]

**Checkpoint**: US1 fully functional and independently testable — profiles select and validate deterministically; default profile degrades safely.

---

## Phase 4: User Story 2 - Record structured, migratable evidence (Priority: P2)

**Goal**: A versioned structured evidence record (cache-key-derived id, producer,
command, exit code, timestamp, commit range, affected paths, summary, optional local
digest) in the ledger; a zero-loss v5→v6 forward migration of legacy
`<CLASS>:<summary>` strings; both `complete-task --auto` and Feature 011 finding
`fix`/`verify` link a structured evidence record.

**Independent Test**: Over a v5-ledger fixture with legacy evidence strings, run the
migration → `schema_version:6`, every string becomes a structured record (class+summary
preserved; malformed strings preserved verbatim), `task.evidence` retained,
`evidence_refs` set, absent list → explicit `[]`, idempotent, pre-migration ledger
still readable; a produced record round-trips its id byte-for-byte; a finding marked
`FIXED` carries a resolvable `evidence_id`.

### Tests for User Story 2 (mandatory) ⚠️

- [ ] T013 [P] [US2] Unit tests for `StructuredEvidence`: cache-key id determinism (identical key ⇒ identical `EV-<hex12>`; any key field change ⇒ new id), local `sha256` artifact digest, and volatile fields excluded from the id — in `tests/unit/test_evidence_record.py` [SC-005]
- [ ] T014 [P] [US2] Migration test: v5→v6 `backfill_evidence` — zero-loss string→record, idempotent re-run, absent list ⇒ explicit `[]`, pre-v6 ledger readable with absent fields reported (not defects), a **malformed** legacy string preserved verbatim as an opaque record without crashing, and an interrupted migration leaving the prior valid ledger readable — in `tests/unit/test_ledger_v6_migration.py` [SC-007]
- [ ] T015 [P] [US2] Integration test: `complete-task --auto` and `--evidence` append a structured record and set `task.evidence_refs` alongside the retained legacy string; atomic via `save(base_revision=…)` — in `tests/integration/test_complete_task_evidence.py` [SC-005] [SC-007]
- [ ] T016 [P] [US2] Integration test: `handoff finding fix` records a `StructuredEvidence` record and sets `finding.evidence_id` (the actual evidence linked at FIXED, Feature 011 FR-005), and `handoff finding verify` resolves that structured evidence — without redefining the Feature 011 finding lifecycle — in `tests/integration/test_handoff_finding_evidence.py` [SC-004] [SC-005]

### Implementation for User Story 2

- [ ] T017 [US2] Implement `StructuredEvidence`, the cache-key (`producer/command/commit_range/affected_paths/context_map_digest`) → `EV-sha256[:12]` id, and the local-artifact `sha256` digest in `src/specops/evidence.py` [SC-005]
- [ ] T018 [US2] Bump `ledger.CURRENT_SCHEMA` 5→6 and add `backfill_evidence(data)` (parse legacy strings zero-loss, idempotent, explicit `[]`, malformed-string-safe verbatim preservation) called from `migrate_to_current` after the existing backfills, in `src/specops/ledger.py` [SC-007]
- [ ] T019 [US2] Add v6 validators for the top-level `evidence[]` list and `evidence_refs`/`evidence_id` references (well-formedness; dangling ref reported, not crashed) in `src/specops/ledger.py` [SC-005] [SC-007]
- [ ] T020 [US2] Wire `complete-task --auto/--evidence` to build + append a structured record (`producer="auto"`) and set `evidence_refs`, retaining the legacy string, in `src/specops/status.py` [SC-005]
- [ ] T021 [US2] Wire Feature 011 `handoff finding fix` (and the `verify` precondition check) to append a `StructuredEvidence` record and set `finding.evidence_id`, composing `evidence.py` and **not** altering the finding lifecycle, in `src/specops/handoff.py` [SC-004] [SC-005]

**Checkpoint**: US2 independently testable — task **and** finding evidence are structured, id-addressable, and migrated with zero loss; v5 ledgers remain readable.

---

## Phase 5: User Story 3 - Classify gate outcomes and make the verdict fully provenanced (Priority: P2)

**Goal**: The fixed outcome taxonomy (`required|optional|skipped|cached|failed|
unavailable`), safe caching keyed on the full cache tuple, per-gate timeouts, the
profile suite integrated into `specops review` (replacing `lint`/`test`), and a
fully-provenanced verdict.

**Independent Test**: Over seeded selection+evidence fixtures, each gate carries exactly
one taxonomy value; a matching cache key ⇒ `cached` (no re-run), any of the four
invalidation vectors ⇒ fresh run + new superseding record; a missing tool ⇒
`unavailable` (≠ `failed`); a timeout ⇒ `failed`; a required `failed`/`unavailable`
blocks the verdict while an optional failure never blocks; the verdict names each
gate's disposition, reason, covered commit-range/paths, and supporting `evidence_id`.

**Depends on**: US1 (selection) + US2 (evidence records + v6 schema).

### Tests for User Story 3 (mandatory) ⚠️

- [ ] T022 [P] [US3] Unit test: outcome-taxonomy mapping to blocking status (required-pass→PASS, cached→PASS, optional-fail non-blocking, required failed/unavailable→FAIL), and `unavailable ≠ failed` — in `tests/unit/test_gate_outcomes.py` [SC-002]
- [ ] T023 [P] [US3] Unit test: `shell.run_client_command` timeout — TimeoutExpired ⇒ `failed`/`timeout` with a deterministic recorded outcome carrying the configured limit, not elapsed wall-clock — in `tests/unit/test_shell_timeout.py` [SC-002]
- [ ] T024 [P] [US3] Integration test: caching — a matching cache key reuses the record without executing the command; each of command / inputs / context-map digest / commit changing forces a fresh run and sets the prior record's `superseded_by` — in `tests/integration/test_gate_cache.py` [SC-003]
- [ ] T025 [P] [US3] Integration test: fully-provenanced verdict via `specops review --json` — every gate shows disposition + reason + commit_range + affected_paths + `evidence_id`; a required failed/unavailable blocks (exit `1`), an optional failure does not (0% false block) — in `tests/integration/test_review_verdict_provenance.py` [SC-004] [SC-007]

### Implementation for User Story 3

- [ ] T026 [US3] Extend `shell.run_client_command(command, cwd, timeout=None)` to pass `subprocess`'s `timeout` and surface a `timed_out` sentinel (backward-compatible default `None`) in `src/specops/shell.py` [SC-002]
- [ ] T027 [US3] Extend `GateResult` with a `disposition` field and implement per-gate execution → record/reuse: build the cache key, reuse a matching non-superseded record (`cached`) else run (with timeout) and append a new record, mapping exit/timeout/missing-tool to the taxonomy, in `src/specops/review.py` [SC-002] [SC-003]
- [ ] T028 [US3] Integrate the selected profile suite into `review.evaluate` — replace the `lint`/`test` branches so the pipeline is `reconcile → [selected profile suite] → working-tree → drift`, with the blocking mapping (required `failed`/`unavailable` ⇒ `passed=False`; optional never blocks) in `src/specops/review.py` [SC-004] [SC-007]
- [ ] T029 [US3] Wire `specops gate report [--json]` (full provenance: selection + per-gate disposition/reason/inputs/`evidence_id` + `evidence[]`) and enrich `review --json` gate objects with `disposition`/`commit_range`/`affected_paths`/`evidence_id` in `src/specops/cli.py` [SC-004] [SC-008]

**Checkpoint**: US3 independently testable — the review verdict performs and records the profile suite with a full, cached, provenanced outcome.

---

## Phase 6: User Story 4 - Emit stable JSON and optional SARIF for external tooling (Priority: P3)

**Goal**: A versioned (`output_version`) JSON report over the whole verification
result, byte-for-byte reproducible; an opt-in SARIF 2.1.0 projection of Feature 011
findings.

**Independent Test**: `gate report --json` embeds `output_version` and is byte-identical
across runs; with a findings fixture, `--sarif` emits schema-valid SARIF 2.1.0
preserving rule/location/severity (`blocking→error`, `advisory→warning`); without
`--sarif`, no SARIF is emitted and its absence is not a defect.

**Depends on**: US3 (report command + verdict JSON) and existing Feature 011 findings.

### Tests for User Story 4 (mandatory) ⚠️

- [ ] T030 [P] [US4] Unit test: `gate report --json` carries `output_version` and is byte-for-byte identical for identical recorded state; canonical ordering honored — in `tests/unit/test_gate_report_json.py` [SC-009]
- [ ] T031 [P] [US4] Unit test: SARIF 2.1.0 projection — rule/location/severity mapping, deduped+sorted `rules[]`, deterministic result order (Feature 011 canonical sort), `region` omitted when a finding has no line — in `tests/unit/test_sarif.py` [SC-009]
- [ ] T032 [P] [US4] Integration test: `--sarif` opt-in on `specops review` and `specops gate report` — emitted only when requested, absent by default (not a defect), read-only — in `tests/integration/test_sarif_optin.py` [SC-009]

### Implementation for User Story 4

- [ ] T033 [P] [US4] Implement the SARIF 2.1.0 projection of Feature 011 structured findings (reads `handoff` findings) in `src/specops/sarif.py` [SC-009]
- [ ] T034 [US4] Ensure the gate report / `review --json` builder stamps `output_version` and renders profiles + selection reasons + outcomes + inputs + evidence in a stable shape in `src/specops/cli.py` [SC-009]
- [ ] T035 [US4] Add the opt-in `--sarif` option to `specops review` and `specops gate report` in `src/specops/cli.py` [SC-009]

**Checkpoint**: All four user stories independently functional; the verification result is a stable, versioned contract with optional SARIF.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Constitution/template propagation, docs, and the Global Definition of Done.

- [ ] T036 Amend `.specify/memory/constitution.md` (MINOR bump): additive Principle III/IV guidance for structured evidence + the `specops gate` inspection surface, with an updated Sync Impact Report [SC-004]
- [ ] T037 [P] Update injected directive templates in the same change set — `src/specops/templates/directives/implement.md` (structured-evidence note for `--auto` and finding `fix`) and `src/specops/templates/review.md` (profile-suite + verdict-provenance note) [SC-004]
- [ ] T038 [P] Update English docs (`README.md`) for gate profiles, structured evidence, caching, the `gate` surface, and the v6 migration [SC-008]
- [ ] T039 [P] Update Portuguese docs (`README.pt-br.md`) behaviorally-equivalent to the English changes (FR-022) [SC-008]
- [ ] T040 [P] Record user-visible behavior + the v5→v6 migration requirement in `CHANGELOG.md` under `[Unreleased]` [SC-007]
- [ ] T041 [P] Add a stack-neutrality unit test asserting a gate result derives only from command + exit code + captured summary + local digest (no framework parsing, no remote store) in `tests/unit/test_gate_stack_neutral.py` [SC-010]
- [ ] T042 Add a cross-command read-only/determinism sweep test (`gate list/validate/report`, `review` evaluation leave ledger+config byte-unchanged; byte-identical output) in `tests/integration/test_gate_readonly_determinism.py` [SC-008]
- [ ] T043 Run the repository quality gates under `conda run -n specops`: `ruff check .`, `mypy src/specops`, full `pytest` at ≥85% coverage; fix any gaps [SC-008]
- [ ] T044 Execute the `quickstart.md` validation scenarios (1–8) against fixtures and confirm each maps to its SC [SC-001] [SC-002] [SC-003] [SC-004] [SC-005] [SC-006] [SC-007] [SC-008] [SC-009] [SC-010]

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)** → no dependencies.
- **Foundational (P2)** → after Setup; blocks all stories.
- **US1 (P1)** → after Foundational. Independent of US2.
- **US2 (P2)** → after Foundational. Independent of US1 (can run in parallel with US1).
- **US3 (P2)** → after **US1 + US2** (needs selection + evidence + v6 schema).
- **US4 (P3)** → after **US3** (report/JSON surface); `sarif.py` itself (T033) can be
  built in parallel earlier since it only reads existing Feature 011 findings.
- **Polish (P7)** → after all targeted stories.

### Within each story

- Tests written first and failing before implementation (Constitution task gate).
- `gateprofiles.py` parse (T008) → validate (T009) → select (T010) → default synth (T011) → CLI (T012).
- `evidence.py`/`ledger.py` records+migration (T017–T019) → `status.py` wiring (T020) → `handoff.py` finding-evidence wiring (T021, needs T017).
- `shell` timeout (T026) → `review.py` per-gate execution/caching (T027) → pipeline integration (T028) → CLI report (T029).

### Parallel opportunities

- T002 ∥ (setup); T004 ∥ (foundational).
- **US1 and US2 run in parallel** (disjoint files: `gateprofiles.py` vs `evidence.py`/`ledger.py`/`status.py`/`handoff.py`).
- All `[P]` test tasks within a story run together (distinct test files).
- US4 `sarif.py` (T033) can start any time after Foundational.
- Polish T037–T041 are `[P]` (distinct files); T036 (constitution) precedes T037 (templates in the same change set).

---

## Parallel Example: US1 + US2 concurrently (after Foundational)

```bash
# Developer A — US1 (selection), Developer B — US2 (evidence/migration):
Task: "T005 Unit tests for profile validate in tests/unit/test_gateprofiles_validate.py"
Task: "T013 Unit tests for evidence record id in tests/unit/test_evidence_record.py"
Task: "T008 Implement GateProfile parser in src/specops/gateprofiles.py"
Task: "T017 Implement StructuredEvidence + id in src/specops/evidence.py"
```

---

## Implementation Strategy

### MVP first (US1 only)

1. Phase 1 Setup → Phase 2 Foundational.
2. Phase 3 US1 (ordered profiles + deterministic selection + default-profile degrade +
   `gate list`/`validate`).
3. **STOP and VALIDATE**: US1 is independently testable (SC-001, SC-006) with no ledger
   change — the smallest shippable slice.

### Incremental delivery

1. Setup + Foundational → foundation ready.
2. US1 (MVP) → validate → demo.
3. US2 (structured evidence + v6 migration + task/finding links) → validate (SC-005, SC-007).
4. US3 (taxonomy + caching + provenanced verdict, the `review.py` seam) → validate
   (SC-002, SC-003, SC-004, SC-007).
5. US4 (stable JSON + opt-in SARIF) → validate (SC-009).
6. Polish (constitution/templates/docs/changelog + Global DoD gates).

---

## Notes

- `[P]` = different files, no incomplete-task dependency.
- Every task carries `[SC-xxx]` tags (roadmap Tasks-and-analysis rule) for
  `/speckit-analyze` traceability; `[US*]` labels map to spec.md user stories.
- No task self-applies SpecOps to this repository — all `specops` behaviors are proven
  by the feature's own tests against fixtures/sample repos (No Self-Application).
- T021 composes Feature 011's `handoff` finding lifecycle (it links a structured
  evidence record and sets `finding.evidence_id`); it does **not** redefine that
  lifecycle or the `handoff` CLI.
- The constitution/template amendment (T036/T037) ships in the **same change set**
  (constitution governance rule), mirroring Features 009/010/011.
- Commit granularity: one commit per user story (Constitution III); intermediate tasks
  closed with `--evidence`, the story's final task with a single US-level commit.
</content>
