# Feature Specification: Gate Rename & Vocabulary Pass

**Feature Branch**: `017-gate-rename-vocabulary`

**Created**: 2026-07-24

**Status**: Draft

**Input**: User description: "Rename the deterministic review gate `specops review → specops preflight`, retaining `specops review` as a deprecated alias with a stderr notice for a defined window, and reserve \"review\" for the phase, the `/specops-review` directive, and the verdict. Update the workflow definition, directives, constitution, and EN/PT docs, and sweep for other overloaded terms as a pre-1.0 vocabulary pass — behavior unchanged, no breaking removal in this feature."

## Clarifications

### Session 2026-07-24

- Q: How aggressively should the vocabulary sweep rename user-facing terms beyond the gate? → A: Conservative — rename only the gate (`review → preflight`); for every other overloaded term the sweep finds, document the rationale rather than rename it. At most this one rename+alias ships in this feature.
- Q: Can the `review` alias's deprecation notice be suppressed (given the loop and CI call it repeatedly)? → A: No — always emit exactly one stderr line per alias invocation, with no suppression flag or environment variable. It stays stderr-only (stdout/JSON clean), so repeated calls never break automation; the migration path is to move callers to `preflight`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The mechanical gate has an honest name (Priority: P1)

A workflow/directive author composing a SpecOps-augmented lifecycle invokes the deterministic verification suite by a name that says what it does: `specops preflight`. It runs the same mechanical checks the gate has always run (reconcile, gate profiles / lint+test, working-tree, drift) and returns the same verdict and exit code. Because the primitive is now named for what it is — a pre-flight mechanical check, not a code review — the author is no longer led to believe that invoking it performs the semantic review (the exact miscomposition that produced the Feature 016 gap).

**Why this priority**: This is the correction the feature exists to make. The audience for the command name is the composing author, and a primitive named `review` that only *gates* invites workflows that skip the actual review. Renaming it to `preflight` is the whole point; every other story supports or protects this one.

**Independent Test**: Run `specops preflight` against a fixture repository in a known state and confirm it executes the full deterministic gate suite and returns the same verdict, exit code, and stdout (modulo the command-label value) as the pre-rename `specops review` for the identical state.

**Acceptance Scenarios**:

1. **Given** a repository whose state passes every mechanical gate, **When** `specops preflight` runs, **Then** it reports an APPROVED verdict and exits zero, identically to the pre-rename gate.
2. **Given** a repository that fails a mechanical gate (e.g., drift or a required gate-profile failure), **When** `specops preflight` runs in its terminal (hard) mode, **Then** it reports a non-APPROVED verdict and exits non-zero, identically to the pre-rename gate.
3. **Given** the soft loop mode, **When** `specops preflight --json --soft` runs, **Then** it emits the verdict in machine-readable output and exits zero, matching the pre-rename `specops review --json --soft`.

---

### User Story 2 - Existing invocations keep working via a deprecated alias (Priority: P1)

A team whose installed workflow steps, scripts, or CI already call `specops review` upgrades SpecOps and nothing breaks. `specops review` continues to run the identical gate suite with the identical stdout and exit code; the only difference is a single-line deprecation notice on stderr telling the author to migrate to `specops preflight`. The alias is not removed in this feature — it ships and stays for a defined window — so upgrading never forces an immediate rewrite.

**Why this priority**: The rename is worthless if it breaks every existing consumer on upgrade. The alias is what makes the rename shippable without a breaking change, so it is co-equal P1 with Story 1: together they are the minimum viable feature.

**Independent Test**: Run `specops review` against the same fixtures as Story 1 and confirm stdout and exit codes are byte-identical to the pre-rename behavior, with exactly one deprecation line appearing on stderr and none on stdout.

**Acceptance Scenarios**:

1. **Given** any repository state, **When** `specops review` runs, **Then** its stdout and exit code are identical to `specops preflight` for that state, and exactly one deprecation notice is written to stderr.
2. **Given** a machine consumer that parses `specops review --json` stdout, **When** it reads the output, **Then** stdout is still valid, byte-identical JSON with no deprecation text mixed in (the notice is stderr-only).
3. **Given** this feature's change set, **When** the release ships, **Then** the `review` alias is present and functional and is **not** removed (removal is deferred to a later feature no earlier than the next MINOR release).

---

### User Story 3 - Shipped artifacts teach the honest name (Priority: P2)

A team reading the shipped workflow definition, the directive templates, the constitution, or the EN/PT documentation sees the deterministic gate referred to as `preflight` and sees "review" used only where a genuine review is meant — the REVIEW phase, the `/specops-review` directive, and the review-cycle verdict. Composing against these artifacts therefore reproduces the correct shape (mechanical `preflight` precondition, then the semantic review), not the miscomposed one.

**Why this priority**: The rename's benefit reaches authors mainly through the artifacts they copy and compose against. If the shipped `workflow.yml` and directives still say "review" for the gate, the honest name never reaches the audience that needs it. Important, but the runtime rename and alias (Stories 1–2) must land first.

**Independent Test**: Inspect the shipped `workflow.yml`, directive templates, constitution, and EN/PT docs and confirm every reference to the deterministic gate uses `preflight`, every legitimate "review" (phase/directive/verdict) is preserved, and the workflow definition still validates and runs unchanged against the workflow engine.

**Acceptance Scenarios**:

1. **Given** the shipped workflow definition, **When** it is inspected, **Then** every gate step (both the soft loop call and the hard terminal gate) invokes `specops preflight`, and the definition validates and runs without error.
2. **Given** the constitution and directive templates, **When** they are inspected, **Then** the deterministic gate is named `preflight` and no principle is removed or redefined (a naming amendment only).
3. **Given** the EN and PT documentation, **When** the sections describing the gate and its alias are compared, **Then** they are behaviorally equivalent (no divergence in described outcomes).

---

### User Story 4 - Other overloaded terms are corrected or documented (Priority: P3)

Because this is the last cheap moment before 1.0 to fix vocabulary, the feature sweeps the user-facing surface for other terms that mislead a composing author. The sweep is **conservative**: the gate (`review → preflight`) is the only rename this feature ships; every other overloaded term found is *documented* with a rationale rather than renamed, keeping the deprecation footprint minimal. Nothing misleading is left silently in place — but nothing beyond the gate is renamed here.

**Why this priority**: A deliberate pre-1.0 hygiene pass with real value, but strictly additive to the core gate rename. It can ship in the same change set or be scoped down without invalidating Stories 1–3.

**Independent Test**: Review the catalogue of user-facing terms produced by the sweep and confirm each identified overloaded term has a recorded disposition (renamed with alias, or documented), with zero identified terms left unaddressed.

**Acceptance Scenarios**:

1. **Given** the conservative vocabulary sweep, **When** an overloaded user-facing term other than the gate is identified, **Then** it is documented with an explicit rationale and is **not** renamed in this feature.
2. **Given** the sweep completes, **When** its catalogue is reviewed, **Then** the gate is the only renamed term and every other identified term carries a recorded disposition of "documented".

---

### Edge Cases

- **Older installed `workflow.yml` still says `specops review`**: it keeps working through the alias; upgrading does not force a workflow reinstall or rewrite.
- **`specops review --json` piped to a parser**: the deprecation notice is stderr-only, so stdout remains byte-identical valid JSON and the parser is unaffected.
- **Over-correction risk**: the sweep MUST NOT rename occurrences of "review" that correctly denote the REVIEW phase, the `/specops-review` directive, or the review-cycle verdict — only the misnamed deterministic gate (and other genuinely misleading terms) is renamed.
- **Persisted-key collision**: the rename MUST NOT touch persisted ledger fields, review-cycle records, the `REVIEW` phase identifier, verdict values (`APPROVED`/`REJECTED`), or any JSON key Features 011–016 bind to — only the command name and its output command-label value change.
- **Both names present in help/catalog**: listing surfaces present `preflight` as canonical and mark `review` as deprecated, so an author discovering the CLI is steered to the honest name.
- **Alias removal after the window**: out of scope here; a run relying on the alias after its removal window is a later feature's concern, and this feature guarantees only that the alias ships and survives the window.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a `specops preflight` command that runs the identical deterministic gate suite currently run by `specops review` (reconcile, gate profiles / lint+test, working-tree, drift), with the same verdict semantics, exit codes, flags, and output modes — behavior unchanged, naming only.
- **FR-002**: The system MUST retain `specops review` as a deprecated alias of `specops preflight` with identical behavior and exit codes, differing only by a single-line deprecation notice. The notice MUST be emitted on every alias invocation and MUST NOT be suppressible by any flag or environment variable; repeated invocations (the corrective loop, CI) each emit exactly one line.
- **FR-003**: The deprecation notice MUST be written to stderr only. Stdout — including `--json` output — MUST remain byte-identical to the pre-rename `specops review` output for the same repository state, so machine consumers that parse stdout are unaffected.
- **FR-004**: The command-label value in human and machine output MUST mirror the invoked name — a run invoked as `preflight` reports `preflight`, a run invoked via the `review` alias reports `review` — so existing `specops review` consumers observe no stdout change while new consumers receive the honest name.
- **FR-005**: `specops preflight` MUST support every flag, option, and invocation mode of the current `specops review`, notably `--json`, `--soft` (the soft, verdict-in-output, always-zero-exit loop mode), and the hard terminal mode that exits non-zero on a non-APPROVED verdict.
- **FR-006**: The `review` alias MUST NOT be removed by this feature. It MUST ship and remain functional for at least the deprecation window (removed no earlier than the next MINOR release and never in a patch); the removal itself is a separate future change.
- **FR-007**: The shipped Feature 007 workflow definition MUST invoke the gate as `specops preflight` in every gate step — both the soft loop call and the hard terminal gate — and MUST validate and run unchanged against the workflow engine.
- **FR-008**: The directive templates that reference the deterministic gate MUST refer to `specops preflight`, while continuing to reserve "review" for the REVIEW phase, the `/specops-review` directive, and the review-cycle verdict.
- **FR-009**: The constitution MUST be updated so every reference to the deterministic gate uses `preflight` and "review" is reserved for the phase/directive/verdict, with no principle removed or redefined (a naming amendment only).
- **FR-010**: EN and PT documentation MUST be updated in the same change set and remain behaviorally equivalent, describing `specops preflight` as the mechanical gate and `specops review` as its deprecated alias.
- **FR-011**: The rename MUST NOT change any persisted ledger field, review-cycle record, phase identifier (`REVIEW`), verdict value (`APPROVED`/`REJECTED`), or JSON key that Features 011–016 already bind to; only the command name and its invoked-name-mirroring output label change (per FR-004).
- **FR-012**: The feature MUST perform a **conservative** vocabulary sweep of the user-facing surface (command and subcommand names, directive and documentation language a composing author reads) for other overloaded terms that mislead composition. The gate (`review → preflight`) is the only rename this feature ships; every other identified term MUST be documented with an explicit rationale rather than renamed. Internal code identifiers with no user-facing surface are out of scope.
- **FR-013**: The sweep MUST NOT rename occurrences of "review" that correctly denote the REVIEW phase, the `/specops-review` directive, or the review-cycle verdict; only genuinely misleading user-facing terms are renamed.
- **FR-014**: Help, catalogue, and command-listing surfaces MUST present `preflight` as the canonical command and clearly mark `review` (and any other alias produced by the sweep) as deprecated.
- **FR-015**: The changelog MUST record the rename, the alias and its deprecation window, that behavior is unchanged, and any migration guidance for consumers moving to the new name.

### Key Entities *(include if feature involves data)*

- **Deterministic gate command**: the mechanical verification suite (reconcile, gate profiles / lint+test, working-tree, drift); canonical name changes from `specops review` to `specops preflight`, behavior unchanged.
- **Deprecated alias**: `specops review`, retained as a behavior-identical alias of `specops preflight` that additionally emits one deprecation line on stderr and survives a defined window.
- **Reserved "review" vocabulary**: the REVIEW phase, the `/specops-review` directive, and the review-cycle verdict (`APPROVED`/`REJECTED`) — genuinely named "review" and left unchanged.
- **Shipped artifacts referencing the gate**: the Feature 007 workflow definition, the directive templates, the constitution, and the EN/PT documentation, all updated to name the gate `preflight`.
- **Deprecation window**: the release span the alias must survive — at least until the next MINOR release, never removed in a patch — with actual removal deferred to a later feature.
- **Vocabulary sweep catalogue**: the recorded set of user-facing overloaded terms found by the sweep, each with a disposition; under the conservative policy the gate is the only "renamed" entry and all others are "documented".

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For the same repository state, `specops preflight` produces a result byte-identical to the pre-rename `specops review` — same verdict, same exit code, same stdout except the invoked-name-mirroring command label — in 100% of parity fixture runs.
- **SC-002**: `specops review` produces stdout and exit codes identical to `specops preflight` for the same state in 100% of alias fixture runs, with exactly one deprecation line on stderr and zero deprecation output on stdout.
- **SC-003**: The shipped workflow definition invokes `preflight` in every gate step and validates and runs unchanged, with zero validation errors and zero workflow-step regressions.
- **SC-004**: The complete existing test suite (CLI, workflow, corrective-handoff, JSON contracts) passes with zero regressions attributable to the rename.
- **SC-005**: A comparison of persisted ledger/handoff schemas, phase identifiers, verdict values, and JSON keys before and after the change shows zero renamed keys or values that downstream consumers bind to.
- **SC-006**: The shipped `workflow.yml`, directive templates, constitution, and EN/PT docs contain zero references to the deterministic gate as "review" (all use `preflight`), while 100% of legitimate "review" usages (phase/directive/verdict) are preserved — verified by review.
- **SC-007**: The EN and PT sections describing the gate and its alias are behaviorally equivalent with zero divergence in described outcomes — verified by review.
- **SC-008**: Every user-facing overloaded term identified by the vocabulary sweep has a recorded disposition, with zero identified terms left unaddressed; the gate is the only term renamed and 100% of other identified terms carry a "documented" disposition (conservative-sweep invariant).

## Assumptions

- The deterministic gate is today the `specops review` command; renaming it to `preflight` is purely a naming change with no change to the gate's logic or verdict semantics (roadmap non-goal: no behavior change).
- Machine consumers of the gate parse stdout only; a deprecation notice on stderr therefore does not affect them, which is the basis for the stderr-only requirement (FR-003).
- Mirroring the output command label to the invoked name (FR-004) is the least-breaking default: `specops review` output stays byte-stable for existing consumers and `specops preflight` reports the honest name — preferred over forcing all output to the new value during the deprecation window.
- The deprecation window is governed by the release policy (removed no earlier than the next MINOR, never in a patch); the actual removal of the alias is a separate, later feature and is out of scope here.
- The vocabulary sweep targets the surface a composing author reads (command/subcommand names, directives, documentation); internal code identifiers without a user-facing surface are out of scope unless exposed to users.
- Features 011–016 bind to persisted keys, the `REVIEW` phase, verdict values, and the corrective-handoff report — none of which this feature renames; this feature changes only the command name and its invoked-name-mirroring output label.
- No new capability, flag, or runtime behavior is added; this feature is naming hygiene only, and it does not depend on any other unmerged feature.
