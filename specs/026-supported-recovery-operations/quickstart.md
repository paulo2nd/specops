# Quickstart: Supported Recovery Operations

**Feature**: 026 | **Phase**: 1

Runnable end-to-end validation. Each scenario maps to a user story and its
acceptance scenarios in [spec.md](./spec.md). Command surface and exact messages
are in [contracts/cli-commands.md](./contracts/cli-commands.md); record shapes in
[data-model.md](./data-model.md).

## Prerequisites

```bash
conda run -n specops pip install -e .
conda run -n specops specops status amend-task --help   # the build carries Feature 026
```

A scratch Git repository with a Spec Kit layout and one feature whose ledger has a
`DONE` task. `tests/fixtures/` already provides the ledger fixtures the unit
suite uses; this guide drives the real CLI instead.

## Scenario 1 — Amend a wrongly-closed task (US1)

```bash
specops status show                      # note the DONE task and its evidence
specops status amend-task T001 \
    --evidence "TEST_REPORT: 1795 passed, 0 failed" \
    --reason "original close recorded no gate run; session terminated mid-flight"
```

**Expect**: exit 0; output names the amended evidence, the superseded record id,
and the reason.

Verify the append-only guarantee and that nothing else moved:

```bash
specops status show                      # task still DONE, same completed_at
specops reconcile                        # exit 0 — FR-008
grep -A2 'producer: amend' specs/*/status.yaml   # amendment record with its reason
```

**Expect**: the original record is still in the `evidence:` list with its original
`summary` and `timestamp`, now carrying `superseded_by: EV-…`; exactly one record
referenced by the task has `superseded_by: null`.

Amend a second time and confirm three records survive (acceptance scenario 2):

```bash
specops status amend-task T001 --evidence "TEST_REPORT: rerun clean" --reason "second pass"
```

Refusal paths — every one must exit non-zero (FR-021):

```bash
specops status amend-task T002 --evidence "CLI_LOG: x" --reason "y"; echo $?  # not DONE → 1
specops status amend-task T001 --evidence "nonsense" --reason "y"; echo $?    # grammar → 1
specops status amend-task T001 --evidence "CLI_LOG: x" --reason ""; echo $?   # no reason → 1
specops status amend-task T999 --evidence "CLI_LOG: x" --reason "y"; echo $?  # unknown → 1
```

## Scenario 2 — Repoint the active feature (US2)

```bash
cat .specify/feature.json                # pointer on the finished feature
specops feature use specs/026-new-thing
specops consistency                      # now answers about 026-new-thing
```

**Expect**: the repoint reports old → new, lists artifacts not yet present, and
names any unfinished work left on the outgoing feature.

Initialization repoints automatically (FR-013):

```bash
mkdir -p specs/027-another && cp specs/026-new-thing/spec.md specs/027-another/
specops status init-spec
cat .specify/feature.json                # → specs/027-another, no hand edit
```

Spec Kit parity (FR-009a) and the override refusal (FR-010a):

```bash
export SPECIFY_FEATURE_DIRECTORY=specs/026-new-thing
specops status show                      # resolves 026-new-thing, not the pointer
specops feature use specs/027-another; echo $?   # refuses, names the override → 1
unset SPECIFY_FEATURE_DIRECTORY
```

**Expect**: with the override set, SpecOps resolves the same feature Spec Kit's
`common.ps1` would from identical repository state.

Inference is labelled, not silent (FR-014a):

```bash
mv .specify/feature.json /tmp/ && specops status show
```

**Expect**: the resolved-directory line carries the `(inferred — …)` suffix.
Restore the pointer afterwards.

## Scenario 3 — Renumber a feature (US3)

```bash
specops status show                      # record the task/evidence/review counts
git branch -m 026-new-thing 027-new-thing
specops feature rename specs/026-new-thing specs/027-new-thing --branch 027-new-thing
```

**Expect**: exit 0; output reports the directory move, the ledger identity change,
the `**Feature Branch**` header rewrite, whether the pointer followed, and every
remaining old-name reference with file and line — unchanged.

```bash
specops status show                      # identical counts, new identity
specops reconcile && specops consistency # both exit 0
git diff --stat                          # artifact prose untouched except spec.md's header
```

Refusals:

```bash
specops feature rename specs/027-new-thing specs/025-existing; echo $?  # target exists → 1
specops feature rename specs/999-nope specs/028-x; echo $?              # no source → 1

export SPECIFY_FEATURE_DIRECTORY=specs/027-new-thing
specops feature rename specs/027-new-thing specs/028-x; echo $?         # override names source → 1
unset SPECIFY_FEATURE_DIRECTORY
```

**Expect**: the last one refuses and names the override — completing it would leave
`SPECIFY_FEATURE_DIRECTORY`, which outranks the pointer file, aimed at a directory
that no longer exists.

## Scenario 4 — Legacy ledgers are unaffected (SC-011)

```bash
specops status migrate                   # v8 → v9 on an existing ledger
specops status show && specops reconcile && specops preflight
```

**Expect**: migration is a pure version bump — no task, evidence, acknowledgement,
or review-cycle record changes; every pre-existing command behaves identically.

## Full suite

```bash
conda run -n specops pytest -q
conda run -n specops mypy src/
conda run -n specops ruff check .
```
