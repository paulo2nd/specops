# Phase 0 Research: Contract Freeze for 1.0

All Technical Context unknowns were resolved by reading the codebase; no external
research was required. Decisions below are grounded in concrete `file:line` sites.

## D1 — Where the stability policy lives

- **Decision**: A new **`docs/stability.md`** (English, authoritative), cross-linked from
  `README.md`, `README.pt-br.md` (PT pointer/summary), `docs/commands.md`, and
  `CHANGELOG.md`. It references — does not duplicate — the existing per-feature contract
  docs (`specs/012-…/contracts/gate-profiles.config.md`, `specs/015-…/contracts/findings-input.schema.json`,
  `specs/018-internal-hardening/contracts/cli-output.md` + `internal-api.md`).
- **Rationale**: Adopters read `docs/` and `README`, not `specs/`. A dedicated file makes
  the policy discoverable and citable (CHK007). The constitution is repo-governance, not
  adopter documentation, so the policy does not belong there — only the Principle VI
  amendment (D4) touches the constitution.
- **Alternatives considered**: (a) a new section inside `docs/commands.md` — rejected: the
  policy is a distinct concern that deserves its own stable URL/anchor; (b) put it in the
  constitution — rejected: mixes adopter contract with internal governance.

## D2 — Base-envelope `output_version` approach (the one code delta)

- **Finding**: `outcome.render()` (`outcome.py:85-89`) builds exactly three keys —
  `command`, `outcome` (ok/blocked/error), `class` (pass/gate-rejection/infra-error).
  `output_version` is **not** in the base envelope. It reaches JSON only because the CLI
  `_emit()` path (`cli.py:597-602`) injects `output_version=<module>.OUTPUT_VERSION` for the
  context/trace/handoff/gate families — while the standalone `outcome.render()` call sites
  for `consistency` (`cli.py:234`) and `reconcile` (`cli.py:201`) pass **no** version, and
  the `preflight`/`review` path (`cli.py:301-306`) passes `output_version` but not `status`.
  Versioning is inconsistent across families today.
- **Decision**: Introduce a single **`outcome.OUTPUT_VERSION = 1`** and have
  `outcome.render()` **always** emit `"output_version": OUTPUT_VERSION`. Remove the
  per-caller `output_version=` argument from `_emit()` and the `preflight` path so the
  envelope version is single-sourced. Net effect: every `--json` output now carries
  `output_version: 1`; `consistency`/`reconcile`/`preflight` gain the key (additive);
  the report families keep it, now single-sourced.
- **Keep separate** (these are NOT the CLI envelope version): the **gate-profile file**
  `output_version` (`gateprofiles.py:30`, validated `:391`) is a *persisted-format* version;
  the **context provenance** `output_version` embedded in the ledger
  (`contextmap.py:929`) is *ledger state*. Both remain their own fields and are frozen as
  persisted-format versions, not folded into the envelope version.
- **Rationale**: Delivers the clarification-Q2 requirement (one detectable version signal
  for every consumer) as a small, centered change, and removes an existing wart rather than
  freezing it. Single-sourcing prevents the family constants from drifting apart.
- **Consequence**: Golden `--json` captures for the `consistency`, `reconcile`, and
  `preflight` families change (they gain `output_version`). These are **re-recorded** via
  the golden harness (`--golden-record`). The change is additive; the frozen-shape tolerance
  test (FR-007) must treat a new optional key as passing.
- **Alternatives considered**: (a) document heterogeneity, no code change — rejected in
  clarification Q2; (b) one top-level `output_version` via a larger refactor of every
  command's output construction — rejected: contradicts the "no redesign" posture and
  touches far more than `render()`.

## D3 — Reuse existing contract-test & migration mechanisms

- **Decision**: Model the new frozen-shape tests on **`tests/unit/test_outcome_contract.py`**,
  which already freezes the status→class→exit mapping by enumerating expected tables
  *independently of the modules* (`test_outcome_contract.py:79-118`) so drift is caught.
  Each new `test_frozen_*.py` enumerates the frozen field set of one surface and asserts the
  module's live schema matches (missing/renamed/type-changed frozen field ⇒ fail; extra
  optional field ⇒ pass). For CLI JSON, add/refresh **golden** scenarios
  (`tests/golden/harness.py` `Scenario` registry) for surfaces lacking one (e.g.
  `gate validate`, `handoff finding import-json`).
- **Migration obligation** (FR-008): the versioning policy points at the existing ledger
  migration-test mechanism — `ledger.classify()`/`migrate_to_current()` (`ledger.py:143/215`)
  exercised by `tests/unit/test_ledger_v7_migration.py` (build prior-version dict → assert
  `classify()==MIGRATABLE`, migrated `schema_version==CURRENT_SCHEMA`, lossless, invariants
  clean, idempotent). No new migration mechanism is invented.
- **Rationale**: The repo already has the exact patterns; the freeze standardizes and
  extends them rather than building parallel machinery.

## D4 — Constitution Principle VI amendment level

- **Finding**: Principle VI (`constitution.md:481-489`) mandates only exit `0`/`1`. The code
  emits `0`/`1`/`2` (`outcome.py:25-27`; `errors.py` `LedgerParseError.exit_code=2`).
- **Decision**: Amend Principle VI to document exit `2` (infrastructure/data/usage error) in
  the same change set, bump the constitution version, and update the Sync Impact Report
  comment (governance rule, `constitution.md:547-554`). **Recommend PATCH** (1.9.2 → 1.9.3):
  it aligns wording to already-shipped behavior; no principle is added, removed, or
  redefined; VI's intent (composable exit-code gates) is unchanged. **MINOR is defensible**
  if a reviewer treats a newly-named mandated exit value as materially expanded guidance.
  **DECIDED (human-approved 2026-07-28): PATCH (1.9.2 → 1.9.3).**
- **Rationale**: Freezing an exit-code contract the governing principle contradicts is
  incoherent; principle and test must agree (CHK016).
- **Alternatives considered**: leave VI at 0/1 (freeze contradicts its own governance —
  rejected); collapse code to 0/1 (breaking change, opposite of a freeze — rejected).

## D5 — Bilingual documentation reality (corrects a spec assumption)

- **Finding**: There is **no automated bilingual-equivalence check** in the repo (grep over
  `tests/`/`docs/` finds none; the single hit is an unrelated "equivalent" comment).
  `README.md` (EN, 8.5K) is authoritative; `README.pt-br.md` (PT, 2.4K) is a summary with a
  language switcher, not a full mirror.
- **Decision**: SC-006's phrase "verified by the existing bilingual-equivalence check" is
  **corrected** to: the freeze is described in EN (`docs/stability.md` + a `README.md`
  section) with a PT pointer/summary in `README.pt-br.md`; equivalence is maintained by
  **manual PR review** (the standing practice), and the objective, testable part of SC-006
  is *presence of the freeze description in both language entry points* plus the CHANGELOG
  link. No automated equivalence check is built (out of scope; would be its own feature).
- **Rationale**: Keeps SC-006 truthful and testable without inventing tooling. Flagged to the
  user in the completion report so they may amend the spec's SC-006/§Assumptions wording if
  they prefer the spec to match this reality verbatim.
- **Alternatives considered**: build an automated EN/PT equivalence checker — rejected: net
  new capability, contradicts FR-012 ("no new capability"); belongs to a separate feature.

## D6 — `specops.json` has no version field (freeze mechanism)

- **Finding**: `config.py` writes only four defaulted keys (`test_command`, `lint_command`,
  `skills_dir`, `min_cli_version`) plus an optional `lane.safety` block; **no
  `schema_version`**. Unknown keys are preserved on merge (`merge_preserve`, `config.py:54-56`).
- **Decision**: Freeze `specops.json` as **additive-only with preserve-unknown** as its
  stability mechanism (no version field is introduced — that would be a second code delta,
  which FR-012 forbids). The policy states: new optional keys may be added; existing keys are
  never removed/renamed/retyped without a MAJOR release; unknown keys are always preserved.
  `min_cli_version` is documented as a *CLI-compat gate*, not a file-schema version.
- **Rationale**: Matches shipped behavior; avoids a second sanctioned code delta.

## D7 — `templates/status.yaml` declares `schema_version: 4` while CURRENT_SCHEMA=7 (observed drift)

- **Finding**: `src/specops/templates/status.yaml:1` says `schema_version: 4`; new ledgers are
  migrated up to 7 on first write (`ledger.CURRENT_SCHEMA=7`).
- **Decision**: The **authoritative frozen baseline is `CURRENT_SCHEMA=7`** (the migrated,
  written shape), which is what the contract test pins and the golden captures reflect. The
  template literal is **left unchanged** in this feature to preserve existing
  migrate-on-first-write behavior and golden output; changing it is a separate, out-of-scope
  cleanup. Recorded here so the contract test asserts against `records.LedgerDocument` /
  `CURRENT_SCHEMA`, not the template literal.
- **Rationale**: Avoids an unrelated behavior change inside a freeze; keeps scope minimal.
- **Flag**: noted for the user as a candidate follow-up (align the template to 7) — not done
  here.

## Resolved unknowns summary

| Unknown | Resolution |
|---|---|
| Policy home | `docs/stability.md` (EN) + README pointers + CHANGELOG link (D1) |
| Envelope version delta | Single `outcome.OUTPUT_VERSION`, always emitted by `render()` (D2) |
| Contract-test pattern | Extend `test_outcome_contract.py` enumerated-table style + golden scenarios (D3) |
| Migration obligation mechanism | Existing `ledger` classify/migrate + `test_ledger_v7_migration.py` pattern (D3) |
| Amendment level | Principle VI PATCH recommended, MINOR defensible — human-confirmed (D4) |
| Bilingual "equivalence check" | None exists; manual review + dual-language presence (D5) — spec SC-006 corrected |
| `specops.json` versioning | Additive-only + preserve-unknown; no version field added (D6) |
| Template schema_version drift | Baseline = CURRENT_SCHEMA=7; template left as-is, flagged (D7) |
