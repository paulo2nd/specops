# Feature Specification: Internal Hardening

**Feature Branch**: `018-internal-hardening`

**Created**: 2026-07-25

**Status**: Draft

**Input**: User description: "Internal Hardening: consolidate the duplicated internal infrastructure that accumulated across features 008–013 without changing any user-facing CLI behavior or output contracts. Scope: (1) unify TraceResult and HandoffResult as subclasses of outcome.CommandResult; (2) unify the five near-identical _emit_* helpers in cli.py; (3) promote the cross-module private API to explicit public contracts; (4) eliminate parallel ledger re-reads; (5) consolidate the evidence grammar into specops/evidence.py; (6) extract a single shared factory for finding record dicts and co-locate the finding-line parser and renderer; (7) test-suite debt: shared git helper, consolidated ledger builders, migrate subprocess integration tests to in-process CLI invocation. Constraints: zero behavior change (except acknowledged divergences that are themselves the bug), no new runtime dependencies, never reimplement what Spec Kit provides."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One place to define a command's result and output (Priority: P1)

A maintainer adding a new SpecOps command (or changing how an existing one reports status) edits a single shared result/emission mechanism instead of copying a per-feature result class and a per-command emit helper. Today the same result dataclass and the same emit function exist in five near-identical copies, and one copy (the workflow-lane one) has already silently diverged from the others.

**Why this priority**: this duplication is the root cause of every other copy in the list — each new feature (008, 010, 011, 012, 013) re-instantiated the pattern instead of consolidating it. Fixing it first makes every remaining story (and every future feature) cheaper, and it removes the one known output divergence.

**Independent Test**: can be fully tested by capturing the complete human and JSON output of every existing CLI command before and after the change and verifying they are identical — except the lane commands' JSON, which must gain the standard envelope fields it was missing (the acknowledged divergence being fixed).

**Acceptance Scenarios**:

1. **Given** the consolidated result mechanism, **When** any existing command (context, trace, handoff, gate, lane families) runs in human or `--json` mode, **Then** its output and exit code are byte-identical to the pre-change behavior.
2. **Given** a lane command run with `--json`, **When** the output is inspected, **Then** it carries the same envelope fields (output version and status) that every other command family already emits — the previously missing fields now present.
3. **Given** a maintainer adds a new command family, **When** they wire its results and output, **Then** they subclass the one shared result type and call the one shared emit function, with no new per-family copies required.

---

### User Story 2 - Module boundaries are explicit contracts (Priority: P2)

A maintainer refactoring one module can rely on naming to know what other modules depend on: helpers consumed across module boundaries carry public names with documented semantics, and underscore-prefixed names are genuinely private. Today 20+ production call sites import another module's underscore-prefixed helpers, so a local rename silently breaks neighbors.

**Why this priority**: it is the safety net for all other refactoring in this feature and after it — without explicit boundaries, every internal change risks silent breakage that only surfaces at runtime.

**Independent Test**: can be tested by statically scanning the production source tree for cross-module references to underscore-prefixed names and verifying the count is zero, while the full existing test suite still passes.

**Acceptance Scenarios**:

1. **Given** the promoted API, **When** the production source is scanned for imports or attribute accesses of another module's underscore-prefixed helpers, **Then** no such reference remains.
2. **Given** a helper promoted to a public name, **When** a maintainer reads its definition, **Then** its cross-module contract (inputs, outputs, error behavior) is documented at the definition site.
3. **Given** the promotion, **When** the full test suite runs, **Then** all tests pass with no behavior change in any command.

---

### User Story 3 - Single authority for shared grammars and records (Priority: P3)

A maintainer changing a shared data shape — the ledger document, the evidence string grammar, the finding record, or the finding line format — edits exactly one definition site, and parse/render pairs live together with a round-trip guarantee. Today the ledger is re-read by three independent code paths with divergent error messages, the evidence grammar is split across two modules, the finding record dict is built in three places (already diverging), and the finding-line parser and its inverse renderer live in different modules.

**Why this priority**: valuable but lower urgency — these duplications corrupt nothing today; they are the next silent divergences waiting to happen (one, the show/report divergence on hand-edited ledgers, already has).

**Independent Test**: can be tested by corrupting a ledger file and verifying every command that reads it reports the same diagnostic; and by a round-trip test that renders and re-parses finding lines through the co-located pair.

**Acceptance Scenarios**:

1. **Given** an unparsable ledger file, **When** any ledger-reading command runs (status show, status report, reconcile), **Then** all report the same diagnostic through the single shared loading path, with today's exit codes preserved.
2. **Given** a hand-edited ledger containing a non-mapping task entry, **When** the human status view and the machine report both run, **Then** they agree (the current divergence where one crashes and the other filters is resolved to the filtering behavior).
3. **Given** a finding created by any of the three creation paths (review authoring, external import preview, import apply), **When** the stored records are compared, **Then** they share one identical base shape produced by a single factory, with path-specific fields layered on top.
4. **Given** any valid finding, **When** it is rendered to its line format and parsed back, **Then** the round-trip is lossless — verified by a test that exercises the co-located parse/render pair.
5. **Given** the evidence grammar consolidated in its owning module, **When** evidence strings are validated at task close and at finding close, **Then** both paths use the same definition and accept/reject identically.

---

### User Story 4 - A test suite that is cheap to extend and fast to run (Priority: P4)

A contributor writing tests for a new feature reuses one shared git helper and one parametrized ledger builder from the shared fixtures, and their integration tests run in-process by default. Today the git helper is defined six times (one copy missing failure checking, so git errors pass silently), the ledger builders exist in three variants, and 17 integration files spawn the packaged binary per test, paying full interpreter startup each time.

**Why this priority**: developer-experience debt — it does not affect shipped behavior, but it taxes every future feature and lets test-setup failures hide.

**Independent Test**: can be tested by scanning the test tree for duplicate helper definitions (none may remain), verifying all git test helpers fail loudly on git errors, and comparing suite wall-clock time before and after the in-process migration.

**Acceptance Scenarios**:

1. **Given** the consolidated helpers, **When** the test tree is scanned, **Then** exactly one git helper definition exists (in the shared fixtures, failing loudly on git errors) and the local ledger-builder variants are gone in favor of the parametrized shared builders.
2. **Given** the in-process migration, **When** the integration suite runs, **Then** the migrated tests exercise commands in-process, a small explicitly-marked smoke set still spawns the real binary (covering true exit codes and streams), and total suite wall-clock time is measurably lower.
3. **Given** the full migrated suite, **When** it runs, **Then** coverage does not drop below the enforced project floor and no test asserts on internals that User Story 2 renamed without being updated to the public names.

### Edge Cases

- What happens when the lane JSON envelope gains its missing fields — does any consumer parse lane output today assuming the old shape? (Assumed additive-safe: fields are added, none removed or renamed; called out in the changelog as the one output delta.)
- How does the single ledger-loading path behave on a ledger that is valid YAML but not a mapping — all callers must converge on the same diagnostic and the same exit code that the canonical loader already uses.
- A finding imported from an external tool carries extra provenance fields — the shared factory must layer them without the base shape drifting between creation paths.
- A promoted public helper is also referenced by tests under its old private name — those references must be updated, not aliased, so the old names truly disappear.
- The subprocess smoke set must still catch what in-process invocation cannot: real exit codes, stream separation, and console encoding on Windows-class environments.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a single shared result abstraction for command outcomes; the trace and handoff result types MUST become specializations of it, eliminating their duplicated definitions and duplicated status-to-class mappings.
- **FR-002**: The system MUST provide a single shared output-emission function used by all command families (context, trace, handoff, gate, lane) for both human and JSON modes, replacing the five per-family copies.
- **FR-003**: All existing commands MUST produce byte-identical human output, JSON output, and exit codes after consolidation, with exactly one sanctioned exception: lane JSON output MUST gain the standard envelope fields (output version, status) it currently lacks. No field may be removed or renamed anywhere.
- **FR-004**: Every helper consumed across production module boundaries MUST carry a public (non-underscore) name with its contract documented at the definition site; after the change, zero cross-module references to underscore-prefixed names may remain in production code.
- **FR-005**: All ledger-reading code paths MUST delegate to the single canonical loading routine; no command may reimplement file-existence, parse, or structure checks, and all must surface the canonical diagnostics and exit codes.
- **FR-006**: The human status view MUST derive its counts and task listing from the same snapshot logic as the machine report, resolving the current divergence on hand-edited ledgers in favor of the tolerant (filtering) behavior.
- **FR-007**: The evidence-string grammar — validation and parsing — MUST live in the evidence module as its single owner; task-close and finding-close paths MUST consume it from there.
- **FR-008**: Finding records MUST be created through one shared factory defining the base shape; creation-path-specific fields (e.g., external-import provenance) MUST layer on top without duplicating the base.
- **FR-009**: The finding-line parse expression and its inverse renderer MUST be co-located in one module and covered by a lossless round-trip test.
- **FR-010**: The shared test fixtures MUST export exactly one git helper that fails loudly on git errors; all test files MUST use it, and duplicate definitions MUST be removed.
- **FR-011**: The shared test fixtures MUST provide parametrized ledger builders covering the variants currently duplicated locally; local builder copies MUST be removed.
- **FR-012**: Integration tests MUST run in-process by default; a small, explicitly marked smoke subset MUST continue to exercise the real installed binary for true exit codes and stream behavior.
- **FR-013**: The change set MUST introduce no new runtime dependency and MUST NOT reimplement any capability Spec Kit itself provides (SpecOps remains a deterministic ledger/gate layer plugging into Spec Kit).
- **FR-014**: Tests that referenced renamed internals MUST be updated to the public names; behavior-level tests MUST target the public surface rather than private helpers wherever the public surface expresses the same assertion.

### Key Entities

- **Command result**: the uniform outcome of a CLI invocation — command name, status, human-readable lines, structured extra data, derived output class and exit code. One definition, specialized per command family.
- **Output envelope**: the uniform JSON wrapper every command emits — output version, status, and payload. After this feature, lane commands emit it fully.
- **Ledger document**: the per-feature execution state file; read through exactly one loading routine that owns parse/structure diagnostics.
- **Evidence string**: the `<CLASS>:<summary>` grammar recorded at task and finding closure; owned by the evidence module.
- **Finding record**: the structured review finding stored in the ledger; base shape produced by one factory, with a line rendering and parser that round-trip losslessly.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A before/after capture of every CLI command's output (human and JSON) across the existing test scenarios shows zero differences, except the lane JSON envelope addition, which appears exactly as specified.
- **SC-002**: A static scan of production code finds zero cross-module references to underscore-prefixed helpers (baseline today: 20+ call sites).
- **SC-003**: Each of the previously duplicated definitions — result type, emit helper, ledger loading, evidence grammar, finding factory, finding-line parse/render, test git helper, test ledger builders — exists in exactly one place (baseline today: 2–6 copies each).
- **SC-004**: Corrupting a ledger file yields the identical diagnostic and exit code from every ledger-reading command.
- **SC-005**: Full test-suite wall-clock time drops measurably (target: at least 30% on the integration portion) after the in-process migration, with coverage still at or above the enforced project floor.
- **SC-006**: The full existing test suite passes throughout, and the changelog records exactly one behavior delta (the lane JSON envelope fields).

## Assumptions

- The lane JSON envelope addition is treated as fixing an acknowledged omission, not as a breaking change: fields are only added, and external consumers tolerating unknown fields are unaffected. It is the single documented output delta of this feature.
- The tolerant (filtering) behavior is the correct resolution for hand-edited ledgers with non-mapping entries, since the machine report already behaves that way and the ledger's own validation reports structural defects separately.
- Promoting helpers to public names is an internal-contract change, not a supported external API commitment: SpecOps' supported surface remains the CLI; the public names serve maintainers and tests, and their stability is governed by ordinary changelog discipline, not semver guarantees on Python imports.
- The subprocess smoke set is kept deliberately small (roughly one representative command per family) and explicitly marked, so the suite's default path is in-process.
- This feature deliberately excludes the separately-tracked bug issues (#23–#28) and any dependency changes (e.g., the GitPython removal candidate); overlaps (such as narrowing broad exception handlers) stay with their issues.
- No Self-Application (constitution v1.9.0) continues to hold: all verification happens through the automated test suite's fixtures, never by running `specops` against this repository.
