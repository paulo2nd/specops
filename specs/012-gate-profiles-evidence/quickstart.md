# Quickstart & Validation: Gate Profiles and Structured Evidence

Runnable scenarios that prove the feature end-to-end. All exercised against
**fixtures / sample repositories** in the feature's own tests — never by running
`specops` against this repository (No Self-Application). Run tests under the tooling
env: `conda run -n specops python -m pytest tests/ -q`.

## Prerequisites

- A sample repo fixture with `specops.json`, a Feature 006 ledger, and (optionally) a
  `.specify/specops/context-map.yaml` with contexts carrying `gates`/`risk`.
- A `.specify/specops/gate-profiles.yaml` fixture (see `contracts/gate-profiles.config.md`).

## Scenario 1 — Deterministic selection (US1 / SC-001)

1. Fixture: profiles with mixed predicates (`always`, a `contexts`/`gate_ref` match, a
   `paths` glob, a `risk` key) + a known changed-file set.
2. `specops gate list --json`.
3. **Expect**: the selected set + order + per-gate `reason` exactly as declared; run
   twice ⇒ byte-for-byte identical (SC-001). A `paths`-scoped gate whose glob does not
   match ⇒ `selected:false, reason:"out-of-scope"`.

## Scenario 2 — Default-profile degrade (US1 / SC-006)

1. Fixture: **no** `gate-profiles.yaml`, `specops.json` with `test_command:"pytest"`.
2. `specops gate list --json` then `specops review --json`.
3. **Expect**: a synthesized `test` gate (`always`, required); verification runs
   unchanged; exit `0` for selection; no retroactive block (roadmap Rule 5).

## Scenario 3 — Config validation fails closed (US1 / SC-006)

1. Fixtures each seeding one defect: duplicate name; empty command; non-positive
   timeout; unparseable predicate; dangling `contexts`/`gate_ref`; unsupported
   `output_version`.
2. `specops gate validate --json`.
3. **Expect**: exit `1`, one **distinct** diagnostic per defect; a well-formed config
   ⇒ exit `0`, no false positives.

## Scenario 4 — Structured evidence + migration (US2 / SC-005, SC-007)

1. Fixture: a **v5** ledger with legacy `evidence` strings (`TEST_REPORT:…;
   CODE_DIFF:…`) and no `evidence` list.
2. Trigger the v5→v6 migration (load through `ledger`); then read the ledger.
3. **Expect**: `schema_version:6`; every legacy string → a `StructuredEvidence`
   record (class+summary preserved, zero loss); `task.evidence` string **retained**;
   `task.evidence_refs` set; absent list ⇒ explicit `[]`; migration idempotent; the
   pre-migration ledger still readable (SC-007).

## Scenario 5 — Outcome taxonomy + safe caching (US3 / SC-002, SC-003)

1. Run a suite; record evidence. Re-run with:
   - all cache-key components unchanged ⇒ gate `disposition:"cached"`, command **not**
     re-executed (SC-003 reuse);
   - a changed commit / changed `context_map_digest` / changed inputs (any one) ⇒
     **not** cached, fresh run, new `EV-id`, prior record `superseded_by` set (SC-003
     no-reuse).
2. Seed a missing command / absent tool ⇒ `disposition:"unavailable"` (distinct from
   `failed`, SC-002). Seed a timeout ⇒ `disposition:"failed"`, reason `timeout`.
3. **Expect**: exactly one taxonomy value per gate; a required `failed`/`unavailable`
   ⇒ verdict blocked (SC-007); an `optional` failure ⇒ never blocks (SC-007).

## Scenario 6 — Fully-provenanced verdict (US3 / SC-004)

1. `specops review --json` (or `specops gate report --json`) after a run.
2. **Expect**: each gate shows `disposition`, `reason`, covered `commit_range` +
   `affected_paths`, and its supporting `evidence_id`; the `evidence[]` records
   resolve those ids (SC-004).

## Scenario 7 — Stable JSON + opt-in SARIF (US4 / SC-009)

1. `specops gate report --json` ⇒ carries `output_version`; run twice ⇒ byte-for-byte
   identical (SC-009).
2. With a findings fixture: `specops review --sarif` (or `gate report --sarif`) ⇒
   schema-valid SARIF 2.1.0 preserving rule/location/severity mapping; **without**
   `--sarif` ⇒ no SARIF emitted, and its absence is not a defect (SC-009).

## Scenario 8 — Read-only & determinism (SC-008, SC-010)

1. Byte-compare ledger + config before/after every read-only command (`gate
   list/validate/report`, `review` evaluation) ⇒ unchanged (SC-008).
2. Confirm no gate result depends on a test framework, language, or remote store — the
   record derives only from command + exit code + summary + local digest (SC-010).

## Repository quality gates (Global DoD)

`conda run -n specops` → `ruff check .`, `mypy src/specops`, `python -m pytest tests/`
(coverage ≥ 85%). EN + PT docs updated behaviorally-equivalent (FR-022); CHANGELOG
records the v6 migration + the new `gate` surface + the profile config.
</content>
