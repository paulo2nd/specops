# Feature Specification: Hardening II — API & State Robustness

**Feature Branch**: `019-api-state-robustness`

**Created**: 2026-07-27

**Status**: Draft

**Input**: User description: "Complete the internal robustness pass deferred from Feature 018: decompose the long status transitions, type the ledger records, single-source the remaining duplicated parsers and gates, remove domain sentinels from generic git helpers, assert template-rendering completeness, simplify doctor's error flow, and fix the ledger-lock stale-reclaim race — all with zero user-visible behavior change."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Concurrent ledger access cannot double-grant the lock (Priority: P1)

Two SpecOps commands that touch the same ledger at the same time — for example an agent closing a task while a human runs a state-changing command, after an earlier process was killed and leaked its lock — never both believe they hold the exclusive lock. Today the stale-lock reclaim path checks the lock's age and then deletes-and-recreates it as two separate steps, so two waiting contenders can both observe "stale", both reclaim, and both proceed into the read-modify-write critical section.

**Why this priority**: this is the only item in the feature that is an actual defect rather than maintainability debt. The ledger is the product's core trust anchor (Repo-as-State); a double-granted lock risks a lost update in exactly the scenario locks exist for. The revision compare at save time bounds the damage, but "one of two writers fails late with a confusing revision error" is a symptom, not a design.

**Independent Test**: can be fully tested by a concurrency test in which multiple contenders race to reclaim a deliberately staled lock and exactly one wins — a test that demonstrably fails against the current implementation.

**Acceptance Scenarios**:

1. **Given** a lock file older than the stale threshold, **When** multiple contenders race to acquire the lock simultaneously, **Then** exactly one contender acquires it and all others wait or time out — never two holders.
2. **Given** a healthy (non-stale) lock held by a live process, **When** another command attempts to acquire it, **Then** the waiting behavior and timeout diagnostics are unchanged from today.
3. **Given** the fixed lock, **When** the full existing test suite runs, **Then** all lock-dependent behavior (acquire, release, timeout, reclaim after a genuine crash) is preserved with byte-identical command output.

---

### User Story 2 - State transitions read as named steps with one DONE gate (Priority: P2)

A maintainer changing how a phase transition or task completion works reads a short, named sequence of sub-steps instead of one long function, and the rule "approval is impossible while any blocking finding is unverified" exists in exactly one place. Today the phase-transition and task-completion flows are long monolithic functions, and the DONE gate is implemented twice verbatim — a future change to one copy would silently diverge the other, splitting the product's central approval invariant.

**Why this priority**: the duplicated DONE gate guards the ledger's most important invariant, and the long transition functions are where every future state-machine change lands. This is the highest-leverage maintainability item in the feature.

**Independent Test**: can be tested by verifying the blocking-approval gate has exactly one implementation consumed by every caller, and that the full suite passes with byte-identical behavior after the decomposition.

**Acceptance Scenarios**:

1. **Given** the decomposed flows, **When** any phase transition or task completion runs (success and every failure path), **Then** output, exit codes, and ledger writes are identical to the pre-change behavior.
2. **Given** a ledger with an unverified blocking finding, **When** a DONE transition is attempted through any path that enforces approval, **Then** all paths reject through the same single gate implementation with today's diagnostics.
3. **Given** a maintainer modifying transition behavior, **When** they locate the logic, **Then** each sub-step (validation, gate checks, record mutation, persistence) is a named unit rather than an inline block of a long function.

---

### User Story 3 - Internal contracts are typed, not conventions (Priority: P3)

A maintainer working with ledger records gets static, key-level checking — a typo in a record key or a wrongly-typed field is caught before tests run — and a caller of the handoff loader handles errors through a typed error path instead of probing the return value's class. Today ledger records are untyped dicts (a mistyped key is a silent bug), and the handoff mutation loader returns either the loaded state or an error result, forcing every one of its callers to repeat the same class-probing boilerplate.

**Why this priority**: typing is the safety net that makes this feature's own refactoring — and Feature 020's git-layer replacement next — verifiable statically. It prevents regressions rather than removing existing duplication.

**Independent Test**: can be tested by running the static type checker over the typed records (a seeded key typo must fail the check), scanning the loader's call sites for class-probing boilerplate (none may remain), and confirming serialized ledger output is byte-identical.

**Acceptance Scenarios**:

1. **Given** the typed ledger record schemas (tasks, findings, review cycles, evidence records), **When** the static type checker runs, **Then** it passes, and a deliberately mistyped record key fails the check.
2. **Given** the typed schemas, **When** any ledger is written and re-read, **Then** the serialized form is byte-identical to before — typing changes zero runtime behavior.
3. **Given** the typed handoff loader error path, **When** its call sites are scanned, **Then** no caller probes the result's class to distinguish success from error, and every error path preserves today's diagnostics and exit codes.

---

### User Story 4 - One authority for each remaining parser, sentinel, and rendering rule (Priority: P4)

A maintainer changing how diffs are parsed, how templates are scaffolded, or what fields a gate profile carries edits exactly one definition site. Today the `git diff --name-status` output is parsed by independent copies in the generic git layer and the lane path; the ledger's `(human)` commit sentinel leaks into generic git helpers that should know nothing about ledger conventions; template scaffolding silently leaves `{{...}}` residue in generated files if a template gains a placeholder the code doesn't fill; gate-profile field knowledge is spelled twice (lenient parse and validation) and can drift; and the doctor's error reporting threads exception objects through call arguments instead of a structured error flow.

**Why this priority**: valuable but lower urgency — these are the same class of silent-divergence risk Feature 018 retired elsewhere, none of which corrupts anything today.

**Independent Test**: can be tested by verifying each concern has exactly one implementation (diff parsing, sentinel filtering, placeholder completeness, gate-profile field table), by a template-drift test that proves scaffolding fails loudly instead of emitting `{{...}}` residue, and by the full suite passing unchanged.

**Acceptance Scenarios**:

1. **Given** the single diff parser, **When** the lane path and the generic git path each request a diff (with and without rename detection), **Then** both consume the same parser, parameterized for rename-awareness, with results identical to today's per-path parsing.
2. **Given** the sentinel moved out of the generic layer, **When** git helpers process commit values, **Then** they contain no `(human)` special-case — callers that need the exemption filter it — and every command that exempts `(human)` today still does.
3. **Given** a template containing a placeholder the scaffolding code does not fill, **When** scaffolding runs, **Then** it fails with a clear diagnostic naming the unfilled placeholder instead of writing a file with `{{...}}` residue.
4. **Given** the declarative gate-profile field table, **When** the lenient parser and the validator process a profile, **Then** both derive their field knowledge from the same table — a field added to one cannot be forgotten by the other.
5. **Given** the simplified doctor error flow, **When** a diagnostic check fails, **Then** the reported output and exit codes are identical to today's, without exception objects passed as call arguments.

### Edge Cases

- A lock leaked by a crashed process is reclaimed while a third process holds a fresh reclaim — the winner chain must never produce two simultaneous holders, even under repeated stale-reclaim cycles.
- A contender is killed between reclaiming the stale lock and releasing it — the new lock must itself become reclaimable by age, preserving today's crash recovery.
- The revision compare at ledger save time remains the durable authority — the lock fix must not weaken or replace it.
- A hand-edited ledger contains records with unexpected or missing keys — the typed schemas are a static-analysis contract only; runtime tolerance for malformed entries is unchanged.
- A diff contains rename entries (two-path lines) — the shared parser must handle them exactly as the rename-aware caller does today, while non-rename callers see today's simpler shape.
- A template legitimately needs literal `{{` in its output — the completeness assertion must distinguish unfilled known placeholders from intentional content (assumed: no current template needs literal `{{`; the assertion may treat any residue as drift).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ledger-lock stale-reclaim path MUST be race-free: when multiple contenders observe a stale lock, at most one may acquire it; all lock behavior (waiting, timeout, crash recovery) MUST otherwise be preserved. Whether this is achieved by hardening the in-tree lock or adopting a locking dependency is a plan-level decision; a new runtime dependency requires justification in the plan's Complexity Tracking.
- **FR-002**: A concurrency regression test MUST cover the stale-reclaim race and MUST fail against the pre-change implementation.
- **FR-003**: The phase-transition and task-completion flows MUST be decomposed into named sub-steps (validation, gate checks, record mutation, persistence), preserving every success and failure path byte-identically.
- **FR-004**: The blocking-findings approval gate (the DONE gate) MUST have exactly one implementation, consumed by every path that enforces it; the current verbatim duplicate MUST be eliminated.
- **FR-005**: Ledger records — tasks, findings, review cycles, and evidence records — MUST carry typed schemas giving the static type checker key-level verification, with zero change to the serialized ledger format.
- **FR-006**: The static type checker MUST pass over the typed records without new suppressions or overrides.
- **FR-007**: The handoff mutation loader MUST expose a typed error path; no caller may distinguish success from error by probing the result's class, and all error diagnostics and exit codes MUST be preserved.
- **FR-008**: Exactly one `git diff --name-status` parser MUST exist, with rename-awareness as a parameter, consumed by both the lane path and the generic git path.
- **FR-009**: Generic git helpers MUST contain no ledger-domain sentinel handling (the `(human)` commit value); callers that need the exemption MUST filter it themselves, and every command that exempts the sentinel today MUST continue to.
- **FR-010**: Template scaffolding MUST verify placeholder completeness: an unfilled `{{...}}` placeholder MUST produce a loud failure naming the placeholder, never a silently generated file containing residue.
- **FR-011**: Gate-profile field knowledge MUST be single-sourced in a declarative field table consumed by both the lenient parser and the validator.
- **FR-012**: The doctor's error reporting MUST use a structured error flow that does not thread exception objects as call arguments, preserving all diagnostics and exit codes.
- **FR-013**: The change set MUST produce zero user-visible change: byte-identical human and JSON output, identical exit codes, no ledger schema bump, and no new CLI surface.

### Key Entities

- **Ledger lock**: the short-lived exclusive lock guarding a ledger's read-modify-write section; its stale-reclaim transition becomes atomic (single-winner).
- **Ledger record schemas**: the typed shapes of task, finding, review-cycle, and evidence entries; a static contract over the unchanged serialized format.
- **DONE gate**: the single implementation of the blocking-findings approval invariant, shared by every enforcement path.
- **Handoff load outcome**: the typed result of loading handoff state for mutation — success state or typed error, never a class-probed union.
- **Diff entry**: the parsed representation of one `--name-status` line (status, path(s)), produced by the single shared parser with rename-awareness as a parameter.
- **Gate-profile field table**: the declarative single source of field names, types, and requiredness consumed by parse and validation alike.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A before/after capture of every CLI command's human and JSON output across the existing test scenarios shows zero differences — this feature has no sanctioned output delta.
- **SC-002**: The stale-reclaim concurrency test passes against the new lock and demonstrably fails against the old implementation; repeated runs (racing contenders over a staled lock) never produce two simultaneous holders.
- **SC-003**: Each previously duplicated or misplaced concern — the DONE gate, the `--name-status` parser, the sentinel special-case, gate-profile field knowledge — exists in exactly one place (baseline today: 2 copies each).
- **SC-004**: Zero call sites of the handoff mutation loader distinguish success from error by probing the result class (baseline today: 6+ sites).
- **SC-005**: The static type checker passes with key-level ledger record checking, and a seeded record-key typo is caught statically (baseline today: not caught).
- **SC-006**: A template-drift test proves scaffolding fails loudly on an unfilled placeholder (baseline today: silent `{{...}}` residue in the generated file).
- **SC-007**: The full test suite passes throughout, the ledger schema version is unchanged, and no serialized ledger byte differs for identical inputs.

## Assumptions

- The choice between hardening the in-tree lock and adopting a locking dependency is deliberately left to planning; the spec requires only the single-winner outcome and the constitution's Complexity Tracking justification if a dependency is chosen.
- The revision compare at ledger save time remains the durable write authority; the lock remains an in-process contention reducer, now race-free.
- Typed record schemas are a static-analysis contract, not runtime validation: tolerance for hand-edited or legacy ledger entries is governed by the existing validation paths and does not change.
- No current template legitimately emits literal `{{` content, so the completeness assertion may treat any `{{...}}` residue as drift.
- Internal decomposition and typed names are maintainer-facing contracts, not a supported external API: SpecOps' supported surface remains the CLI (same posture as Feature 018).
- The GitPython replacement is explicitly out of scope (Feature 020); this feature only refactors parsing and sentinel placement around the existing git layer, without changing what the git layer calls.
- No Self-Application (constitution v1.9.1) continues to hold: all verification happens through the automated test suite's fixtures, never by running `specops` against this repository.
