# Quickstart & Validation: Native Workflow Orchestration

A runnable validation guide proving the feature end-to-end. Each scenario maps to a success criterion.
Implementation details live in `tasks.md`; this file is the *run/validate* guide.

## Prerequisites

- A Spec Kit-initialized client repository (the fixtures under `tests/` provide one).
- SpecOps installed (`pip install speckit-specops`) and its extension registered:
  ```bash
  specops extension install     # registers commands + the `specops` workflow (additive)
  specify workflow list         # shows `specops` alongside the untouched bundled `speckit`
  ```

## Scenario 1 — Full lifecycle with the readiness gate (SC-001, SC-003)

```bash
specify workflow run specops --input spec="Add a widget export endpoint"
```
Expected: the run walks specify → (clarify/checklist gates) → plan → **pauses at the human readiness
gate** before tasks → after approval, tasks → analyze → implement → review → DONE. Verify tasks were
**not** generated until the readiness gate was approved, and every phase advance appears in
`status.yaml` written by a `specops status` step (not the engine).

## Scenario 2 — SpecOps builds no orchestrator (SC-002, SC-007)

Inspect `.specify/workflows/specops/workflow.yml`: every `steps[].type` is a Spec Kit native type
(`command`/`shell`/`gate`/`do-while`/`if`). Confirm no engine/resume/gate/loop code exists under
`src/specops/`. Confirm all `status.yaml` mutations trace to a `specops status …` invocation.

## Scenario 3 — Resume + reconciliation stays authoritative (SC-004)

Interrupt the run mid-implement (kill the process), then:
```bash
specify workflow resume            # Spec Kit's own resume
```
Expected: the `specops reconcile` precondition re-aligns the ledger; the run continues from the
correct step with no duplicate phase advance. Then desync deliberately (e.g. `git reset` past the
baseline) and resume: `specops reconcile` exits `1` with `diverged_dimension`, the run halts, and the
guide points to `specops status rebaseline` (no new command).

## Scenario 4 — Bounded corrective loop + terminal gate (SC-005, SC-008)

Force the review gate to fail (e.g. failing `test_command` in `specops.json`):
```bash
specops review --json    # -> {"class":"gate-rejection","verdict":"REJECTED"}
```
Expected: the `do-while` loops implement→review while `verdict == REJECTED`, recording a new review
cycle each round; when `max_iterations` is exhausted still rejecting, the **terminal `specops review`
gate** fails closed (exit 1) and the run halts for an out-of-band human decision — it does **not**
fall through to DONE. Fix the cause; a passing verdict exits the loop and reaches DONE.

## Scenario 5 — Failure classification (SC-006)

```bash
specops reconcile --json     # divergence -> class "infra-error"  (fix env / rebaseline)
specops review --json        # rejection  -> class "gate-rejection" (corrective loop)
# integration command crash  -> Spec Kit engine abort (execution failure) -> `specify workflow resume`
```
Expected: each is a distinct class; in the infra-error and execution-failure cases the ledger phase is
**not** advanced and no review rejection is recorded.

## Scenario 6 — Optional-step skip is explicit and recorded (FR-006)

At the clarify/checklist/analyze gate choose "skip". Verify `status.yaml`'s `workflow.skipped_steps`
records `{step, decision: skip, at}` and the run proceeds without failing. No implicit auto-skip occurs.

## Scenario 7 — Additive install / backward compatibility (CHK025)

Before/after `specops extension install`, confirm `.specify/workflows/speckit/workflow.yml` is
byte-identical and other `workflow-registry.json` entries are preserved. `specops extension remove`
prunes only the `specops` workflow entry.

## Mapping

| Scenario | Success Criteria |
|---|---|
| 1 | SC-001, SC-003 |
| 2 | SC-002, SC-007 |
| 3 | SC-004 |
| 4 | SC-005, SC-008 |
| 5 | SC-006 |
| 6 | FR-006 |
| 7 | FR-001a, backward compatibility (CHK025) |
