# Quickstart: Validating the Lightweight Workflow Lane

Runnable validation scenarios proving the feature end-to-end. These map 1:1 to the spec's user
stories and success criteria and are the shape the integration tests (`tests/integration/
test_lane_flow.py`) automate against fixtures under `tests/fixtures/lane/`. Per No
Self-Application, run everything against a **fixture repo**, never this repository.

> **Operating model (how it is really used).** In production the human does not run any
> `specops` command. The injected lite-lane directive makes the agent *recognize and propose*
> the lane; on confirmation the agent/workflow engine drives every `specops lane *` step, and the
> human answers only native gates (eligibility, root-cause attestation, halt/promote). The `specops
> lane` commands are shown **directly** below because this is a validation guide exercising the
> deterministic primitives — that is the agent's job at runtime, not the human's. Scenario F
> validates the directive/operating-model itself.

## Prerequisites

- `pip install -e .[dev]` (Typer, PyYAML, GitPython; pytest/ruff/mypy).
- A fixture Git repo with `specops.json` present and a `specops extension install` having
  registered both `specops` and `specops-lite` workflows.
- Quality gates run under the project env: `conda run -n specops pytest -q` (also `ruff`, `mypy`).

## Setup (per scenario, in the fixture repo)

```bash
specops extension install          # registers specops + specops-lite (idempotent)
specify workflow catalog           # expect: both 'specops' and 'specops-lite' listed
```

---

## Scenario A — Clean lane, proportional ceremony (US1, SC-001, SC-004)

1. Make a small reversible change; commit it on the branch.
2. `specops lane start --answers small,reversible,no-high-risk-category` → exit 0; `lane.yaml`
   at `state: OPEN`; **no** `spec.md`/`plan.md`/`tasks.md` and **no** `status.yaml` created.
3. `specops lane check --json` → exit 0, `detections: []`.
4. `specops lane attest --root-cause confirmed` → exit 0.
5. `specops lane close --json` → exit 0; `verdict: APPROVED`; `lane.yaml` `state: CLOSED` with a
   `closure` block; `retrospective.md` rendered.

**Expected**: closure carries both a retrospective and structured gate evidence (SC-004); zero
full-lifecycle artifacts were required (SC-001). See [contracts/cli-lane.md](./contracts/cli-lane.md).

---

## Scenario B — Safety core halts high-risk work (US2, SC-002, SC-005)

Run once per diff-detectable category (migration, secret, dependency, public-contract,
destructive):

1. `specops lane start …` on a small change, then introduce a change matching the category
   (e.g. add `db/migrations/003.sql`).
2. `specops lane check --json` → **exit 1**, `detections` includes the category.
3. The workflow's `stop-and-ask` gate offers exactly `[halt, promote]` — assert no third
   "continue with reason" path exists (G-1 / INV-3).

Then the non-detectable category:

4. On an otherwise clean change, `specops lane attest --root-cause ambiguous` → **exit 1**;
   closure is blocked until halt-or-promote (D-2).
5. Assert the attestation checkpoint is presented on **every** pass (SC-002), and that
   `specops lane close` refuses without a `confirmed` attestation (SC-005 fail-closed).

**Expected**: 100% of the six categories force a halt; 0% can reach closure by recording a
reason. See [data-model.md §2](./data-model.md).

---

## Scenario C — Lossless promotion to the full workflow (US3, SC-003)

1. `specops lane start …`; make N commits on the branch.
2. Record `git rev-list --all --count` and the reachable set from HEAD.
3. `specops lane promote --reason scope-growth --json` → exit 0;
   `synthesized_ledger: specs/<feature>/status.yaml`, `resumed_phase: PLAN`.
4. Assert:
   - `status.yaml` exists at `current_phase: PLAN` with `promoted_from_lane: true` and a
     non-empty `lane_provenance` (eligibility + decisions + any evidence).
   - The set of commits reachable from HEAD is **identical** before and after (zero loss, P-1).
   - `lane.yaml` is `state: PROMOTED` and read-only.
5. Confirm the full `specops` workflow can continue from PLAN (`specify workflow status`).

**Expected**: 100% commit preservation and a populated ledger (SC-003). A `safety-trip`
promotion (Scenario B → choose `promote`) exercises the identical path (FR-016).

---

## Scenario D — Bundling under supervision (US5)

1. Stage two adjacent reversible changes.
2. `specops lane start --bundle "two adjacent copy tweaks" …` → `eligibility.bundled: true`.
3. Introduce a high-risk change in one of them → `specops lane check` flags it → the **whole**
   bundle halts (not partially completed around the risky change).

---

## Scenario E — Safe degradation & offline (SC-006, FR-019)

1. Remove any context map; run Scenarios A and C. Assert `lane check`/`close`/`promote` still
   succeed (absent optional capability is treated as absent, not a failure).
2. Run offline (no network). Assert all `specops lane` commands function.

---

## Scenario F — Agent-driven operating model (FR-022/FR-023, SC-008)

1. **Directive delivery**: after `specops extension install`, assert the lite-lane directive is
   present at its injection seam (native path) and, on the legacy path, as an idempotent
   marker block; re-running install does not duplicate it. In a repo without SpecOps initialized,
   assert the directive degrades to a no-op (the base Speckit prompt is unchanged).
2. **Recognition → proposal (not auto-entry)**: given a small/reversible request, the directive
   leads the agent to *propose* the `specops-lite` lane and stop at the `eligibility-gate`;
   assert no `lane start` occurs before the human confirms (no auto-classification).
3. **Zero human `specops` commands**: drive Scenario A (or C) via the `specops-lite` workflow and
   assert every `specops lane *` invocation is agent/engine-issued and the human's interactions
   were only native gate/prompt answers (SC-008).

## Edge assertions (from spec Edge Cases)

- Ineligible at entry (migration already present) → `lane start` exits 1, no lane opened.
- Required gate unavailable at closure → `lane close` exits 1 (no silent pass, C-1).
- Promote an empty lane (0 commits) → still produces a valid ledger, loses nothing.
- Abandoned lane (started, not closed) → `lane.yaml` intact; resumable/closable/promotable later.

## What this guide is not

No implementation code, module bodies, or full test suites here — those live in `tasks.md`
(next, via `/speckit-tasks`) and the implementation. This file is the runnable validation
contract only.
