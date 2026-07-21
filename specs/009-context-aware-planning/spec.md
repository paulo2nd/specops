# Feature Specification: Context-Aware Planning and Impact

**Feature Branch**: `009-context-aware-planning`

**Created**: 2026-07-21

**Status**: Draft

**Input**: User description: "Integrate the SpecOps context map into planning, implementation, and review. Resolve minimal phase-specific reads, validate declared topology, calculate explainable impact through declared dependencies, snapshot context provenance in the ledger, and detect stale map entries after moves or removals."

## Complement Boundary *(mandatory context)*

SpecOps runs **inside** Spec Kit and is a **complement**, never a replacement (Constitution Principle I). Feature 008 added a deterministic, self-contained context map (schema plus the read-only `context init`, `context validate`, `context resolve`, `context explain` commands and their JSON contract) but explicitly deferred *consuming* that map inside the lifecycle. This feature is that consumption layer: it wires the resolved context package into the SpecOps-augmented **planning**, **implementation**, and **review** phases so agents read the minimal correct set of files, declared topology is checked against real paths, review scope expands only through explainable edges, and the provenance of every context decision is captured in the deterministic ledger.

Consistent with the roadmap's Rule 8, this feature adds **no** language-specific dependency parser, **no** Spec Kit workflow engine, gate, or resume mechanism, and **no** automatic code edits. It composes the existing context map resolution (Feature 008) and the versioned ledger (Feature 006), contributing only:

1. Deterministic **phase-scoped context resolution and display** at each lifecycle seam.
2. **Plan topology validation** — declared context IDs and paths checked against context ownership.
3. A new **`context impact`** read-only command over changed paths.
4. **Context provenance** (resolved context IDs + map digest) snapshotted in task/review ledger records.
5. **Stale-map detection** when declared paths are moved or removed.

Scope-drift acknowledgement (the model that lets a human accept a discovered path) and end-to-end traceability are explicitly deferred to Feature 010; structured evidence and gate profiles to Feature 012. This feature makes context *consumable and auditable*, without those later refinements.

## Clarifications

### Session 2026-07-21

- Q: When the context-map digest recorded at planning differs from the digest at review time (the map changed underneath the work), what should SpecOps do? → A: Report the divergence as a **non-blocking warning** in review output and ledger provenance (exit `0`); enforcement/acknowledgement of the drift is deferred to Feature 010.
- Q: Where should filesystem-aware stale-map detection live, given Feature 008's `context validate` is guaranteed syntactic-only? → A: In a **new dedicated read-only command** (e.g. `context stale`); Feature 008's `context validate` semantics remain unchanged (still no filesystem check).
- Q: How should the new `context impact` command receive the set of changed paths? → A: **Explicit path arguments, defaulting to a Git-derived diff** (active branch vs baseline) when none are supplied.
- Q: At what granularity should context provenance (resolved context IDs + map digest) be snapshotted into the ledger? → A: On **every task record and every review record** when a map is present, with an explicit empty/no-map marker when no map exists.
- Q: For `context impact`, when a changed path is owned by context A, which contexts are reported as affected "dependents"? → A: **Reverse edges** — the contexts that declare a dependency *on* A, expanded transitively and cycle-safe (the direction opposite to Feature 008 forward resolution). Impact answers "who is affected by this change," not "what A depends on."
- Q: What makes an expanded context "explained" (basis for SC-002's "zero unexplained contexts")? → A: A **closed three-member edge-type set** — `ownership` (a path match), `dependency` (a declared reverse dependency edge), and `policy` (a declared gate/policy edge). A context may appear in expanded scope only when the reason trace attributes it to exactly one of these; any context not reachable by such an edge MUST NOT appear.
- Q: What objectively triggers FR-008's "would-be unbounded/unexplained expansion" condition? → A: Expansion follows **only** the closed `ownership`/`dependency`/`policy` edges, so it is bounded by construction; the condition fires when any expansion step would require reaching a context **not attributable to such an edge** (e.g., a catch-all/wildcard owner or a whole-map transitive closure). SpecOps reports that condition instead of degenerating into a repository-wide read.
- Q: When a plan declares a path that no context owns (matches zero contexts), how should the plan-time topology check treat it? → A: **Report as a non-blocking "unowned path" observation (exit `0`)**, distinct from the blocking "owned by an undeclared context" case; partial maps are supported and this aligns with FR-005 and Feature 008's "no matching context is a supported non-error."
- Q: How is a declared path that is valid but currently matches zero files (e.g. a create-target) handled, and how does that relate to stale detection? → A: Plan-time topology validation is **existence-agnostic** (never flags a zero-match declared path; mirrors Feature 008 `validate`). Filesystem existence is checked **only** by the dedicated stale command, which operates over the **context map's** declared path patterns — never over the plan's create-targets — so create-targets and genuinely stale map entries are never conflated.
- Q: How should `context impact` behave when it derives the change set from Git and the situation is degenerate (clean tree / not a Git repo / no baseline)? → A: **Clean working tree or empty diff → empty result at exit `0`** (a supported state); **unable to derive (not a Git repo, or no resolvable baseline) → usage/input error at exit `2`** with a clear message. Explicit `--path` arguments always bypass Git derivation entirely.
- Q: Against which set of files does stale detection decide a context-map pattern "matches no file"? → A: **Git-tracked files only** (index/worktree), with symlinks matched by their own path entry and not followed. This keeps stale detection deterministic and reproducible (SC-001) and ignores environment-specific untracked/gitignored artifacts.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plan with declared context topology (Priority: P1)

A maintainer planning a feature in a repository that has a context map declares, in the plan, which context(s) the work touches and which paths it will create or modify. SpecOps resolves the minimal phase-specific read set for those contexts, displays it, and validates the declared topology — checking that declared paths fall under the declared contexts' ownership and that declared context IDs exist in the map. Planning proceeds on a validated, minimal, reasoned context scope instead of an unbounded repository read.

**Why this priority**: This is the core value of the feature — turning the static Feature 008 map into an active planning input. Without it, agents still read too much and plans still assert topology from memory (the exact failure Constitution Principle IV forbids).

**Independent Test**: With a fixed valid map and a plan that declares context IDs and paths, run the plan-time context check and confirm it (a) resolves and displays the minimal read set for the planning phase, (b) passes when declared paths are owned by declared contexts, and (c) fails closed with a specific defect when a declared context ID is unknown or a declared path is owned by an undeclared context.

**Acceptance Scenarios**:

1. **Given** a valid context map and a plan declaring existing context IDs whose ownership covers every declared path, **When** the maintainer runs the plan-time context check, **Then** it reports success (exit `0`), displays the minimal phase-specific read set, and lists the declared contexts.
2. **Given** a plan declaring a context ID that is absent from the map, **When** the check runs, **Then** it fails closed (exit `1`) and names the unknown context ID without mutating any repository or ledger state.
3. **Given** a plan whose declared path is owned by a context the plan did not declare, **When** the check runs, **Then** it fails closed and reports the undeclared owning context, prompting the maintainer to declare it.
4. **Given** a repository with **no** context map, **When** the plan-time context check runs, **Then** it reports the map-absent state as a supported non-error (exit `0`) and imposes no declaration requirement.
5. **Given** the same map, plan, and phase, **When** the check is run repeatedly, **Then** the displayed read set and reason trace are byte-for-byte identical across runs.

---

### User Story 2 - Explain the impact of a change (Priority: P1)

Before or during review, a maintainer (or an automated caller) runs impact analysis over the set of changed paths. SpecOps reports the directly affected contexts, the declared dependents that pull those contexts in, and the associated contracts, tests, gates, and risk metadata — every entry attributable to a specific ownership, dependency, or policy edge. Review scope is therefore expanded only where the map justifies it, and never degenerates into an unexplained repository-wide read.

**Why this priority**: Explainable, bounded impact is what makes context-aware review trustworthy and cheap (Constitution Principle IV, Token-Optimized Review). It is independently valuable even before ledger provenance is wired in.

**Independent Test**: With a fixed valid map, run `context impact` for a set of changed paths and confirm it returns the directly affected contexts, the transitive dependents reachable through declared dependency edges (cycle-safe), and the contracts/tests/gates/risks for each — with a reason trace attributing every expanded entry to an edge, and a stable JSON contract.

**Acceptance Scenarios**:

1. **Given** a valid map and a changed path owned by exactly one context A, **When** `context impact` runs, **Then** it reports A as directly affected plus the contexts that declare a dependency *on* A (its transitive reverse dependents), each with its contracts, tests, gates, and risk metadata.
2. **Given** a changed path matched by no context, **When** `context impact` runs, **Then** it reports the path as unmatched (a supported, non-error state) rather than failing or expanding scope arbitrarily.
3. **Given** declared dependency edges among contexts, **When** impact expands to dependents, **Then** every expanded context in the output is attributable to a specific dependency or policy edge in the reason trace, and expansion is bounded (no unexplained repository-wide read).
4. **Given** identical map and changed-path inputs, **When** `context impact --json` is run twice, **Then** the JSON output is byte-for-byte identical.

---

### User Story 3 - Snapshot context provenance in the ledger (Priority: P2)

When SpecOps records task progress and review activity, it snapshots the resolved context IDs and the context-map digest into the relevant ledger records. A later session — or a reviewer — can read the ledger and know exactly which contexts a task was planned and executed against and which version of the map produced that decision, without re-running resolution or trusting agent narration.

**Why this priority**: Provenance makes context decisions auditable and reproducible and is the bridge to Feature 010 traceability. It depends on the resolution (US1) and impact (US2) capabilities existing first, so it is P2.

**Independent Test**: Complete a task and open a review cycle against a fixture repository with a valid map, then read the ledger and confirm each task/review record carries the resolved context IDs and the map digest, and that the digest matches the map that was in effect.

**Acceptance Scenarios**:

1. **Given** a valid map and a task closed through the SpecOps ledger, **When** the ledger record is inspected, **Then** it contains the resolved context IDs for that work and the context-map digest in effect at close time.
2. **Given** a review cycle recorded through the ledger, **When** the review record is inspected, **Then** it carries the resolved context IDs and the map digest, enabling deterministic reproduction of the resolution.
3. **Given** a repository with no context map, **When** tasks and reviews are recorded, **Then** the records omit context provenance cleanly (an explicit "no map" state) and no other ledger behavior changes.
4. **Given** an existing ledger written before this feature, **When** it is read, **Then** it remains readable and records without context provenance are treated as a valid, supported prior shape.

---

### User Story 4 - Detect a stale context map after moves or removals (Priority: P3)

A maintainer restructures the repository, moving or deleting files that a context's declared paths pointed at. SpecOps detects that the map now references paths that no longer exist and reports each stale reference with the owning context, so the map can be corrected before later features rely on it. Detection is deterministic and never rewrites the map automatically.

**Why this priority**: Stale-map detection protects the integrity of every downstream context decision, but the planning, impact, and provenance capabilities deliver value first, so it is P3.

**Independent Test**: Against a fixture where a declared context path no longer matches any file on disk (because files were moved or removed), run stale-map detection and confirm it reports each stale reference with its owning context, deterministically, without modifying the map.

**Acceptance Scenarios**:

1. **Given** a context whose declared path pattern previously matched files that have since been removed, **When** stale detection runs, **Then** it reports that context's reference as stale and identifies the owning context.
2. **Given** files that were moved so a declared path now matches nothing while the intended files live elsewhere, **When** stale detection runs, **Then** the now-empty reference is reported as stale.
3. **Given** a map where every declared path still matches at least one file, **When** stale detection runs, **Then** it reports no stale references (exit `0`).
4. **Given** identical repository and map state, **When** stale detection runs repeatedly, **Then** the reported stale set is identical each time and the map file is never modified.

---

### Edge Cases

- **Map present, plan declares nothing**: When a map exists but a plan omits all context declarations, the plan-time check reports a missing-declaration defect (fail closed) rather than silently proceeding — declaration is required when a map is present.
- **Discovered path not predicted at planning**: A path that appears in the change set but was not declared during planning is reported (so review scope can include it) but does **not** by itself cause a hard rejection; the acknowledgement model for such discoveries is deferred to Feature 010.
- **Dependency cycle during impact expansion**: Impact expansion over a cyclic dependency graph terminates safely and still attributes each visited context to an edge (cycle-safe, matching Feature 008 resolution semantics).
- **Ownership is not a write boundary**: A declared path owned by one context may legitimately be read or referenced by work in another context; validation checks declared-vs-owning topology for explanation, not as an exclusive write-permission gate.
- **Changed path under an ambiguous or absent owner**: If the map itself is invalid or ambiguous, context-consuming commands fail closed and defer to `context validate` rather than producing an unreliable impact or read set.
- **Map digest changes between plan and review**: If the map digest recorded at planning differs from the digest at review time, the divergence is reported as a non-blocking warning (exit `0`) in review output and remains visible in ledger provenance; it does not block review in this feature (enforcement is deferred to Feature 010).
- **Empty change set for impact**: Running impact analysis over an empty set of changed paths — whether passed explicitly or produced by a clean working tree — returns an empty, explicitly reported result (exit `0`), not an error. In contrast, an inability to derive the set from Git (not a Git repository, or no resolvable baseline) is a usage/input error (exit `2`), not an empty success.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SpecOps MUST resolve and display the minimal phase-specific context read set for the planning, implementation, and review phases by composing Feature 008 context resolution, without re-implementing resolution logic.
- **FR-002**: When a context map is present, SpecOps MUST require a plan to declare the context ID(s) the work touches, and MUST fail closed (blocking) when the declaration is absent.
- **FR-003**: SpecOps MUST validate that context IDs declared in a plan exist in the map, reporting each unknown ID as a distinct, blocking defect.
- **FR-004**: SpecOps MUST validate declared paths against context ownership — reporting, as a **blocking** defect (exit `1`), when a declared path is owned by a context the plan did not declare — while treating ownership as an explanatory/topology relationship, **not** as an exclusive write-permission boundary. A declared path that matches **no** context at all MUST be reported as a distinct **non-blocking** "unowned path" observation (exit `0`), not a failure, since maps may be partial (Feature 008's "no matching context" is a supported non-error).
- **FR-005**: SpecOps MUST NOT hard-reject a plan or review solely because a changed file was not predicted during planning; unpredicted discovered paths are reported but not, by themselves, blocking (the acknowledgement model is Feature 010).
- **FR-006**: SpecOps MUST provide a read-only `context impact` command that, given a set of changed paths, reports the directly affected contexts, the declared **dependents** — contexts that declare a dependency *on* an affected context, expanded transitively along **reverse** dependency edges (cycle-safe), which is the opposite direction to Feature 008 forward resolution — and the contracts, tests, gates, and risk metadata associated with each. The command MUST accept explicit changed-path arguments and, when none are supplied, MUST derive the changed set from Git (active branch vs baseline). When deriving from Git, a clean working tree or empty diff MUST yield an empty result at exit `0` (a supported state), while an inability to derive the set (not a Git repository, or no resolvable baseline) MUST be a usage/input error at exit `2` with a clear message; explicit path arguments always bypass Git derivation.
- **FR-007**: SpecOps MUST make every context included in an expanded read or review scope attributable, in the reason trace, to exactly one member of the closed edge-type set **`ownership`** (a path match), **`dependency`** (a declared reverse dependency edge), or **`policy`** (a declared gate/policy edge). No context may appear in expanded scope without such an edge, and no edge type outside this closed set may pull a context into scope.
- **FR-008**: Dependency-driven expansion MUST follow **only** the closed `ownership`/`dependency`/`policy` edge set (FR-007), so it is bounded by construction and MUST NOT degenerate into an unexplained repository-wide read. When any expansion step would require reaching a context not attributable to such an edge (e.g., a catch-all/wildcard owner or a whole-map transitive closure), SpecOps MUST report that bounded-failure condition rather than reading the whole repository.
- **FR-009**: SpecOps MUST snapshot the resolved context IDs and the context-map digest into **every** task record and **every** review record when a context map is present, using the Feature 006 versioned ledger; when no map is present, each such record MUST carry an explicit empty/no-map provenance marker rather than omitting the field ambiguously.
- **FR-010**: SpecOps MUST record context provenance in a way that lets a later session deterministically reproduce which contexts a task/review targeted and which map version produced them.
- **FR-011**: SpecOps MUST detect declared **context-map** path patterns that no longer match any repository file (moved or removed) and report each stale reference together with its owning context, deterministically and without modifying the map. This filesystem-aware check MUST be exposed as a **new dedicated read-only command** (distinct from `context validate`); Feature 008's `context validate` MUST remain syntactic/safety-only with no filesystem dependency. Stale detection MUST operate over the context map's declared patterns only, never over a plan's declared create-target paths, so create-targets (expected to be absent) are never reported as stale. Plan-time topology validation MUST itself be existence-agnostic and MUST NOT flag a declared path merely because it currently matches zero files. Stale detection MUST evaluate matches against **Git-tracked files only** (index/worktree), matching symlinks by their own path entry without following them, so results are deterministic and reproducible and unaffected by untracked or gitignored artifacts.
- **FR-012**: All context-consuming read commands (resolution display, impact, stale detection) MUST be read-only: they MUST NOT mutate repository or ledger state.
- **FR-013**: Every context-consuming command MUST treat a missing context map as a supported, explicitly reported state (non-error), imposing no context requirements when no map exists.
- **FR-014**: Every read-only context-consuming command MUST provide a stable JSON output contract suitable for automation and for consumption by Feature 010, in addition to concise human-readable output.
- **FR-015**: For identical map, repository, and inputs, every context-consuming command MUST produce byte-for-byte identical output (deterministic ordering and serialization), consistent with Feature 008's determinism guarantees.
- **FR-016**: Context-consuming commands MUST expose the fixed exit-code taxonomy already established for context commands — `0` success (including supported map-absent and no-match states), `1` blocking/fail-closed (invalid, ambiguous, or unsupported map; missing required declaration; unknown declared context; undeclared owner), `2` usage/input error — with the fine-grained outcome carried in a stable `status` field.
- **FR-017**: When the underlying map is invalid, ambiguous, or an unsupported version, context-consuming commands MUST fail closed and defer to `context validate` rather than producing an unreliable result.
- **FR-018**: SpecOps MUST preserve read compatibility with ledgers written before this feature; task/review records lacking context provenance MUST be treated as a valid supported prior shape and MUST NOT block reads.
- **FR-019**: SpecOps MUST NOT introduce a language- or framework-specific source-code dependency parser; all dependency, contract, test, gate, and risk information MUST come from the declared context map, keeping the core stack-neutral (Constitution Principle V).

### Key Entities *(include if feature involves data)*

- **Plan Context Declaration**: The set of context IDs and planned paths a plan asserts it touches; the input to plan-time topology validation.
- **Phase-Scoped Context Package**: The minimal, ordered read set plus reason trace resolved for a specific lifecycle phase (planning, implementation, or review), derived from the Feature 008 resolution.
- **Impact Report**: For a set of changed paths, the directly affected contexts, their transitive reverse dependents (contexts declaring a dependency on an affected context), and the associated contracts, tests, gates, and risks — each attributable to exactly one `ownership`/`dependency`/`policy` edge.
- **Context Provenance Record**: The resolved context IDs and context-map digest snapshotted into every task and review ledger record (or an explicit empty/no-map marker when no map exists), enabling deterministic reproduction and audit.
- **Stale Reference**: A declared context path (with its owning context) that no longer matches any repository file after moves or removals.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For any fixed valid map and inputs, planning display, impact, and stale-detection outputs are 100% reproducible — repeated runs produce byte-for-byte identical results, including the reason trace.
- **SC-002**: 100% of contexts appearing in an expanded read or review scope are attributable to exactly one edge from the closed set {`ownership`, `dependency`, `policy`}; there are zero unexplained contexts (and zero contexts introduced by any out-of-set edge type) in expanded scope across the test fixtures.
- **SC-003**: Dependency-driven expansion never reads the whole repository unexplained: in every fixture, the expanded scope is a bounded subset justified entirely by the closed `ownership`/`dependency`/`policy` edge set, and any step that would require an off-set (catch-all or whole-map-closure) reach is reported as the bounded-failure condition instead of performed.
- **SC-004**: When a map is present, 100% of plans that omit required context declarations, declare an unknown context ID, or leave a declared path owned by an undeclared context are detected and blocked (exit `1`); when no map is present, 0% of plans are blocked for context reasons.
- **SC-005**: 100% of moved-or-removed declared context-map paths in the test fixtures are reported as stale references with the correct owning context, evaluated against Git-tracked files only, with no false positives on maps whose patterns all still match a tracked file and no dependence on untracked/gitignored artifacts.
- **SC-006**: 100% of task and review records created against a repository with a map carry the resolved context IDs and the map digest; records created without a map carry an explicit empty/no-map marker, and pre-feature ledgers remain readable in 100% of migration tests.
- **SC-007**: Every context-consuming read command returns within the fixed `0`/`1`/`2` exit-code taxonomy with a populated `status` field, and never mutates repository or ledger state (verified by before/after state comparison).
- **SC-008**: A reviewer can determine, from ledger provenance alone, whether the context map changed between planning and review for a given task (digest comparison), in 100% of fixtures exercising a map change; such a change is surfaced as a non-blocking warning (exit `0`) and never blocks review in this feature.

## Assumptions

- The context map schema, resolution semantics, reason trace, dependency-edge model, glob-ownership/most-specific-wins rules, and the `0`/`1`/`2` exit-code taxonomy with a `status` field are as delivered by Feature 008 and are reused unchanged; this feature consumes them rather than redefining them.
- The versioned, concurrency-safe ledger from Feature 006 is the storage for context provenance; provenance fields are added as an additive, forward-migrated extension that preserves read compatibility with prior ledger shapes.
- A plan declares context IDs and planned paths through a SpecOps-owned declaration surface in the plan artifact (consistent with the existing pattern where planned paths carry action suffixes and are validated by `specops consistency`); the exact surface is a planning detail resolved in `/speckit.plan`.
- The "map digest" is a deterministic content hash of the resolved context map already available from Feature 008's outputs; this feature records and compares it but does not redefine how it is computed.
- The set of "changed paths" fed to `context impact` is supplied as explicit command arguments, and when omitted is derived from Git (active branch vs baseline); explicit input keeps tests hermetic while the Git default makes the command usable directly in review. Computing the diff is an implementation detail, not new schema.
- "Contracts, tests, gates, and risks" reported by impact are the metadata already declared on contexts in the Feature 008 map; this feature surfaces them and does not introduce new gate execution (deferred to Feature 012).
- Stale detection is a filesystem-aware check performed on demand by a new dedicated read-only command; it does not run automatically during unrelated commands, does not alter Feature 008's syntactic-only `context validate`, and never edits the map.
- Discovered-but-undeclared paths are reported for visibility in this feature; the human acknowledgement workflow that clears them is delivered by Feature 010 and is out of scope here.
- English and Portuguese documentation remain behaviorally equivalent, and all new surfaces degrade safely to a supported no-op state when no context map exists (roadmap Rule 5).
