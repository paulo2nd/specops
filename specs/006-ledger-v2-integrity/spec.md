# Feature Specification: Ledger v2 Integrity

**Feature Branch**: `006-ledger-v2-integrity`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "Introduce a versioned Ledger v2 with migrations, timezone-aware timestamps, workspace identity validation, concurrency protection, explicit invariants, and richer recovery metadata. Preserve supported v1 ledgers and guarantee atomic, interruption-safe state changes."

## Clarifications

### Session 2026-07-19

- Q: How is a successful-but-wrong migration recovered from, given auto-migration overwrites the older ledger in place? → A: Migration writes a retained backup of the original ledger before replacing it, recorded in recovery metadata, so rollback is deterministic (mirrors Feature 005's non-destructive precedent).
- Q: What triggers migration — automatic on first write, or an explicit command? → A: Automatic on the first state-changing operation, with an explicit opt-in migrate command also offered as a convenience for CI/deliberate migration.
- Q: What does "baseline" mean for the identity/divergence check? → A: The branch-point commit — HEAD at ledger creation — which must remain reachable as an ancestor of current HEAD; unreachability (from a branch switch, reset, or history rewrite) is the divergence signal.
- Q: Does read-only inspection remain available when the ledger is too-new, unsupported-old, or malformed? → A: Yes — read-only is always non-mutating and reports best-effort status plus a clear diagnostic for these states; it never mutates and never fails destructively.

### Session 2026-07-20

- Q: The identity gate fails closed on a branch rename or history rewrite (baseline no longer an ancestor), which strands legitimate workflows. Is there an escape hatch? → A: Yes — an explicit, auditable `rebaseline` operation re-anchors the recorded branch and baseline to the current workspace. It never changes the bound feature identity (that is not a re-baseline and fails closed), preserving the fail-closed default while giving the human a deliberate opt-in path (FR-019a).
- Q: Should a pre-existing (legacy) invariant defect in a v1 ledger block unrelated commands after migration? → A: No — the invariant gate blocks only violations a command *newly introduces*; violations already present at load are tolerated so a legacy ledger is never permanently locked out (FR-025 refined). `reconcile` still reports them.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upgrade an existing feature ledger to v2 without losing work (Priority: P1)

A maintainer whose repository already tracks one or more features with the current (v1) execution ledger upgrades SpecOps. The next time they run a state-changing operation on a feature, SpecOps recognizes the ledger is an older schema, migrates it deterministically to the versioned v2 shape, and continues the operation. No phase state, task record, evidence, or review history is lost or altered in meaning, and read-only inspection of an un-migrated ledger never rewrites it.

**Why this priority**: The entire roadmap that follows (traceability, context provenance, gate profiles) writes into the ledger. Without a versioned, migratable ledger, every later feature would risk corrupting existing adopters' state. A safe, lossless migration is the minimum viable slice that unblocks the rest.

**Independent Test**: Starting from a repository whose feature ledger was produced by a supported prior SpecOps version, run a state-changing operation and verify that (a) the ledger now carries an explicit schema version, (b) every phase, task, evidence entry, and review cycle is preserved with identical meaning, and (c) reading the ledger before that operation left the on-disk file unchanged.

**Acceptance Scenarios**:

1. **Given** a feature ledger written by a supported prior version, **When** the maintainer runs a state-changing operation, **Then** SpecOps migrates the ledger to the versioned schema and completes the operation, preserving all prior records.
2. **Given** a supported prior-version ledger, **When** the maintainer runs a read-only inspection, **Then** the on-disk ledger file is not modified.
3. **Given** a ledger already at the current schema version, **When** any operation runs, **Then** no migration is attempted and the schema version is unchanged.
4. **Given** a ledger whose recorded schema version is newer than this SpecOps release understands, **When** any operation runs, **Then** SpecOps refuses to proceed and reports that the ledger requires a newer SpecOps version, leaving the ledger untouched.

---

### User Story 2 - Prevent lost updates from concurrent or stale sessions (Priority: P1)

Two agents or humans work against the same feature at overlapping times, or one session holds a ledger it read earlier while another has since advanced it. When a session tries to commit a state change based on a ledger snapshot that is no longer current, SpecOps refuses the write instead of silently overwriting the newer state. The rejected session is told the ledger moved on, so it can re-read and retry. No committed record is ever lost to a competing write.

**Why this priority**: The ledger is the single source of execution truth. A lost update — one session clobbering another's committed task completion or review verdict — is a silent data-integrity defect that undermines the whole methodology. This must ship together with the versioned schema because both are foundational integrity guarantees.

**Independent Test**: Simulate two sessions that both load the same ledger revision; let the first commit a change, then have the second attempt a change against its now-stale snapshot, and verify the second write is rejected with a clear stale-state signal while the first session's change remains intact.

**Acceptance Scenarios**:

1. **Given** two sessions holding the same ledger revision, **When** the first commits a state change and the second then attempts a change against its stale snapshot, **Then** the second attempt is rejected and the first change is preserved.
2. **Given** a rejected stale write, **When** the session re-reads the current ledger and retries, **Then** the retry succeeds against the current revision.
3. **Given** any successful state change, **When** the change is written, **Then** the ledger revision advances so that a later stale write can be detected.
4. **Given** two sessions attempting to advance the same ledger, **When** their writes are concurrent, **Then** at most one succeeds and the other fails without partial or interleaved data.

---

### User Story 3 - Refuse state changes when workspace identity is inconsistent (Priority: P2)

A maintainer runs a state-changing operation while the repository is in an inconsistent state — the active branch, feature directory, or baseline the ledger was created against no longer matches the current workspace (for example, the branch was switched, the feature directory was renamed, or the baseline commit is absent from the current branch's history). SpecOps detects the mismatch and refuses to mutate the ledger, reporting exactly which identity dimension diverged, so the maintainer cannot accidentally record progress against the wrong feature or branch.

**Why this priority**: Recording state against the wrong workspace corrupts the audit trail as surely as a lost update, but it is a narrower failure mode than concurrency and depends on the identity metadata introduced alongside the schema, so it follows the two P1 integrity guarantees.

**Independent Test**: Take a valid v2 ledger, change one identity dimension in the workspace (switch branch, rename the feature directory, or make the baseline commit unreachable), attempt a state change, and verify the operation is refused with a message naming the diverged dimension while the ledger is left unmodified.

**Acceptance Scenarios**:

1. **Given** a ledger bound to a feature/branch/baseline, **When** a state change is attempted from a workspace whose active branch differs from the ledger's recorded branch, **Then** the operation is refused and the ledger is unmodified.
2. **Given** a ledger whose baseline commit is no longer reachable in the active branch's history, **When** a state change is attempted, **Then** the operation is refused and reports the baseline divergence.
3. **Given** a workspace whose feature identity cannot be determined unambiguously, **When** a state change is attempted, **Then** SpecOps fails closed rather than guessing which feature to write to.
4. **Given** a consistent workspace whose branch, feature, and baseline all match the ledger, **When** a state change is attempted, **Then** the identity check passes and the operation proceeds.

---

### User Story 4 - Survive an interrupted write with a readable ledger (Priority: P2)

A state-changing operation is interrupted midway — the process is killed, the machine loses power, or the terminal is closed — while SpecOps is persisting the ledger. When the maintainer returns, the ledger on disk is still a complete, valid, readable ledger reflecting the last successfully committed state; the interrupted change is simply absent. No half-written, truncated, or corrupt ledger is ever left behind, and recovery metadata makes clear what the last consistent state was.

**Why this priority**: Interruptions are inevitable in real agent and human workflows. A ledger that can be left corrupt turns a routine interruption into unrecoverable state loss. This guarantee is what makes the atomic-write promise credible, and it pairs with the recovery metadata added by this feature.

**Independent Test**: Interrupt a state-changing operation during ledger persistence, then read the ledger and verify it is complete and valid, reflects the previous committed state (not a partial new state), and exposes recovery metadata identifying that state.

**Acceptance Scenarios**:

1. **Given** a state change is interrupted while the ledger is being persisted, **When** the maintainer next reads the ledger, **Then** the ledger is a complete valid document reflecting the last committed state.
2. **Given** an interrupted write, **When** the ledger is inspected, **Then** no truncated, empty, or partially-written ledger file is present.
3. **Given** a recovered ledger, **When** the maintainer inspects recovery metadata, **Then** it identifies the last consistent state so the interrupted work can be resumed or re-attempted deterministically.

---

### Edge Cases

- **Unsupported legacy shape**: A ledger predates the oldest schema this release can migrate. SpecOps refuses to guess, reports the shape as unsupported, and leaves it untouched rather than performing a lossy best-effort migration.
- **Simultaneous first migration**: Two sessions both try to migrate the same v1 ledger at once. At most one migration is applied; the other observes the migrated result or a stale-state rejection, never a double migration or a merge of two migrations.
- **Timestamp without zone**: A prior ledger stored timestamps without timezone information. Migration attaches an explicit, unambiguous zone using a documented rule so no timestamp becomes ambiguous or shifts in meaning.
- **Malformed or hand-edited ledger**: A ledger has been manually edited into an invalid shape (e.g., a task references a phase that does not exist, or a required field is missing). State-changing operations fail closed with a specific invariant-violation message instead of writing on top of invalid state.
- **Clock skew / non-monotonic time**: A new timestamp would be earlier than the most recent recorded one. The system records the timestamp as given but relies on the monotonic ledger revision — not wall-clock time — to order and detect stale writes.
- **Empty or newly created ledger**: A brand-new feature with no prior ledger starts directly at the current schema version with an initial revision and complete identity metadata.

## Requirements *(mandatory)*

### Functional Requirements

#### Schema versioning & migration

- **FR-001**: The ledger MUST carry an explicit, persisted schema version identifier.
- **FR-002**: SpecOps MUST detect the schema version of any ledger it reads and classify it as current, migratable-older, unsupported-older, or too-new.
- **FR-003**: SpecOps MUST migrate a migratable-older ledger to the current schema deterministically, such that the same input ledger always produces the same migrated result.
- **FR-004**: Migration MUST preserve every phase, task, evidence entry, review cycle, and recovery record from the source ledger with identical meaning.
- **FR-005**: SpecOps MUST refuse to operate on a ledger whose schema version is newer than the running release understands, leaving it unmodified and reporting that a newer SpecOps version is required.
- **FR-006**: SpecOps MUST refuse to migrate a ledger whose shape is older than the oldest supported schema, reporting it as unsupported and leaving it unmodified.
- **FR-007**: Read-only operations MUST NOT migrate or otherwise modify the on-disk ledger.
- **FR-008**: Migration of a ledger already at the current schema version MUST be a no-op (idempotent) that does not rewrite the schema version or reorder existing records.
- **FR-008a**: Before replacing an older ledger, migration MUST write a retained backup of the original ledger content and reference it from recovery metadata, so a migration later found defective can be rolled back deterministically to the pre-migration state.
- **FR-008b**: Migration MUST be applied automatically and transparently on the first state-changing operation against a migratable-older ledger, and SpecOps MUST additionally provide an explicit opt-in migration command that performs the same migration deliberately (for CI or pre-flight inspection) with identical, idempotent results.

#### Timestamps

- **FR-009**: Every timestamp the ledger records MUST be timezone-aware and serialized in a stable, unambiguous, documented format.
- **FR-010**: Migration MUST convert any pre-existing zone-naive timestamp to a zone-aware value using a documented, deterministic rule without changing the instant it refers to.
- **FR-011**: Serialization of unchanged ledger content MUST be stable — re-persisting a ledger whose logical content did not change MUST NOT produce spurious differences in timestamps or field ordering.

#### Concurrency & lost-update protection

- **FR-012**: Each ledger MUST carry a monotonic revision marker that advances on every successful state change.
- **FR-013**: A state-changing operation MUST reject its write when the ledger has advanced beyond the revision the operation was based on, without overwriting the newer state.
- **FR-014**: When concurrent state changes target the same ledger, at most one MUST succeed; the others MUST fail cleanly with no partial, interleaved, or merged data.
- **FR-015**: A stale-write rejection MUST clearly signal that the ledger moved on, so the caller can re-read the current ledger and retry.
- **FR-016**: Stale-write detection MUST rely on the ledger revision marker rather than wall-clock timestamps.

#### Workspace identity validation

- **FR-017**: The ledger MUST record the workspace identity it is bound to, covering at least the feature identity, the branch, and the baseline it was created against. The baseline is the branch-point commit — the HEAD commit at the moment the ledger was created.
- **FR-017a**: The baseline check MUST verify the recorded baseline commit is still reachable as an ancestor of the current HEAD; an unreachable baseline (from a branch switch, reset, or history rewrite) MUST be treated as a divergence.
- **FR-018**: Before any state change, SpecOps MUST verify that the current workspace's feature, branch, and baseline match the ledger's recorded identity.
- **FR-019**: On any identity mismatch, SpecOps MUST refuse the state change, leave the ledger unmodified, and report which identity dimension diverged.
- **FR-020**: When the current feature identity cannot be determined unambiguously, SpecOps MUST fail closed rather than write to a guessed feature.
- **FR-021**: Identity validation MUST apply only to state-changing operations; read-only inspection MUST remain available even when identity has diverged, without mutating the ledger.
- **FR-019a**: SpecOps MUST provide an explicit, auditable re-baseline operation that re-records the current branch and a fresh baseline (current HEAD) into the ledger, for use after a deliberate branch rename or history rewrite. It MUST NOT change the bound feature identity; if the resolved feature no longer matches the ledger's feature it MUST fail closed. It is a state change (advances the revision) and goes through the same atomic/CAS/invariant machinery as any other write.

#### Atomicity, interruption safety & recovery

- **FR-022**: Persisting the ledger MUST be atomic: an interrupted write MUST leave the previous complete, valid ledger readable, never a truncated or partial file.
- **FR-023**: After an interrupted write, the ledger on disk MUST reflect the last successfully committed state, with the interrupted change absent.
- **FR-024**: The ledger MUST expose recovery metadata identifying the last consistent state sufficient to deterministically resume or re-attempt interrupted work.
- **FR-025**: State-changing operations MUST NOT write new invalid state: an operation MUST fail closed with a specific invariant-violation report when it would *introduce* a formalized-invariant violation. A violation already present when the ledger was loaded (a legacy defect a v1 ledger may carry) MUST NOT, on its own, block an unrelated operation — otherwise a legacy ledger could be permanently locked out; such pre-existing violations remain reportable by `reconcile`.

#### Invariants & new metadata

- **FR-026**: SpecOps MUST define and enforce explicit invariants for phases (a single well-defined ordered phase progression), tasks (valid state and references), recovery records, and review cycles.
- **FR-027**: The ledger MUST record the active artifact and workflow-lane metadata alongside the ledger revision metadata.
- **FR-028**: All new v2 metadata (schema version, revision, identity, workflow lane, active artifact, recovery) MUST be populated for newly created ledgers and back-filled deterministically during migration.

#### Compatibility

- **FR-029**: SpecOps MUST preserve the ability to read supported v1 ledgers for inspection without requiring migration first.
- **FR-029a**: Read-only inspection MUST remain non-mutating and available for every ledger state — including too-new, unsupported-older, and malformed ledgers — reporting best-effort status together with a clear diagnostic rather than mutating the ledger or failing destructively.
- **FR-030**: Evidence records MUST remain compatible with their current representation; this feature MUST NOT redesign the evidence format.

### Key Entities

- **Ledger**: The per-feature execution record. Now additionally carries a schema version, a monotonic revision marker, workspace identity, workflow-lane and active-artifact metadata, and recovery metadata, in addition to its existing phase, task, evidence, and review-cycle content.
- **Schema Version**: An explicit identifier classifying a ledger as current, migratable-older, unsupported-older, or too-new, driving migration and refusal decisions.
- **Ledger Revision**: A monotonic marker that advances on every committed state change and is the basis for detecting stale/lost updates.
- **Workspace Identity**: The bound feature identity, branch, and baseline the ledger was created against, checked before every state change.
- **Recovery Metadata**: Information identifying the last consistent committed state, used to resume or re-attempt interrupted work.
- **Migration**: A deterministic transformation from a supported older schema to the current schema that preserves the meaning of all prior records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of ledgers produced by every supported prior SpecOps version migrate to the current schema with every phase, task, evidence entry, and review cycle preserved, verified by migration tests covering each supported prior shape.
- **SC-002**: In a concurrent or stale-write scenario, 0 committed records are lost — at most one competing writer succeeds and the rejected writer receives a clear stale-state signal in 100% of trials.
- **SC-003**: A ledger whose recorded state, branch, feature, or baseline does not match the current workspace is rejected for state changes in 100% of mismatch cases, each identifying the diverged dimension.
- **SC-004**: An interruption at any point during ledger persistence leaves a complete, readable ledger reflecting the last committed state in 100% of injected-interruption trials, with 0 truncated or corrupt ledgers observed.
- **SC-005**: Re-running a state-changing operation that produces no logical change yields a byte-stable ledger (no spurious timestamp or ordering differences) in 100% of idempotency checks.
- **SC-006**: Read-only inspection of any supported ledger, including un-migrated older shapes, leaves the on-disk file unchanged in 100% of cases.
- **SC-007**: Every recorded timestamp in a v2 ledger is timezone-aware, with 0 zone-naive timestamps remaining after migration.

## Assumptions

- **Concurrency model**: Lost-update protection is achieved with optimistic concurrency — a monotonic ledger revision compared at write time (compare-and-swap on revision), rather than long-held external locks — chosen because the roadmap already requires a ledger-revision metadata field and this keeps the CLI free of interactive locking. Any advisory file lock used is a short-lived implementation detail internal to a single atomic write.
- **Migration trigger**: Migration is applied automatically and transparently on the first state-changing operation against an older supported ledger; it is never triggered by a read-only command (per FR-007). An explicit opt-in migrate command is additionally provided as a convenience (per FR-008b); it is not mandatory to invoke before normal use.
- **Fail-closed default**: Consistent with the project's global definition of done, all ambiguous-identity and invariant-violation conditions fail closed (refuse the state change) rather than warn-and-proceed; there is no override flag in this feature's scope.
- **Supported prior shapes**: "Supported v1 ledgers" means the ledger shapes emitted by prior released SpecOps versions still in use; shapes never shipped in a release are out of scope for migration.
- **Timezone rule for naive timestamps**: Pre-existing zone-naive timestamps are interpreted as UTC during migration (the documented deterministic rule referenced in FR-010), since existing serialization already normalizes toward UTC; this preserves the recorded instant.
- **Baseline meaning**: "Baseline" is the branch-point commit — the HEAD commit captured when the ledger was created (per FR-017/FR-017a). Divergence is detected when that commit is no longer reachable as an ancestor of the current HEAD.
- **Out of scope (deferred to later roadmap features)**: no evidence-format redesign (Feature 012), no new agent orchestration (Feature 007), no context routing or context map (Features 008–009). This feature is confined to ledger integrity.
