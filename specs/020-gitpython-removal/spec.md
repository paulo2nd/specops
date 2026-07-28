# Feature Specification: GitPython Removal

**Feature Branch**: `020-gitpython-removal`

**Created**: 2026-07-28

**Status**: Draft

**Input**: User description: "Replace GitPython with direct git plumbing behind the gitops seam: a minimal typed repository abstraction, an error-taxonomy mapping preserving today's diagnostics and exit codes, removal of the gitpython/gitdb/smmap dependencies and the mypy override, and a constitution amendment to the named dependency list — behavior byte-identical, verified against the golden-capture harness."

## Clarifications

### Session 2026-07-28

- Q: How should the git precondition be defined — pinned minimum version or "present & functional"? → A: **Present & functional** — verify `git` actually runs (probe a trivial invocation); no pinned minimum version. `specops doctor` reports the detected version informationally. Every plumbing flag used predates git ~1.8 (2012), so a version gate adds cost with no realistic benefit.
- Q: What severity should `specops doctor`'s git-availability finding carry when git is missing/nonfunctional? → A: **blocking** — it is precisely "why the workflow cannot safely continue"; `ok`/informational when git is present.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Installing SpecOps pulls no GitPython dependency tree (Priority: P1)

An adopter installs SpecOps into their environment and the installation no longer pulls in `gitpython`, `gitdb`, or `smmap`. Every git-dependent SpecOps command — reconcile, the preflight gate suite, status transitions, trace, impact, context resolution — behaves exactly as it did before, using the git already on the adopter's PATH. The three transitive packages, one of which (GitPython) is in maintenance mode, leave the supported footprint entirely.

**Why this priority**: this is the feature's headline deliverable and its measurable acceptance gate — a strictly smaller, better-maintained dependency footprint with zero behavior cost. Every other story in the feature exists to make this one safe. It is the one outcome an adopter can observe directly.

**Independent Test**: can be fully tested by resolving the installed dependency tree of the built package and asserting `gitpython`, `gitdb`, and `smmap` are absent, then replaying the golden-capture harness across every git-dependent command and confirming byte-identical human and JSON output.

**Acceptance Scenarios**:

1. **Given** the built and installed package, **When** its runtime dependency tree is resolved, **Then** it contains no `gitpython`, `gitdb`, or `smmap` and names only the sanctioned runtime dependencies.
2. **Given** a repository fixture exercised by the golden-capture harness, **When** every git-dependent command is replayed after the replacement, **Then** its human and JSON output, exit codes, and any ledger writes are byte-identical to the pre-change capture.
3. **Given** an environment whose only git access is the system `git` on PATH, **When** any git-dependent command runs, **Then** it succeeds using that `git` and needs no importable git library.

---

### User Story 2 - All git access flows through one owned seam (Priority: P2)

A maintainer who needs to understand or change how SpecOps talks to git finds every git operation behind a single access layer that exposes a minimal repository abstraction — root discovery, current branch, HEAD, commit-range enumeration, ancestry, commit existence, blob/tree lookup, porcelain status, tracked-file listing, and name-status/name-only diffs. No production module imports a git library directly or threads a third-party repository type through its function signatures; they depend only on the SpecOps abstraction.

**Why this priority**: today the third-party `git.Repo` type leaks into public function signatures across several modules (the gate evaluator, the status engine, the CLI). Consolidating access behind one seam is the precondition that makes the P1 replacement a change to one module instead of many, and it is what lets a future maintainer reason about all git behavior in one place. It delivers value even if judged on its own: a single, testable git boundary.

**Independent Test**: can be tested by scanning production modules for any direct import of a git library or any use of a third-party repository type in a signature (none may remain outside the single access layer), and by confirming the abstraction exposes every capability the previous direct usages required.

**Acceptance Scenarios**:

1. **Given** the consolidated seam, **When** production modules are scanned for git-library imports, **Then** only the single git access layer imports git primitives; no other module does.
2. **Given** the repository abstraction, **When** its surface is compared against the previously required operations (root, branch, HEAD, commit range, ancestry, existence, blob/tree lookup, porcelain status, tracked files, diffs), **Then** every operation is covered and every former caller consumes the abstraction rather than a raw repository object.
3. **Given** a caller that previously received a third-party repository type, **When** its signature is inspected, **Then** it now names the SpecOps abstraction and the static type checker verifies the substitution.

---

### User Story 3 - Failure diagnostics and exit codes are preserved (Priority: P3)

A user who runs a git-dependent command against a directory that is not a git repository, a missing path, an unresolvable commit or revision, or a repository with no commits yet, sees exactly the same diagnostic message and receives exactly the same exit code as before the replacement. Every failure mode the previous library surfaced through its error taxonomy has an equivalent in the new plumbing-based layer, mapped onto the existing SpecOps error contract.

**Why this priority**: the replacement's real risk is not the happy path but the error paths — a plumbing invocation fails differently from a library call, and a silent divergence in a diagnostic or exit code is a user-visible regression that byte-identical happy-path replay would miss. Isolating and testing the taxonomy mapping is what makes the P1 guarantee trustworthy on the failure paths.

**Independent Test**: can be tested by driving each failure mode (not-a-repo, missing path, unknown commit/revision, empty repository, unreadable diff) against both the old and new layers over the same fixtures and asserting identical diagnostics and exit codes; degradation contracts (operations that return an empty result on error) must return the same empty result.

**Acceptance Scenarios**:

1. **Given** a directory that is not a git repository, **When** a command that requires a repository runs, **Then** the diagnostic message and exit code are identical to the pre-change behavior.
2. **Given** an unresolvable commit, revision, or absent path, **When** an operation that previously raised a library-specific error runs, **Then** the new layer surfaces the same SpecOps-level outcome — the same diagnostic, exit code, or documented empty-result degradation — as before.
3. **Given** a repository with no commits (unborn HEAD) or a detached HEAD, **When** branch or HEAD resolution runs, **Then** the fallback behavior (short-SHA label, degraded result) matches today exactly.
4. **Given** an environment with no functional `git` on PATH, **When** `specops init` runs, **Then** it fails closed up front with the FR-012 diagnostic rather than crashing at the `git init` step, and `specops doctor` reports the same git-availability finding as `blocking`.

---

### User Story 4 - Dependency contract and type-checker debt retired in the same change (Priority: P4)

A maintainer reviewing the change sees the constitution's named dependency list amended to remove GitPython in the same change set that removes the code dependency, and the static type checker's git-library override removed with type annotations moved onto the new abstraction — so the declared contracts and the actual footprint never disagree, even transiently.

**Why this priority**: valuable but strictly housekeeping — it corrects the governing documents and the type-checker configuration to match the new reality. It carries no runtime behavior, but landing it atomically with the code is what prevents the constitution and the dependency footprint from drifting apart (the same discipline earlier features applied to dependency additions).

**Independent Test**: can be tested by confirming the constitution's Technical Constraints dependency enumeration no longer names GitPython (and states the replacement rationale), that the type-checker configuration no longer carries the git-library override, and that the static type checker passes with annotations referencing only the new abstraction.

**Acceptance Scenarios**:

1. **Given** the merged change set, **When** the constitution's dependency list is read, **Then** GitPython is absent and the amendment records why (library in maintenance mode; git access moved behind the owned seam over plumbing).
2. **Given** the type-checker configuration, **When** it is inspected, **Then** the git-library module override is gone and no new suppression replaces it.
3. **Given** the new abstraction, **When** the static type checker runs, **Then** it passes with git-related annotations naming the SpecOps abstraction, not a third-party type.

### Edge Cases

- A repository path containing non-ASCII or non-UTF-8 byte sequences in file names — the plumbing layer must decode paths exactly as the previous library did (same bytes, same normalization), so diff and status output over such paths stays byte-identical.
- Windows-class paths (backslashes, drive letters, path separators in porcelain/diff output) — path handling in the new layer must match the previous behavior across platforms covered by CI.
- A rename in a diff — the rename-aware invocation (`-M`, single `R` on the new path) and the rename-decomposed invocation (`--no-renames`, removed-plus-added) must each produce the same shape the corresponding caller received before.
- A blob/tree lookup for a path absent at the requested revision (removed or renamed) — must return the same "not found" degradation (empty/None) the previous tree lookup did, which callers treat as stale.
- The `git` binary is absent from PATH or nonfunctional (resolves but does not run) — a git-dependent command MUST fail closed with a clear diagnostic, `specops init` MUST detect it at its first step (rather than crashing at the `git init` subprocess as it does today), and `specops doctor` MUST report it as a `blocking` finding (showing the detected version informationally when git is present) so the cause is diagnosable in one read-only place. Git-on-PATH is already an implicit precondition today (the previous library itself required an installed `git` executable), so this is not a new system requirement — only a newly explicit diagnostic. No minimum git version is enforced.
- A very large commit range or diff — the plumbing invocation must not truncate or reorder results relative to the previous library enumeration; deterministic ordering (e.g. codepoint-sorted effective-diff paths) is preserved.
- A concurrent external process mutates the repository mid-command — this feature changes only how git is invoked, not SpecOps' concurrency posture; no new guarantee is made or removed here.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The built package's runtime dependencies MUST NOT include `gitpython`, `gitdb`, or `smmap`; git access MUST use the `git` executable via plumbing invocations behind the SpecOps git access layer.
- **FR-002**: A single git access layer (the `gitops` seam) MUST be the only production module that invokes git; no other production module may import a git library or accept/return a third-party repository type.
- **FR-003**: The git access layer MUST expose a minimal repository abstraction covering every operation the previous direct usages required: root discovery, current branch (with the existing detached-HEAD fallback), HEAD resolution, commit-range enumeration, ancestry, commit existence, blob/tree (per-path content digest) lookup, porcelain working-tree status, tracked-file listing, and name-status / name-only diffs (including the cached/staged and rename-aware variants).
- **FR-004**: Every git-dependent command MUST produce byte-identical human and JSON output, exit codes, and ledger writes compared to the pre-change behavior, verified against the Feature 018 golden-capture harness plus the subprocess smoke set over real repositories.
- **FR-005**: The previous library's error taxonomy (invalid/missing repository, missing path, unresolvable commit/revision/name, failed git command) MUST be mapped onto the existing SpecOps error contract so that every failure mode yields the same diagnostic, the same exit code, and the same documented empty-result degradation as before.
- **FR-006**: Operations that today degrade to an empty result on error (e.g. diff/commit-range helpers returning an empty list) MUST preserve that exact degradation contract under the plumbing implementation.
- **FR-007**: Path decoding, ordering, and normalization in status and diff output MUST match the previous behavior, including non-UTF-8 file names and Windows-class paths, across the platforms covered by CI.
- **FR-008**: The constitution's Technical Constraints dependency enumeration MUST be amended in the same change set to remove GitPython and record the replacement rationale.
- **FR-009**: The static type checker's git-library module override MUST be removed and MUST NOT be replaced by an equivalent suppression; git-related type annotations MUST reference the SpecOps abstraction, and the static type checker MUST pass.
- **FR-010**: The change MUST introduce no new git capability, no performance work beyond the mechanical replacement, no change to what is recorded in the ledger, and no new CLI command or option. Exactly two surface deltas are sanctioned, both fail-safe improvements on error paths that carry no defined output contract today: (a) additive git-availability diagnostic content inside the existing `specops doctor` command (FR-012); and (b) `specops init` reporting a clean fail-closed diagnostic when `git` is missing instead of an uncaught crash (FR-013). No happy-path output, exit code, or command signature changes.
- **FR-011**: The ledger-domain sentinel exemption established previously (the `(human)` commit marker filtered by callers, not by the generic git layer) MUST be preserved: the new abstraction remains free of ledger-domain special-casing.
- **FR-012**: When the `git` executable is absent or nonfunctional (does not run when probed), a git-dependent command MUST fail closed with a clear, deterministic diagnostic (rather than degrade silently), and `specops doctor` MUST report git availability as an additive check — classified `blocking` when git is absent/nonfunctional and `ok` (with the detected version shown informationally) when present — consistent with its existing PATH probing for gate-command availability. The precondition is "present & functional" (a trivial probe invocation succeeds); no minimum git version is pinned, because every plumbing invocation used predates git ~1.8. The git-availability precondition MUST be evaluated in a single shared place consumed by every git-dependent path.
- **FR-013**: `specops init` MUST validate git availability (the same "present & functional" probe as FR-012) as its first step — before the repository check or the `git init` offer — and fail closed with the same diagnostic. Today `init` invokes `git init` via a subprocess with no guard, so a missing `git` surfaces as an uncaught error; after this feature even the repository check itself invokes git, so the precondition MUST be checked up front rather than crashing mid-flow.

### Key Entities

- **Repository abstraction**: the minimal, SpecOps-owned representation of an open git repository, exposing the operations in FR-003; replaces the third-party repository type in every signature.
- **Git access layer (`gitops` seam)**: the single production module that invokes the `git` executable and constructs the repository abstraction; the only place git primitives are used.
- **Error taxonomy mapping**: the correspondence from git-invocation failure modes to the existing SpecOps error contract (diagnostics, exit codes, empty-result degradations).
- **Git-availability precondition**: the single shared "present & functional" check for `git` (a trivial probe invocation succeeds; no pinned minimum version), consumed by `specops init` (first step), `specops doctor` (as an additive `blocking`/`ok` finding reporting the detected version informationally), and every git-dependent command's fail-closed path.
- **Golden-capture harness**: the Feature 018 before/after behavior-freeze mechanism, plus the subprocess smoke set, used here as the primary evidence of byte-identical behavior.
- **Dependency contract**: the constitution's named runtime-dependency enumeration and the type-checker configuration, both amended atomically with the code change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The installed runtime dependency tree contains zero of `gitpython`, `gitdb`, `smmap` (baseline today: all three present).
- **SC-002**: A before/after golden capture of every git-dependent command across the existing test scenarios shows zero differences in human output, JSON output, exit codes, and ledger writes — with the two sanctioned exceptions of `specops doctor`'s additive git-availability check (FR-012) and `specops init`'s clean git-absent diagnostic (FR-013).
- **SC-008**: With `git` absent or nonfunctional, a git-dependent command — including `specops init` at its first step — fails closed with a clear diagnostic and a stable exit code (no traceback), and `specops doctor` reports the git-availability finding as `blocking` — all covered by tests.
- **SC-003**: Exactly one production module invokes git; the count of production modules importing a git library or naming a third-party repository type in a signature is zero (baseline today: four modules import the git library directly).
- **SC-004**: Every failure mode enumerated in FR-005 produces a diagnostic and exit code identical to the pre-change behavior, demonstrated over shared fixtures against both the old and new layers.
- **SC-005**: The static type checker passes with the git-library override removed and no replacement suppression added (baseline today: a `git.*` override is required).
- **SC-006**: The constitution's dependency list no longer names GitPython and records the amendment rationale, landing in the same merged change set as the code (baseline today: GitPython named).
- **SC-007**: The full test suite passes on every CI platform, including the subprocess smoke set exercised against real repositories with real encodings and Windows-class paths.

## Assumptions

- The target environments provide a functional `git` executable — already an implicit precondition today, since GitPython itself requires an installed `git`. When it is absent or nonfunctional, SpecOps fails closed with a clear diagnostic and `specops doctor` reports it as `blocking` (FR-012). No minimum git version is pinned (every plumbing invocation used predates git ~1.8); the check is "present & functional," with the detected version shown informationally. This doctor content and `init`'s clean git-absent diagnostic are the only sanctioned, additive surface changes in the feature.
- The Feature 018 golden-capture harness and subprocess smoke set are the authoritative behavior-freeze mechanism and are available for this feature; no new capture mechanism is built.
- This is a behavior-preserving mechanical replacement: no ledger schema bump, no output-envelope change, no exit-code change, and no new CLI surface (same posture as Features 018 and 019).
- The minimal repository abstraction is a maintainer-facing internal contract, not a supported external API; SpecOps' supported surface remains the CLI.
- The dependency-list amendment is a PATCH-level constitutional change (the enumeration updates; the rule "new runtime dependencies require justification" is unchanged), consistent with the amendment precedent that added `packaging`.
- No Self-Application (constitution v1.9.1) continues to hold: all verification happens through the automated test suite's fixtures and the golden/subprocess harnesses, never by running `specops` against this repository.
- Removing the library does not, by itself, change SpecOps' offline guarantee: git-dependent operations already required a local repository; they now require the local `git` binary rather than an importable library.
