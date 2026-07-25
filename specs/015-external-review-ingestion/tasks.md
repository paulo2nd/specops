---
description: "Task list for Feature 015 — External Review Ingestion"
---

# Tasks: External Review Ingestion

**Input**: Design documents from `specs/015-external-review-ingestion/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/findings-input.schema.json, contracts/ingestion-cli.md, quickstart.md

**Tests**: Per the Constitution task gate, every task closes with passing automated tests. The pure parse/identity/digest logic is unit-tested without a repo; the commands are integration-tested over fixture repos with an open review cycle. Every task carries one or more `[SC-xxx]` tags (roadmap §4).

**Organization**: Grouped by user story. MVP = **US1 + US3** (both P1): ingest external findings and keep them advisory-until-human-promotion. US2 (SARIF) and US4 (staleness) layer on top.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US4 from spec.md
- Exact file paths are included in each description

## Path Conventions

- New pure module: `src/specops/ingestion.py`
- Edited modules: `src/specops/handoff.py`, `src/specops/ledger.py`, `src/specops/gitops.py`, `src/specops/cli.py`
- Unit tests: `tests/unit/test_ingestion.py`, `tests/unit/test_ledger_v7_migration.py`
- Integration tests: `tests/integration/test_handoff_ingestion_cli.py`
- Contract: `specs/015-external-review-ingestion/contracts/findings-input.schema.json`
- Docs: `README.md`, `README.pt-br.md`, `CHANGELOG.md`
- Run tooling under `conda run -n specops …` (repo convention)

### Single-file coupling (important)

- `src/specops/ingestion.py` is edited by **T005, T009, T017** → sequential, never `[P]` together.
- `src/specops/handoff.py` is edited by **T006, T010, T013, T018, T022** → sequential.
- `src/specops/cli.py` is edited by **T011, T014, T019** → sequential.
- `tests/unit/test_ingestion.py` is edited by **T007, T015, T020** → sequential.
- `tests/integration/test_handoff_ingestion_cli.py` is edited by **T008, T012, T016, T021** → sequential.

---

## Phase 1: Setup (Shared Baseline)

**Purpose**: Establish a green baseline before editing the shared modules.

- [ ] T001 Run `conda run -n specops pytest tests/unit/test_handoff.py tests/unit/test_ledger.py tests/unit/test_ledger_v6_migration.py tests/unit/test_sarif.py tests/integration/test_handoff_cli.py -q` and confirm all pass; record the current `ledger.CURRENT_SCHEMA` (6) and the Feature 011 finding record shape as the modification baseline. [SC-009]

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The shared layer every story needs — ledger v7, the per-location digest helper, the pure ingestion scaffolding, and the handoff record/status additions. **No user story can proceed until this phase is done.**

- [ ] T002 In `src/specops/ledger.py`, bump `CURRENT_SCHEMA` 6 → 7; make `migrate_to_current` additive (version bump only — the new finding fields are optional, absence means "not imported", no backfill); update `finding_structural_defects` to **accept** the new optional finding fields (`imported`, `producer`, `reviewed_digest`, `promotion`) and never flag their presence or absence as a defect. [SC-009]
- [ ] T003 [P] Add `tests/unit/test_ledger_v7_migration.py` (modeled on `test_ledger_v6_migration.py`): a v6 ledger with pre-existing findings upgrades to v7 with zero data loss; cycle/handoff records stay semantically identical; migration is idempotent; a v6 finding without the new fields reads and validates clean. [SC-009]
- [ ] T004 [P] In `src/specops/gitops.py`, add `blob_sha(repo, rev, path) -> str | None` returning the git blob SHA of `path` at `rev` (`repo.commit(rev).tree / path` → `.hexsha`), returning `None` when the path is absent or `rev` unresolvable; add its unit coverage in `tests/unit/test_ingestion.py` (present path → stable sha; missing path/rev → None). [SC-006]
- [ ] T005 Create `src/specops/ingestion.py` (pure, no I/O): `INPUT_CONTRACT_VERSION = 1`; a normalized-finding representation; `content_identity(f)` = `(producer_name, rule, file, line, action)`; the advisory-severity constant; the SARIF→advisory severity handling (reuse `sarif.SARIF_VERSION`); and the all-or-nothing defect-collector type used by both adapters. No parsing yet — just the shared scaffolding US1/US2/US4 import. [SC-001][SC-004]
- [ ] T006 In `src/specops/handoff.py`, add the ingestion status vocabulary (`FINDINGS_IMPORTED`, `FINDING_PROMOTED` → `outcome.PASS` in `_CLASS_FOR_STATUS`); extend the finding record builder and `_finding_view` to carry the optional `imported`, `producer`, `reviewed_digest`, and `promotion` fields (absent on non-imported findings); add a shared `_apply_import(feature_dir, data, base_rev, base_violations, normalized)` write helper that appends new findings via `_next_id`, matches existing findings by `ingestion.content_identity` (refresh `reviewed_digest` in place, never duplicate, never overwrite `promotion`), and commits once via `status._finalize`. [SC-001][SC-004]

**Checkpoint**: Ledger is v7 with a green migration test; `blob_sha` works; the pure scaffolding and the handoff record/write helper exist. Begin User Story 1.

---

## Phase 3: User Story 1 - Ingest external findings through a versioned JSON contract (Priority: P1) 🎯 MVP-core

**Goal**: `handoff finding import-json` lands a schema-valid JSON document as `advisory` findings carrying producer + reviewed-diff-digest provenance, deterministically, idempotently, and all-or-nothing.

**Independent Test**: Against a fixture with an open review cycle, import a sample JSON document and confirm `handoff report --json` lists each finding as `advisory`/`OPEN` with `producer` and `reviewed_digest` and a stable `R<round>-F<NN>` id — no built-in review ran.

### Tests for User Story 1 ⚠️

- [ ] T007 [US1] Add unit tests in `tests/unit/test_ingestion.py` for `parse_contract`: a valid `contract_version: 1` document → normalized findings; unknown/missing `contract_version`, missing `rule`/`file`/`action`, and missing `producer.name` each accumulate a named defect; producer without version → `"unspecified"`; an empty `findings: []` → zero findings + no defect; two results with equal content identity collapse to one; normalized ordering is deterministic. [SC-001][SC-007]
- [ ] T008 [US1] Add integration tests in `tests/integration/test_handoff_ingestion_cli.py` for `handoff finding import-json`: import → `findings_imported` (exit 0) and `handoff report --json` shows each finding `advisory`/`OPEN` with `producer` + `reviewed_digest` (SC-001); a document with any defect → exit 2 naming every defect with the ledger byte-identical before/after (SC-007, all-or-nothing); empty-but-valid → exit 0 no-op no write; no open review cycle → exit 2 no write; a second identical import → no duplicate and byte-identical ledger (SC-004, idempotency). [SC-001][SC-004][SC-007]

### Implementation for User Story 1

- [ ] T009 [US1] In `src/specops/ingestion.py`, implement `parse_contract(doc) -> (normalized, defects)` per `contracts/findings-input.schema.json`: validate `contract_version`, required fields, and producer; apply document-level `producer`/`reviewed_commit` defaults with per-finding overrides; normalize paths via `trace._norm`; every finding severity `advisory`. Pure — collects all defects, writes nothing. [SC-001][SC-007]
- [ ] T010 [US1] In `src/specops/handoff.py`, implement `cmd_finding_import_json(root, *, file)`: read the document (path or `-`/stdin), call `ingestion.parse_contract`; on any defect return `BAD_ARGS` naming all (no write); else capture each finding's `reviewed_digest` via `gitops.blob_sha(repo, reviewed_commit or HEAD, file)`, require an open review cycle (else `BAD_ARGS`), and apply via `_apply_import`. Returns `FINDINGS_IMPORTED` with count + new ids (+ `refreshed` count on re-import). [SC-001][SC-004][SC-007]
- [ ] T011 [US1] In `src/specops/cli.py`, register `handoff finding import-json` under `finding_app` (`--file <path>`, `-` = stdin, `--json`), bridging through the existing `_emit_handoff` pattern. [SC-001]

**Checkpoint**: External JSON findings become advisory handoff state, deterministically and all-or-nothing; T007/T008 pass.

---

## Phase 4: User Story 3 - External findings are advisory until a human escalates them (Priority: P1) 🎯 completes MVP

**Goal**: Every import is `advisory` regardless of declared severity; a human, audited `promote` is the sole path to `blocking`, after which the Feature 011 blocking-approval invariant gates completion; withdrawal reuses the existing `dismiss`.

**Independent Test**: Import a finding whose producer declared `error`/`critical`; confirm it is `advisory` and does not block; promote it (with closure + expected evidence) and confirm `DONE -r APPROVED` is blocked until it is verified or dismissed; confirm a re-import never demotes it.

### Tests for User Story 3 ⚠️

- [ ] T012 [US3] Add integration tests in `tests/integration/test_handoff_ingestion_cli.py`: a producer-declared blocking-equivalent severity still imports `advisory` and does not block approval (SC-002); `handoff finding promote <ID> --closure … --expected-evidence …` sets `blocking` + `promotion` and `status transition-phase DONE -r APPROVED` then exits 1 naming the finding until `handoff finding verify` (SC-003); `handoff finding dismiss <ID> --reason …` also unblocks (CHK005 delegation); a re-import of the same document leaves the promoted finding `blocking` with its `promotion` intact (SC-004, no demote); promoting without `--closure`/`--expected-evidence` → exit 2. [SC-002][SC-003][SC-004]

### Implementation for User Story 3

- [ ] T013 [US3] In `src/specops/handoff.py`, implement `cmd_finding_promote(root, fid, *, closure, expected_evidence)`: fail closed (`BAD_ARGS`/`UNKNOWN_FINDING`) when the finding is unknown, not imported, not `advisory`, or `--closure`/`--expected-evidence` missing; else set `severity=blocking`, `closure_criteria`, `expected_evidence`, and a `promotion={"at": now_utc()}` record; write via `status._finalize`. Returns `FINDING_PROMOTED`. Withdrawal/demotion is the existing `cmd_finding_dismiss` (no new command). [SC-002][SC-003]
- [ ] T014 [US3] In `src/specops/cli.py`, register `handoff finding promote` under `finding_app` (`<ID>`, `--expected-evidence`, `--closure`, `--json`). [SC-003]

**Checkpoint**: MVP complete — external findings are advisory, human-promotable, and enforced through the unchanged Feature 011 gate; T012 passes.

---

## Phase 5: User Story 2 - Ingest findings from a SARIF-emitting tool (Priority: P2)

**Goal**: An optional SARIF 2.1.0 input adapter maps each result to an `advisory` finding preserving rule/primary-location/(informational) severity and recording `tool.driver` as producer — the inverse of the Feature 012 output adapter.

**Independent Test**: Import a sample SARIF document; confirm each result becomes an `advisory` finding with rule + primary location + `producer` from `tool.driver`; combined with US1, two distinct producers coexist attributed (roadmap acceptance gate).

### Tests for User Story 2 ⚠️

- [ ] T015 [US2] Add unit tests in `tests/unit/test_ingestion.py` for `parse_sarif`: a valid SARIF 2.1.0 doc → normalized findings (every one `advisory`) with rule from `ruleId`, action from `message.text`, primary location by the defined rule, producer from `tool.driver.{name,version}`; a non-2.1.0 / unparseable doc → defect; a result with no usable physical location → a named per-result defect; multiple locations → deterministic primary pick. [SC-005][SC-007][SC-008]
- [ ] T016 [US2] Add integration tests in `tests/integration/test_handoff_ingestion_cli.py` for `handoff finding import-sarif`: round-trips rule/location/severity-mapping into `advisory` findings with `tool.driver` producer (SC-008); a SARIF doc with a locationless result → exit 2, ledger byte-identical (SC-007, all-or-nothing); SARIF is opt-in — never invoked by default and its absence is never a defect (SC-008); after both `import-json` (US1) and `import-sarif`, the handoff holds findings from **two distinct producers**, each attributed (SC-005, roadmap gate). [SC-005][SC-007][SC-008]

### Implementation for User Story 2

- [ ] T017 [US2] In `src/specops/ingestion.py`, implement `parse_sarif(doc) -> (normalized, defects)`: validate `version == sarif.SARIF_VERSION`; map `runs[].results[]` (ruleId→rule, message.text→action, primary `physicalLocation.artifactLocation.uri`→file + `region.startLine`→line, `tool.driver.{name,version}`→producer); every result `advisory` (SARIF `level` kept informational only); a result with no usable location → per-result defect. Pure. [SC-005][SC-007][SC-008]
- [ ] T018 [US2] In `src/specops/handoff.py`, implement `cmd_finding_import_sarif(root, *, file)` reusing `_apply_import` (same reviewed-digest capture, open-cycle requirement, all-or-nothing, idempotency as `import-json` — the only difference is the parser). [SC-005][SC-008]
- [ ] T019 [US2] In `src/specops/cli.py`, register `handoff finding import-sarif` under `finding_app` (`--file <path>`, `-` = stdin, `--json`). [SC-005]

**Checkpoint**: A second producer format feeds the same handoff; the roadmap two-producer gate is demonstrable; T015/T016 pass.

---

## Phase 6: User Story 4 - A stale imported finding is flagged, never silently trusted (Priority: P2)

**Goal**: `handoff report` computes per-finding staleness read-only — a finding is `stale` only when the code at its own location changed since it was reviewed.

**Independent Test**: Import a finding, commit a change to the file it points at, and confirm `handoff report` flags that finding `stale: true` while a finding whose target is unchanged stays `stale: false`; report mutates nothing.

### Tests for User Story 4 ⚠️

- [ ] T020 [US4] Add unit tests in `tests/unit/test_ingestion.py` for staleness comparison: given a stored `reviewed_digest.blob` and a current blob, `stale` is `True` when they differ or the current is `None` (path removed), `False` when equal. [SC-006]
- [ ] T021 [US4] Add integration tests in `tests/integration/test_handoff_ingestion_cli.py`: after import, committing a change to one finding's file makes `handoff report --json` show `stale: true` for that finding and `stale: false` for an unrelated one (SC-006); a matching re-import refreshes `reviewed_digest` in place (no duplicate; staleness recomputed) (SC-004/SC-006); `handoff report`/`validate` leave `status.yaml` byte-identical (FR-016, read-only). [SC-006]

### Implementation for User Story 4

- [ ] T022 [US4] In `src/specops/handoff.py`, extend `_finding_view` / `cmd_report` to acquire the repo (`gitops.find_repo`) and, for each imported finding, compute `current_digest = blob_sha(HEAD, file)` and `stale = reviewed_digest.blob != current_digest`, adding `producer`, `reviewed_digest`, `current_digest`, and `stale` to the human + JSON views (additive; `OUTPUT_VERSION` unchanged). No writes. [SC-006]

**Checkpoint**: Per-finding staleness is visible and read-only; T020/T021 pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Documentation parity, contract/quickstart cross-check, full-suite validation, and the roadmap flip.

- [ ] T023 [P] Update `README.md`: document `handoff finding import-json` / `import-sarif` / `promote`, advisory-by-default + human promotion, producer + reviewed-diff-digest provenance, per-finding staleness, all-or-nothing import, and the v6→v7 migration note. [SC-010]
- [ ] T024 [P] Update `README.pt-br.md` with the behaviorally-equivalent Portuguese text for the same section. [SC-010]
- [ ] T025 [P] Add a `[Unreleased]` entry to `CHANGELOG.md` describing the new ingestion surface, advisory-by-default/human-promotion, staleness, and the required v6→v7 migration. [SC-010]
- [ ] T026 Cross-check that `contracts/findings-input.schema.json` matches the implemented `parse_contract` (fields, required set, `contract_version` 1) and that `quickstart.md` scenarios reference the real command spellings. [SC-001]
- [ ] T027 Run full gates: `conda run -n specops ruff check src tests`, `conda run -n specops mypy src`, `conda run -n specops pytest -q`; confirm zero regressions across the existing handoff/ledger/sarif suites and the new tests. [SC-009]
- [ ] T028 Walk the CI-reproducible `quickstart.md` scenarios (1, 4, 5, 6) against the delivered CLI and confirm outcomes match. [SC-006][SC-007]
- [ ] T029 In the feature's own PR commit, flip the `ROADMAP.md` row 015 from `ACTIVE` to `MERGED` (repo policy: the MERGED flip lands inside the feature PR, not a separate chore PR). [SC-010]

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: none — start immediately.
- **Foundational (Phase 2)**: depends on Setup. T002 (ledger v7) blocks T003 (migration test). T004/T005/T006 are the shared layer every story imports. **All of Phase 2 blocks Phases 3–6.**
- **US1 (Phase 3)** and **US3 (Phase 4)** form the P1 MVP; US3 depends on US1 (both edit `handoff.py`; promotion acts on imported findings).
- **US2 (Phase 5)** depends on Foundational; independent of US1's behavior but edits the same `ingestion.py`/`handoff.py`/`cli.py`, so it lands after US1/US3 to avoid churn (its two-producer test T016 needs `import-json` from US1).
- **US4 (Phase 6)** depends on US1 (it surfaces the `reviewed_digest` captured at import).
- **Polish (Phase 7)**: after all story phases; T027/T028 depend on every edit; T029 is the completion commit.

### Parallel Opportunities

- **T003** (new migration test file) and **T004** (gitops.py + its test) are `[P]` — different files.
- **Docs**: **T023** (README.md), **T024** (README.pt-br.md), **T025** (CHANGELOG.md) touch different files → `[P]` together.
- Everything on `ingestion.py`, `handoff.py`, `cli.py`, and each shared test file is serialized per the single-file coupling note above.

---

## Parallel Example: Phase 7 docs

```bash
# Different files, no interdependency — run together:
Task: "Update README.md ingestion section"
Task: "Update README.pt-br.md equivalent section"
Task: "Add CHANGELOG.md [Unreleased] entry"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 3)

1. Phase 1 Setup (T001) → Phase 2 Foundational (T002–T006).
2. Phase 3 US1 (T007–T011): external JSON findings become advisory handoff state.
3. Phase 4 US3 (T012–T014): advisory-by-default + human promotion + Feature 011 enforcement.
4. **STOP and VALIDATE**: external judgment is now ingestible, enforceable, and safe (no auto-block). This is the minimum viable feature.

### Incremental Delivery

1. US1 → JSON ingestion with provenance, deterministic + all-or-nothing.
2. US3 → advisory-until-human-promotion; enforcement via the unchanged gate.
3. US2 → SARIF adapter (second producer; roadmap acceptance gate).
4. US4 → per-finding staleness in the report.
5. Polish → EN/PT docs, changelog, contract/quickstart cross-check, full gates, roadmap flip.

### Commit granularity

One commit per user story (repo convention): commit after each story's tests + implementation pass, plus the Foundational commit and a final polish commit. Never one monolith.

---

## Notes

- `[P]` = different files, no incomplete-task dependency.
- No parallel finding store and no new finding lifecycle — imported findings ARE Feature 011 findings (FR-002/FR-017). Withdrawal reuses the existing `handoff finding dismiss` (CHK005).
- No new runtime dependency: SARIF is parsed as plain JSON (mirroring the Feature 012 output adapter); digests use git's own blob hashing.
- Read paths (`handoff report`/`validate`) must stay read-only — verified by before/after `status.yaml` comparison.
- Do not run `specops` gates against this repository (roadmap "No Self-Application"); acceptance is the feature's own tests against fixtures.
