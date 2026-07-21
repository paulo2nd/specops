# Feature Specification: Context Map Core

**Feature Branch**: `008-context-map-core`

**Created**: 2026-07-20

**Status**: Draft

**Input**: User description: "Add a generic, versioned SpecOps context map with deterministic path and ID resolution, phase-specific read sets, ownership, dependencies, gates, and risk metadata. Provide init, validate, resolve, explain, and JSON interfaces while keeping the core stack-neutral and safe when no map exists."

## Complement Boundary *(mandatory context)*

SpecOps runs **inside** Spec Kit and is a **complement**, never a replacement (Constitution Principle I). Spec Kit ships a workflow engine, artifacts (`spec.md`, `plan.md`, `tasks.md`), gates, and a preset/extension system, but it ships **no** repository context map: there is no native description of which repository areas exist, who owns them, which files an agent should read at each lifecycle phase, how areas depend on one another, or what risk and gate policy applies to a change. This feature adds exactly that missing layer under the SpecOps-owned namespace, and nothing Spec Kit already provides.

Therefore this feature does **not** parse source code, infer dependencies, register a Spec Kit workflow step, or run any planning/review integration. It contributes only:

1. A **versioned, stack-neutral context map schema** authored under the SpecOps namespace in `.specify`.
2. Four **read-only CLI commands** — `context init`, `context validate`, `context resolve`, `context explain` — that create, check, and deterministically interpret the map.
3. A stable **JSON contract** for every read-only command so downstream features (008 → 009) and automation can consume the resolved context package without re-deriving it.

Consumption of the resolved context by planning, implementation, and review is explicitly deferred to Feature 009. This feature is the deterministic, self-contained foundation those later features build on.

## Clarifications

### Session 2026-07-20

- Q: How does a Context claim repository paths, and how are overlapping matches resolved deterministically? → A: **Glob patterns, most-specific wins.** Contexts declare gitignore-style glob patterns relative to the repository root; on overlap the most specific pattern wins (fewer wildcards / longer literal prefix). A genuine equal-specificity tie claiming the same path is reported as **ambiguous ownership** and fails validation (fail closed), never silently resolved.
- Q: What does a resolved context package contain for a context that declares dependencies on other contexts? → A: **Dependency edges plus the transitive read sets they pull in.** The package lists the dependency edges and includes a deduplicated, deterministically ordered expanded read set drawn from dependency contexts, with each pulled-in entry attributable to its originating edge in the reason trace. Expansion is cycle-safe.
- Q: In FR-005, what does "invalid/non-existent paths" mean for `context validate`? → A: **Syntactic and safety validation only — no filesystem check.** A path pattern is invalid only when it is malformed or unsafe (escapes the repository root via traversal or absolute path). A well-formed, in-repo pattern that currently matches zero files on disk is **valid**; validation stays deterministic and independent of current worktree contents.
- Q: When a context declares no read set for the requested lifecycle phase, what does resolution return? → A: **Inherit a phase-agnostic `base` read set.** Each context may declare a `base` read set; a phase with no specific set inherits `base`, and `context explain` states that the fallback was used. When no `base` is declared either, the phase resolves to an explicit empty read set (distinct from "no matching context").
- Q: What exit-code contract should the context commands expose across all outcomes? → A: **Small fixed taxonomy `0` / `1` / `2` plus a stable `status` field.** `0` = success (including the supported "absent map" and "no matching context" reads); `1` = blocking / fail-closed (invalid, ambiguous, malformed, or unsupported-version map); `2` = usage/input error (bad arguments). The fine-grained outcome (the five map states, no-match, resolved) is carried in a stable `status` field in the output, so exit codes stay minimal (Principle VI) while FR-013/FR-018 supported states remain non-errors.
- Q: How is glob "specificity" defined as a total, deterministic order for most-specific-wins? → A: **Documented comparator tuple; genuine ties are errors.** Specificity is compared in order: (1) longer literal prefix, then (2) fewer wildcard tokens, then (3) more path segments. If two different contexts tie on all three for a given path, that is the ambiguous-ownership validation error — never broken silently.
- Q: How strictly should `context validate` check dependency edges and gate/policy references? → A: **Dependency edges strict; gate references structural only.** A dependency edge referencing an unknown context ID is a distinct validation error (dangling dependency), required for safe deterministic transitive expansion. Gate/policy references are validated for well-formedness (structure/type) only, not resolvability, because the gate system arrives in Feature 012 — 008 does not couple to it.
- Q: How do `resolve`/`explain` accept the target — a repository path vs a context ID? → A: **Explicit `--path` / `--id` selectors.** Supplying both, or neither, is a usage error (exit `2`). This removes all ambiguity (an ID containing a slash can never be misread as a path) and makes the input contract deterministic and testable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Author and validate a context map (Priority: P1)

A maintainer of a Spec Kit repository wants to describe the repository's structure so that later SpecOps features can give agents the right, minimal context. They scaffold a starter map, edit it to describe their repository's areas, and validate it before anyone relies on it.

**Why this priority**: Without a valid map there is nothing to resolve or explain. Authoring and validation is the irreducible MVP — it delivers standalone value (a checked, versioned description of the repository) even before resolution exists, and every other story depends on a map existing.

**Independent Test**: Run `context init` in a repository with no map, confirm a schema-valid starter map is written under the SpecOps namespace, edit it, run `context validate`, and confirm the command reports success (exit 0) for a valid map and a precise, actionable diagnostic (exit 1) for each defect class.

**Acceptance Scenarios**:

1. **Given** a repository with no context map, **When** the maintainer runs `context init`, **Then** a schema-valid starter map carrying the current schema version is created under the SpecOps namespace and the command reports where it was written.
2. **Given** an existing context map, **When** the maintainer runs `context init` again, **Then** the existing map is not overwritten or mutated and the command reports that a map already exists.
3. **Given** a well-formed context map, **When** the maintainer runs `context validate`, **Then** the command exits 0 and reports the number of contexts and the schema version.
4. **Given** a map with a defect (invalid path, duplicate context ID, ambiguous ownership, dependency cycle, unsafe path traversal, or unsupported schema version), **When** the maintainer runs `context validate`, **Then** the command exits 1 and names the specific defect, the offending context ID(s), and the field responsible.

---

### User Story 2 - Deterministically resolve context for a path or ID (Priority: P1)

A maintainer (or, later, an automated caller) wants to know which context(s) govern a given repository path or context ID, and receive the ordered, phase-specific set of files that should be read for that context — the same result every time, for the same map and inputs.

**Why this priority**: Deterministic resolution is the primary capability the map exists to provide and the direct input to Feature 009. It is independently valuable and testable: given a fixed map and input, the ordered context package is a pure function with a stable JSON shape.

**Independent Test**: With a fixed valid map, run `context resolve` for (a) an explicit context ID and (b) a repository path, and confirm each returns the same ordered context package and phase-specific read set on repeated runs, with a stable JSON shape.

**Acceptance Scenarios**:

1. **Given** a valid map and an explicit context ID, **When** the maintainer runs `context resolve` for that ID, **Then** the command returns that context and its ordered, phase-specific read set deterministically.
2. **Given** a valid map and a repository path owned by exactly one context, **When** the maintainer runs `context resolve` for that path, **Then** the command returns the owning context and its ordered read set.
3. **Given** a valid map and a phase argument, **When** the maintainer resolves a context for that phase, **Then** the read set returned is the phase-specific set for that phase, ordered deterministically.
4. **Given** identical map and inputs, **When** the maintainer runs `context resolve` repeatedly, **Then** the ordered package and every field are byte-for-byte identical across runs.
5. **Given** a path that matches no context, **When** the maintainer runs `context resolve` for it, **Then** the command reports an explicit "no matching context" result (not an error and not a silent empty success) with a stable, distinguishable outcome.

---

### User Story 3 - Explain why a context was resolved (Priority: P2)

A maintainer wants to understand *why* the resolver selected a particular context for a path or ID — which rule matched, why it won over alternatives, and what dependencies and policy were pulled in — so the result is auditable rather than a black box.

**Why this priority**: Explainability turns deterministic resolution into a trustworthy, auditable decision and is a prerequisite for Feature 009's "every expanded review file explainable by a dependency or policy edge." It depends on resolution (US2) existing but adds distinct reason-trace value.

**Independent Test**: With a fixed valid map, run `context explain` for a path that could plausibly match more than one rule and confirm the command emits an ordered reason trace naming the matched rule, the specificity/precedence basis for selection, and the declared dependencies and gates pulled in.

**Acceptance Scenarios**:

1. **Given** a valid map and a resolvable path or ID, **When** the maintainer runs `context explain`, **Then** the command emits an ordered reason trace: the candidate rules considered, the selected rule, and the deterministic basis on which it was selected.
2. **Given** a context with declared dependencies and gates, **When** the maintainer runs `context explain`, **Then** the trace lists the dependency and policy edges that contributed to the resolved package.
3. **Given** identical map and inputs, **When** the maintainer runs `context explain` repeatedly, **Then** the reason trace is identical across runs.

---

### User Story 4 - Operate safely when no map exists (Priority: P2)

A maintainer runs a read-only context command in a repository that has never adopted a context map. The command must treat "no map" as a first-class, explicitly reported state — never a crash, never a misleading empty success.

**Why this priority**: Roadmap Rule 5 requires new behavior to degrade safely when an optional context map is absent. Every downstream consumer (Feature 009 onward) relies on a clean, distinguishable "no map" signal. It is small but load-bearing.

**Independent Test**: In a repository with no context map, run `context validate`, `context resolve`, and `context explain`, and confirm each reports a clear, consistent "no context map present" state with a stable, distinguishable outcome rather than an error or a false positive.

**Acceptance Scenarios**:

1. **Given** a repository with no context map, **When** the maintainer runs any read-only context command, **Then** the command reports an explicit "no context map present" state without crashing.
2. **Given** the "no map" state, **When** the maintainer requests JSON output, **Then** the JSON explicitly marks the absent-map state in a stable, machine-distinguishable way.
3. **Given** the "no map" state, **When** the command completes, **Then** it does not create, mutate, or partially write any map or repository state.

---

### Edge Cases

- **Overlapping matches**: When a path matches more than one glob rule, resolution selects the most specific rule (fewer wildcards / longer literal prefix); a genuine, unbreakable tie (two rules of equal specificity claiming the same path with conflicting ownership) is reported as ambiguous ownership and fails validation, not silently resolved.
- **Unsafe path traversal**: A context whose path pattern escapes the repository root (e.g. `..` traversal or absolute paths outside the repo) is rejected by validation before any resolution occurs.
- **Dependency cycles**: A cycle among declared context dependencies is detected and reported with the participating context IDs (in a stable order); it never causes infinite expansion during resolution.
- **Dangling dependency**: A dependency edge referencing a context ID absent from the map is rejected at validation as a distinct defect (not conflated with a cycle).
- **Duplicate context IDs**: Two contexts sharing an ID are rejected at validation with both locations named.
- **Unsupported schema version**: A map whose declared schema version is newer or otherwise unsupported is rejected with a clear version diagnostic rather than being partially interpreted.
- **Empty but present map**: A syntactically valid map declaring zero contexts is a valid, resolvable state (every resolve returns "no matching context") — distinct from an absent map.
- **Malformed map file**: A map that is not parseable is reported as a parse/format error distinct from a schema-validation error and distinct from the absent-map state.
- **Path outside every context**: Resolving a path owned by no context returns an explicit "no matching context" outcome (exit `0`, distinct `status`), not an error.
- **Unknown context ID**: Resolving `--id` for an ID absent from the map returns an explicit "no matching context" outcome (exit `0`), distinct from a usage error.
- **Conflicting or missing selector**: Supplying both `--path` and `--id`, or neither, to `resolve`/`explain` is a usage error (exit `2`), never a silent default.
- **Phase with no declared read set**: Resolving a context for a phase that declares no specific read set falls back deterministically to the context's `base` read set (or an explicit empty set when no `base` exists), and `explain` states that the fallback was used.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SpecOps MUST define a versioned context map schema, stored under the SpecOps-owned namespace within `.specify`, that carries an explicit schema version and is stack-neutral (no coupling to any language, framework, or business domain).
- **FR-002**: The schema MUST separate the following into independently declared and independently validated fields: (a) context matching (which paths/IDs a context governs), (b) reading guidance (phase-specific read sets), (c) topology/ownership, (d) inter-context dependencies, (e) gate policy references, and (f) risk metadata. A defect in one field MUST be reportable without conflating it with another.
- **FR-003**: SpecOps MUST provide a `context init` command that creates a schema-valid starter context map when none exists, reports where it was written, and is idempotent — re-running MUST NOT overwrite or mutate an existing map and MUST report that a map already exists.
- **FR-004**: SpecOps MUST provide a `context validate` command that checks a map against the schema and all structural rules, with no interactive prompts (Constitution Principle VI). Exit codes follow the common contract in FR-004a.
- **FR-004a**: Every context command MUST expose a fixed exit-code taxonomy: `0` = success — including the supported "absent map" and "no matching context" reads; `1` = blocking / fail-closed (invalid, ambiguous, malformed, or unsupported-version map); `2` = usage/input error (bad or conflicting arguments). The fine-grained outcome MUST additionally be reported in a stable `status` field in the command output (see FR-014, FR-015), so exit codes stay minimal while supported states (FR-013, FR-018) remain non-errors.
- **FR-005**: `context validate` MUST detect and distinctly report each of: invalid path patterns, unsafe path traversal, duplicate context IDs, ambiguous ownership, dangling dependency references, dependency cycles, and unsupported schema versions — naming the offending context ID(s) and responsible field for each, each with a distinct diagnostic. A path pattern is "invalid" when it is malformed; "unsafe path traversal" is the distinct subclass where a well-formed pattern escapes the repository root (`..` traversal or absolute path). Path validation is **syntactic and safety-based only** and MUST NOT consult the filesystem — a well-formed, in-repo pattern that matches zero files on disk is valid. A dependency edge referencing a context ID not present in the map is a distinct "dangling dependency" defect; gate/policy references, ownership, and risk metadata are validated for well-formedness (correct type / a string-keyed mapping) only — not resolvability or semantic interpretation (deferred to Features 009 and 012).
- **FR-006**: SpecOps MUST provide a `context resolve` command that accepts the target through explicit, mutually exclusive selectors — a context ID (`--id`) or a repository path (`--path`) — and returns the governing context and its ordered, phase-specific read set. Supplying both selectors, or neither, is a usage error (exit `2`); an ID is never inferred from a path or vice versa.
- **FR-007**: Resolution MUST be deterministic: the same map and the same inputs MUST always produce the identical ordered context package and read set, independent of filesystem ordering, locale, or invocation environment.
- **FR-008**: Contexts MUST claim paths via gitignore-style glob patterns (each such pattern is a "match rule") interpreted relative to the repository root. When a path matches more than one match rule, resolution MUST select the winning context by a **total, documented specificity comparator** applied in this order: (1) longer literal (non-wildcard) prefix, then (2) fewer wildcard tokens, then (3) more path segments. Resolution MUST never depend on undefined ordering. If two different contexts tie on all three comparator dimensions for the same path, that path has ambiguous ownership: it MUST NOT be resolved silently and MUST be reported as an ambiguous-ownership defect that fails validation (FR-005).
- **FR-009**: `context resolve` MUST accept an optional lifecycle phase and return the read set specific to that phase; when a context declares no read set for the requested phase, resolution MUST fall back deterministically to the context's phase-agnostic `base` read set, and when no `base` is declared either, to an explicit empty read set (distinct from a "no matching context" outcome).
- **FR-010**: SpecOps MUST provide a `context explain` command that accepts the same explicit `--id` / `--path` selectors as `context resolve` (FR-006) and emits an ordered reason trace for a resolution: the candidate rules considered, the selected rule, the deterministic basis for selection (which specificity comparator dimension decided it, per FR-008), and the dependency and gate/policy edges that contributed to the resolved package.
- **FR-011**: The reason trace produced by `context explain` MUST be deterministic and MUST be sufficient to reconstruct why a given context (and no other) was resolved for the given input.
- **FR-012**: Resolution MUST resolve declared inter-context dependencies without infinite expansion. A dependency edge to an unknown context ID (dangling dependency) MUST be rejected at validation (FR-005). A dependency cycle MUST be surfaced deterministically (at validation and, if reached, at resolution) with the participating context IDs in a stable order and MUST NOT hang or loop.
- **FR-012a**: The resolved context package MUST include both (a) the declared dependency edges and (b) a deduplicated, deterministically ordered expanded read set drawn from the dependency contexts, with each pulled-in entry attributable to its originating dependency edge in the reason trace. Expansion MUST be cycle-safe (a context is never expanded twice).
- **FR-013**: SpecOps MUST treat an absent context map as a supported, first-class state: every read-only context command MUST report a clear, distinguishable "no context map present" outcome without crashing and without creating or mutating any state.
- **FR-014**: SpecOps MUST distinguish, as separate outcomes, at least: absent map, unparseable/malformed map, schema-invalid map, valid-but-empty map, and valid map — so callers can act on each differently.
- **FR-015**: Every read-only context command (`validate`, `resolve`, `explain`) MUST offer a stable, versioned JSON output whose shape does not change between runs for the same logical result, suitable for automation and for Feature 009 consumption.
- **FR-016**: All read-only context commands MUST NOT create, mutate, or partially write any repository or map state; only `context init` may create the starter map, and only when none exists.
- **FR-017**: Validation and resolution MUST fail closed: an invalid or ambiguous map MUST be rejected before any resolution result is emitted, so no downstream workflow state can be derived from an unsound map.
- **FR-018**: A "no matching context" result from `context resolve` MUST be an explicit, distinguishable outcome (not an error and not an empty success indistinguishable from a match).
- **FR-019**: Human-readable output MUST remain concise; the machine-readable JSON is the stable automation surface (Global Definition of Done).
- **FR-020**: The persisted map format MUST be versioned and forward-migratable, and unsupported versions MUST be rejected rather than partially interpreted (aligns with Feature 006's versioning discipline).

### Key Entities *(include if feature involves data)*

- **Context Map**: The versioned, repository-owned document describing all contexts. Attributes: schema version, an ordered/keyed collection of Contexts, and map-level metadata. It is the single source the resolver interprets.
- **Context**: A named region of the repository. Attributes: a stable unique ID (used for direct `--id` lookup, not for path matching); one or more match rules (glob patterns) declaring which paths it governs; ownership/topology metadata; phase-specific read sets; declared dependencies on other Contexts; referenced gate/policy identifiers; and risk metadata. Independently validated per FR-002.
- **Match Rule**: A single gitignore-style glob pattern (relative to the repository root) by which a Context claims paths, carrying an intrinsic specificity (fewer wildcards / longer literal prefix) used for deterministic most-specific-wins precedence.
- **Read Set**: An ordered collection of files/areas an agent should read for a Context, keyed by lifecycle phase, plus an optional phase-agnostic `base` set that phases without their own set inherit; when neither exists, the phase read set is explicitly empty.
- **Dependency Edge**: A declared directed relationship from one Context to another (referencing a context ID that MUST exist in the map), expanded during resolution (contributing its read set to the expanded read set), deduplicated, and checked for cycles.
- **Resolved Context Package**: The deterministic output of resolution — the selected Context, its ordered phase-specific read set, its declared dependency edges, a deduplicated ordered expanded read set attributable per edge, and its referenced gates/risk — with a stable JSON shape.
- **Reason Trace**: The ordered, deterministic explanation emitted by `context explain` — candidate rules, selected rule, selection basis, and contributing dependency/policy edges.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any fixed valid map and fixed inputs, 100% of repeated `context resolve` and `context explain` invocations produce byte-for-byte identical ordered output (determinism is total, not statistical).
- **SC-002**: Every defect class named in FR-005 (invalid path pattern, unsafe path traversal, duplicate ID, ambiguous ownership, dangling dependency reference, dependency cycle, unsupported schema version) is detected by `context validate`, each producing a distinct, correctly attributed diagnostic — verified by one failing-fixture test per class.
- **SC-003**: An invalid or ambiguous map never yields a resolution result: 100% of resolve/explain attempts against an invalid map fail closed before emitting a resolved package.
- **SC-004**: In a repository with no map, every read-only context command reports the explicit "no map present" state and exits without crashing and without creating or mutating any file — verified for all three read-only commands.
- **SC-005**: The five map states in FR-014 (absent, malformed, schema-invalid, empty-valid, valid) are each distinguishable from the command outcome alone (human and JSON), verified by a fixture per state.
- **SC-006**: Every read-only context command emits JSON with a stable, versioned shape; a schema/contract test confirms the shape is unchanged across runs for the same logical result.
- **SC-007**: For a path matching multiple glob rules, resolution selects the most-specific winner in 100% of cases and `context explain` names the specificity basis; an equal-specificity conflict is reported as ambiguous ownership at validation — verified by an overlapping-rules fixture and a tie fixture.
- **SC-008**: A dependency cycle is detected and reported with participating context IDs and never causes a hang or unbounded expansion — verified within a bounded test time budget.
- **SC-009**: `context init` is idempotent: running it twice leaves exactly one unmodified map and reports the pre-existing map on the second run.
- **SC-010**: The persisted map declares a schema version and an unsupported version is rejected with a version-specific diagnostic — verified by a version-mismatch fixture.
- **SC-011**: For a context with declared dependencies, the resolved package's expanded read set is deduplicated, deterministically ordered, and every entry is attributable to its originating dependency edge in the reason trace — verified by a dependency-expansion fixture.
- **SC-012**: Resolving a phase with no declared read set returns the context's `base` set (or an explicit empty set when no `base` exists), and `context explain` reports that the fallback was used — verified by base-inheritance and no-base fixtures.
- **SC-013**: Every command maps its outcome to the fixed exit-code taxonomy (`0` success incl. absent-map/no-match, `1` blocking, `2` usage error) AND to a stable `status` field — verified by an exit-code matrix test covering valid, invalid, absent-map, no-match, and usage-error cases.
- **SC-014**: The most-specific-wins comparator is a total order decided by dimensions (1) literal prefix, (2) wildcard count, (3) segment count in that priority; `context explain` names which dimension decided — verified by one fixture per deciding dimension plus a genuine-tie fixture that fails validation.
- **SC-015**: `resolve`/`explain` accept the target only via explicit `--path`/`--id`; supplying both or neither exits `2` with a usage-error status, and an unknown `--id` yields "no matching context" (exit `0`) — verified by selector-contract fixtures.

## Assumptions

- **Namespace and format**: The context map lives under the SpecOps-owned area of `.specify` (e.g. a `.specify/specops/` path), serialized in the same human-editable, versioned style already used for SpecOps persisted state (consistent with the PyYAML-based ledger). The exact filename is an implementation detail resolved in planning; the spec only requires "under the SpecOps namespace in `.specify`."
- **Path matching model**: Resolved by clarification — gitignore-style glob patterns relative to the repository root, most-specific-wins, equal-specificity ties = ambiguous-ownership validation failure (see Clarifications, FR-008).
- **Ownership semantics**: In this feature, ownership is descriptive topology/metadata used for resolution and diagnostics, **not** an exclusive write-permission boundary; the interpretation of ownership as a review-scope signal is deferred to Feature 009 (per that feature's non-goals).
- **Gates and risk are references/metadata only**: This feature stores gate identifiers and risk metadata as declared fields and validates their structure; it does **not** execute gates or interpret risk (gate execution is Feature 012; planning/review consumption is Feature 009).
- **No source parsing**: Dependencies and topology are taken exclusively from the declared map; SpecOps performs no semantic source-code dependency parsing (explicit non-goal).
- **Read-only guarantee**: Only `context init` writes, and only when no map exists; `validate`, `resolve`, and `explain` never mutate state.
- **Phases**: Lifecycle phases referenced by read sets are the SpecOps/Spec Kit lifecycle phases (specify, plan, tasks, implement, review); the map may omit a phase and rely on the documented default.
- **Offline and domain-agnostic**: All behavior operates offline against local repository state and remains free of stack-specific coupling (Constitution Principle V, Roadmap Rule 6).
- **Development discipline**: This capability is built and proven through the feature's own tests against fixtures and sample repositories; it is **not** exercised by running SpecOps against this repository (No Self-Application).

## Dependencies

- **Feature 005 (Native Spec Kit Extension, MERGED)**: The context commands are registered through SpecOps's native extension/command surfaces established by 005.
- **Feature 006 (Ledger v2 Integrity, MERGED)**: The context map reuses 006's versioning, timezone/serialization, and forward-migration discipline for its own persisted, versioned format.
- **Downstream (not part of this feature)**: Feature 009 consumes the resolved context package and reason trace for planning, implementation, and review; this feature ships the deterministic foundation only.
