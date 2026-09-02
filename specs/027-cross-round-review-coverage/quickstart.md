# Quickstart: Validating Cross-Round Review Coverage

**Feature**: 027 | **Date**: 2026-09-02

> **No self-application.** Constitution *Development Workflow & Quality Gates* §3:
> SpecOps' own gate behavior is validated **exclusively** through the fixture
> suite under `tests/`, never by running `specops` against this repository. Every
> scenario below runs against a throwaway git fixture.

## Prerequisites

```bash
conda run -n specops python -c "import specops; print(specops.__file__)"
```

The `specops` conda env is required — `base` carries a numpy stub that aborts
mypy and hides real errors.

## Full check

```bash
conda run -n specops ruff check src tests
conda run -n specops mypy src
conda run -n specops pytest -q
```

## Targeted runs

```bash
# Coverage derivation (R1/R2/R5) — pure + real-git
conda run -n specops pytest tests/unit/test_reviewscope.py -q

# Approval guard end to end (US3)
conda run -n specops pytest tests/integration/test_review_coverage_guard.py -q

# record-scope emission (US1/US2)
conda run -n specops pytest tests/integration/test_corrective_scope.py -q

# Frozen surfaces must not move
conda run -n specops pytest tests/unit/test_frozen_envelope.py tests/golden -q
```

Existing fixture helpers: `tests/conftest.py` (`tmp_git_repo`, `git`) and the
`_commit` / `_linear_repo` builders already in `tests/unit/test_reviewscope.py`.

---

## Scenario 1 — Reviewer sees the whole feature (US1)

**Setup**: fixture with an anchor round recorded over `baseline..t₁`, a corrective
round open, one fix commit touching `src/a.py`, and `src/c.py` changed before `t₁`
and untouched since.

**Run**: `handoff record-scope`.

**Expect**:
- `scope_paths` contains `src/a.py` (unchanged from today);
- `baseline_paths` contains `src/a.py` **and** `src/c.py`;
- `not_reverified_paths == ["src/c.py"]`;
- the human output prints a labelled *not yet re-verified this round* block;
- the persisted `reviewed_range` is byte-identical to what Feature 025 recorded.

**Anchor variant**: on the anchor round `not_reverified_paths == []` and no second
block is printed.

## Scenario 2 — Never-reached derivation (US2)

**2a — intact chain.** Rounds chaining `baseline → t₁ → HEAD`, all endpoints
resolving ⇒ `never_reached_paths == []`. (SC-002 — the no-false-block case.)

**2b — orphaned middle range.** Rewrite the commit `t₁` names (amend/squash) so the
recorded `baseline..t₁` no longer resolves, keeping the baseline intact ⇒ the paths
that range alone accounted for appear in `never_reached_paths`, by name. (SC-003 —
the silent-credit hole.)

**2c — moved baseline.** Point the ledger baseline at an earlier commit ⇒ the
product paths changed in the newly-included span appear.

**2d — managed exclusion.** Change `.specify/…`, `specops.json`, `specs/<active>/…`
**and** `specs/<some-other-feature>/…` ⇒ none appear in any of the three sets
(FR-005a — the rename case).

## Scenario 3 — Approval fails closed (US3)

**Acceptance gate from the roadmap.** Drive REJECTED → REJECTED → APPROVED on a
fixture where no round ever reached `src/d.py`:

| Case | Expect |
|---|---|
| no round reached `src/d.py` | approval blocked, exit `1`, message names `src/d.py` |
| plus an anchor round reaching it | approval succeeds |
| ledger with no reviewed-scope records | closes through the pre-025 path (FR-008) |
| baseline unresolvable, records present | blocked, **unchanged** message (FR-009) |
| no product change since the baseline | approval proceeds |

**Bounded message**: with 37 never-reached paths, assert the message states `37`
and names exactly 10; with 3, assert all 3 named and no `(N shown of M)` suffix.

**Recovery**: after a 2b block, one `handoff record-scope` on the round already
open re-anchors over `baseline..HEAD` and the next approval succeeds — no new
round consumed.

## Scenario 4 — Nothing else moved (SC-007)

- `tests/golden` re-runs clean **without** `--golden-record` for `preflight`,
  `reconcile`, `consistency`, and every `handoff` command other than
  `record-scope`.
- `tests/unit/test_config_round_cap.py` and `tests/integration/test_round_cap.py`
  pass untouched.
- `tests/unit/test_reconcile_reviewed_range_exempt.py` passes untouched — the
  `reconcile` half of the Principle II carve-out is not narrowed.
- Ledger `schema_version` stays `9`; no new migration test.

## Scenario 5 — Directive (FR-012)

`tests/unit/test_review.py`-style assertion on
`src/specops/templates/review.md`: the corrective bullet no longer contains
"Do **not** re-hunt unchanged, already-reviewed code", and does state that the
remainder of the baseline set is unverified this round and that declining to read
it is the reviewer's decision to record.

## Definition of done

- [ ] `ruff`, `mypy`, `pytest` clean under `conda run -n specops`
- [ ] Scenarios 1–5 asserted by fixtures under `tests/`
- [ ] Constitution amended to `1.13.0` (Principles II and IV — research R2/R7),
      Sync Impact Report updated, `templates/review.md` edited in the same commit
- [ ] `README.md` and `README.pt-br.md` updated together
- [ ] `CHANGELOG.md` entry under `[Unreleased]`
- [ ] No `specops.json` / `status.yaml` created in this repository
