# Feature Specification: Test Execution Only at the Review Gate

**Feature Branch**: `024-proportional-test-evidence`

**Created**: 2026-08-01

**Status**: Draft

**Input**: User description: "Make the SpecOps workflow stop running the target project's test suite redundantly within a single feature run. Today a full run executes the suite U+2 times (once per user story via `complete-task --auto`, once in the soft review gate, once again in the terminal gate). Move all test execution to the review gate: closing a user story records only diff/commit evidence and runs no tests, and the terminal gate reuses the soft gate's already-computed full-suite result instead of re-running it. Test execution during development is dropped entirely — the agent writes and commits a story's code before any test would run, so on the happy path a per-story test is purely confirmatory and only adds cost; the gate remains the single point of test enforcement."

## Clarifications

### Session 2026-08-01

- Q: How is a stale cache hit prevented when the working tree changed but the commit range did not? → A: Include a working-tree digest (a hash of the uncommitted diff, or a `clean` marker) in the gate-run cache key, so any change — committed or not — invalidates reuse.
- Q: Which gates participate in cache reuse? → A: Only the command-executing gates (`lint`, `test`); state-derived gates (`reconcile`, `working-tree`, `drift`) always recompute from the current tree and are never cached.
- Q: How is accumulation of gate-run evidence records handled on each execution? → A: Supersede by cache key — activate Feature 012's latent `append_record(supersede=True)` so the latest run per key is retained and prior records are marked `superseded_by` (traceable, bounded growth).

### Session 2026-08-01 (implementation pivot)

- Q: Persisting gate-run evidence into the committed `status.yaml` dirties the working tree, which the `working-tree` gate rejects — where should the cache live? → A: **Not in the ledger.** The gate-run cache is ephemeral, tree-scoped local state; store it inside the git directory (`<git-dir>/specops/gate-cache/<feature>.yaml`), invisible to `git status` and to the working tree. Consequences: `preflight` stays **fully** read-only with respect to the ledger (Principle IV needs **no** amendment and the read-only ledger/tree contract is unchanged); gate runs are intentionally **not** part of the committed cross-clone audit trail (acceptable — they are reproducible, and the durable audit remains the review verdict plus `complete-task` task evidence). The `worktree_digest`, cache-key, and supersede mechanics are unchanged; only the storage location moved out of the ledger.

## User Scenarios & Testing *(mandatory)*

The actors are the **adopting developer** (who configures SpecOps in a client repository and pays the cost of every test execution in dev-loop and CI time) and the **conducting agent** (which drives the workflow and records evidence). "Value" here is wall-clock and compute spent re-running a suite that has not changed, with the guarantee that the review gate remains the single, complete correctness check that nothing bypasses.

### User Story 1 - The full suite stops running twice back-to-back per corrective round (Priority: P1)

Within a single corrective-loop iteration the soft review gate and the terminal gate today each execute the identical full test suite over the identical working tree, one immediately after the other. The adopting developer wants the terminal gate to reuse the result the soft gate just produced when nothing relevant has changed, so the suite runs once per round instead of twice.

**Why this priority**: This is the most clearly redundant execution in the workflow — same command, same tree, back-to-back — and removing it is a pure de-duplication with no change to what evidence means. It is the largest safe win and directly answers the reported problem ("is SpecOps forcing the tests to run multiple times?"). It is a viable standalone MVP: shipping only this already removes one of the two back-to-back full-suite runs.

**Independent Test**: On an unchanged working tree, run the gate suite twice in succession. Confirm the second run does not re-execute the test command and instead reports the test gate with a "reused/cached" disposition backed by the first run's evidence record. Then make a change to the tree and confirm the next gate run re-executes (no stale reuse).

**Acceptance Scenarios**:

1. **Given** a soft review gate has just executed the full test suite and recorded its result, **When** the terminal gate runs over the same commit range, affected paths, and gate command with no intervening tree change, **Then** the terminal gate reports the test gate as reused (cached) and does not execute the test command a second time.
2. **Given** the corrective loop made code edits after the soft review gate (committed or not), **When** the terminal gate runs, **Then** the working-tree digest in the cache key no longer matches and the test gate re-executes over the new tree.
3. **Given** a gate suite run, **When** it records its gate-run evidence, **Then** it appends evidence records only and leaves every existing task, phase, and finding record in the ledger byte-identical.

---

### User Story 2 - Closing a user story runs no tests (Priority: P2)

When the conducting agent closes the final task of a user story with `--auto`, SpecOps today runs the client's full `test_command`. For a feature with several user stories this multiplies the full suite across the run. The adopting developer wants per-story closing to record only mechanical diff and commit evidence and run no tests at all, leaving every test execution to the review gate.

**Why this priority**: This removes the U-fold multiplication for multi-story features. It ranks below US1 because it changes what `--auto` does at the boundary between development and review; US1 changes nothing semantically. On the happy path the removed per-story test is purely confirmatory (the story's code is already written and committed before it would run), so dropping it costs nothing in correctness — the gate remains the single, complete enforcement point.

**Independent Test**: Close a user story's final task with `--auto` and confirm no test command is invoked, while the diff and commit evidence for the story is still recorded mechanically (not agent-narrated).

**Acceptance Scenarios**:

1. **Given** any client repository, **When** the agent closes a user story's final task with `--auto`, **Then** SpecOps records the story's code-diff and commit evidence mechanically and runs no test command.
2. **Given** a user story is closed with `--auto` and no test ran, **When** the workflow later reaches the review gate, **Then** the full test suite runs (or is reused per US1) as the single test-enforcement point, and no story is considered test-verified before the gate.
3. **Given** a user story whose final task is closed with `--auto`, **When** the evidence is inspected, **Then** it is unambiguously identifiable as development-phase evidence (diff/commit provenance) rather than a test result.

---

### Edge Cases

- **Tree changes mid-loop**: if the corrective loop edits code between the soft gate and the terminal gate, reuse must not happen — the terminal gate must re-execute against the new tree. Reuse is correct only when the full cache key (command, commit range, affected paths, context-map digest, working-tree digest) is unchanged. An uncommitted edit changes the working-tree digest and therefore invalidates reuse even if no new commit was made.
- **Empty changed-file set at close**: closing a story whose diff is empty still records commit/provenance evidence (or an explicit note) and runs nothing.
- **Bounded evidence growth**: each command-running gate execution supersedes the prior record for the same cache key (`superseded_by`) rather than appending indefinitely; the ledger retains the latest run per key while preserving the audit trail of superseded records.
- **State-derived gates are never cached**: `reconcile`, `working-tree`, and `drift` recompute every run from the current tree; only `lint` and `test` are cacheable. A lint gate reuse must never be mistaken for a test gate result.

## Requirements *(mandatory)*

### Functional Requirements

**Terminal-gate reuse / cache activation (US1)**

- **FR-001**: The review/preflight gate suite MUST persist each executed command-running gate's run as a structured evidence record identified as a gate producer (distinct from the `auto` task-evidence producer), so a later identical gate run can find and reuse it. The record is stored in an **ephemeral, git-directory-local cache** (`<git-dir>/specops/gate-cache/<feature>.yaml`), never in the committed ledger. Persistence MUST supersede any prior record sharing the same producer/cache key (marking it `superseded_by`) rather than accumulate unbounded, retaining only the latest run per key while keeping superseded records traceable within the cache.
- **FR-002**: A gate MUST reuse a prior gate-run cache record instead of executing its command when the cache key matches (same producer, command, commit range, affected paths, context-map digest, and working-tree digest), and MUST report that outcome with the reused/cached disposition.
- **FR-003**: When the working tree (including uncommitted changes), commit range, gate command, or covered paths differ from a prior gate-run record, the gate MUST execute its command (reuse MUST NOT occur). The cache key MUST incorporate a working-tree digest (a hash of the uncommitted diff, or an explicit `clean` marker) so that a change to the tree invalidates reuse even when the commit range is unchanged.
- **FR-003a**: Only command-executing gates (`lint`, `test`) participate in cache reuse. State-derived gates (`reconcile`, `working-tree`, `drift`) MUST always recompute from the current tree and MUST NOT be served from cache.
- **FR-004**: `preflight`/`review` MUST remain **read-only with respect to the committed repository**: they make no ledger writes and leave the working tree byte-identical (the gate-run cache lives inside the git directory, so it never appears in the working tree or `git status`). The existing byte-for-byte read-only contract for the ledger and tree is preserved and MUST stay covered by tests.
- **FR-005**: The terminal gate MUST reuse the soft review gate's full-suite result within the same corrective-loop iteration when nothing relevant has changed, so the full suite executes at most once per iteration.

**No test execution during development (US2)**

- **FR-006**: Closing a user story's final task with `--auto` MUST NOT run the client's `test_command` or any other test command.
- **FR-007**: Closing a user story's final task with `--auto` MUST still collect and record the story's commit hashes and code-diff evidence mechanically (not dependent on agent narration), preserving automated evidence collection for development-phase provenance.
- **FR-008**: The review gate MUST remain the single point of test enforcement; correctness enforcement MUST be unchanged in strength — no change may merge or reach DONE without a passing full-suite gate result.

**Compatibility & non-goals**

- **FR-009**: Existing ledgers and evidence records MUST remain readable; any schema change required to persist gate-run evidence MUST be additive and MUST preserve all prior records without loss.
- **FR-010**: SpecOps MUST remain agnostic to test frameworks and result formats; this feature MUST NOT add any framework-specific test-selection or coverage logic. Targeted/impacted per-story testing is explicitly out of scope (see Assumptions).

### Key Entities *(include if feature involves data)*

- **Gate-run cache record**: an evidence-shaped record produced by a command-executing gate (`lint`, `test`), stored in the ephemeral git-directory-local cache (`<git-dir>/specops/gate-cache/<feature>.yaml`), identified by a gate-scoped producer and a cache key derived from command, commit range, affected paths, context-map digest, and working-tree digest; enables a later identical gate run to reuse it rather than re-execute. A new run supersedes the prior record for the same producer (`superseded_by`), keeping the latest run per key while preserving the superseded trail within the cache.
- **Development-phase completion evidence**: the code-diff and commit provenance recorded mechanically when a user story is closed with `--auto`; carries no test result, because test enforcement lives entirely at the gate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the happy path (one corrective-loop iteration, APPROVED) for a single-user-story feature, the full test suite executes exactly once during the run (down from three today).
- **SC-002**: On the happy path for a feature with U user stories, the full test suite executes exactly once and zero per-story test runs occur (down from U+2 today).
- **SC-003**: Running the gate suite twice over an unchanged working tree executes each gate's command exactly once; the second run reports every gate as reused (cached).
- **SC-004**: Closing any user story with `--auto` invokes no test command, and the story's commit and code-diff evidence is still recorded mechanically.
- **SC-005**: Across any review/preflight run, the committed ledger and the working tree remain byte-identical before and after (the gate-run cache lives inside the git directory and never touches either).
- **SC-006**: No change reaches DONE without a passing full-suite gate result (correctness enforcement is preserved despite the removal of development-phase testing).

## Assumptions

- **Decision resolved — test only at the gate**: Test execution is removed from the development phase entirely; there is no per-story test run and no opt-in targeted run. This was chosen deliberately over requiring per-story tests or an optional impacted-test command, because on the happy path a per-story test is purely confirmatory (the story's code is already written and committed before it would run) and the review gate already guarantees a complete correctness check that nothing bypasses.
- **Governance impact**: This feature narrows **one** constitution directive — Principle III ("`complete-task --auto` … run the client's `test_command` … including the `TEST_REPORT`") becomes "`--auto` collects commit and code-diff evidence only and runs no test." Principle IV's "`specops preflight` stays byte-for-byte read-only" is **unchanged** (the gate-run cache lives in the git directory, so preflight still writes nothing to the ledger or working tree). The Principle III change is a broadening, not a removal; the never-destructive intent is preserved.
- **Deferred capability**: Targeted/impacted per-story testing for fail-fast failure localization is intentionally deferred (YAGNI — no adopter has requested it, and impacted-test tooling is framework-specific and unevenly available). If a future need appears, it can be reintroduced as an optional client-provided command that receives the story's changed-file set, without SpecOps performing any framework-specific selection itself.
- **Domain agnosticism preserved**: No test-framework-specific behavior is added; the review gate continues to run the client's configured commands opaquely (Principle V).
- **Ledger schema**: The ledger is currently at v7; persisting gate-run evidence is expected to be additive (existing records preserved). No scope/partial-evidence marker is needed because all recorded test evidence now originates from full-suite gate runs.
- **Self-application constraint**: SpecOps is not run against its own repository; this feature is developed with plain Speckit artifacts and verified through the project's own unit/integration test suite, not by conducting a SpecOps ledger over the SpecOps repo.
- **Cache machinery already exists**: The structured-evidence cache-key/id/supersession machinery shipped in Feature 012 but has been inert end-to-end because review never persisted gate evidence; this feature activates it rather than building it from scratch.
