# Feature Specification: Native Spec Kit Extension

**Feature Branch**: `005-native-speckit-extension`

**Created**: 2026-07-19

**Status**: Draft

**Input**: User description: "Package SpecOps as a native Spec Kit extension with lifecycle hooks, integration-neutral command registration, idempotent install/update/remove, and a safe migration path from marker-injected legacy installations. Keep the Python CLI as the deterministic execution engine and preserve offline use."

## Clarifications

### Session 2026-07-19

- Q: When the install action runs but a compatible Python CLI engine is missing or is a version the extension cannot drive, what should happen? → A: Install verifies a compatible CLI is present and refuses (leaving the repository unchanged) if it is missing or incompatible; it does not install or upgrade the CLI itself.
- Q: How is legacy migration made non-destructive when it strips SpecOps marker blocks out of host-owned prompt files? → A: Migration backs up each affected host file before editing it and automatically restores the backups if the migration fails or is aborted.
- Q: Is an explicit "purge" (also delete ledgers/config) in scope for removal in this feature? → A: Yes — ship both: default `remove` preserves ledgers and configuration, and an explicit opt-in purge additionally removes them.
- Q: What is the mechanism of disable/enable — inert flag or unregister/re-register? → A: Disable unregisters the hooks and command from the host (so they are absent from the host's active surface); enable re-registers them from the retained configuration.
- Q: How is idempotency of install/update/migration measured — byte-identical or semantic equivalence? → A: Semantic equivalence — identical set of registrations and enabled/version state with no duplicates, ignoring benign ordering, formatting, or timestamp differences produced by the host.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Install SpecOps natively into a Spec Kit repository (Priority: P1)

A maintainer of a clean Spec Kit repository adds SpecOps with a single install action. SpecOps registers its review command and its lifecycle hooks through the host's native extension mechanism, without editing or rewriting any of the host's own prompt or command files. After install, the SpecOps directives run at the correct lifecycle seams and the repository still works offline.

**Why this priority**: This is the foundation the entire roadmap depends on. Without native registration, every later feature would keep inheriting the fragility of editing files SpecOps does not own. A clean install is the minimum viable slice that delivers standalone value.

**Independent Test**: Starting from a fresh Spec Kit repository, run the install action once and verify that (a) SpecOps commands and hooks are registered and executable at their lifecycle seams, (b) no file owned/managed by the host integration was modified, and (c) lifecycle operations still succeed with no network access.

**Acceptance Scenarios**:

1. **Given** a clean Spec Kit repository with no SpecOps present, **When** the maintainer runs the install action, **Then** SpecOps registers its command and lifecycle hooks and reports success without modifying any integration-managed prompt file.
2. **Given** a freshly installed SpecOps, **When** a lifecycle stage that SpecOps hooks into is exercised, **Then** the corresponding SpecOps directive runs at the correct seam.
3. **Given** SpecOps is installed, **When** the repository is used with no network access, **Then** all installed SpecOps behavior continues to work.
4. **Given** SpecOps is already installed, **When** the maintainer runs the install action again, **Then** the result is identical to a single install with no duplicated registrations and no error.

---

### User Story 2 - Migrate a legacy marker-injected installation (Priority: P2)

A maintainer whose repository already uses SpecOps through the older marker-injected directive blocks upgrades to the native extension. SpecOps detects the legacy installation, migrates it to native registration without losing existing configuration or any feature ledger, and removes the now-obsolete injected markers from the host's prompt files so nothing owned by the host stays modified.

**Why this priority**: Existing adopters must not be stranded or forced to reconstruct their state. A non-destructive migration path protects prior work and is required before the legacy path can eventually be retired.

**Independent Test**: Starting from a repository with legacy marker-injected SpecOps directives, existing configuration, and at least one feature ledger, run the migration and verify configuration and every ledger are preserved unchanged while the installation is now native and the injected markers are gone.

**Acceptance Scenarios**:

1. **Given** a repository with legacy marker-injected SpecOps directives, **When** the maintainer runs the install or migration action, **Then** SpecOps detects the legacy installation and reports that a migration is available or has been performed.
2. **Given** a legacy installation is migrated, **When** the migration completes, **Then** existing SpecOps configuration and every feature ledger remain intact and unmodified in meaning.
3. **Given** a migration completes, **When** the maintainer inspects the host's prompt files, **Then** no SpecOps-injected marker blocks remain in files owned by the host integration.
4. **Given** a migration already completed, **When** the maintainer runs it again, **Then** the operation is a no-op that reports the installation is already native.

---

### User Story 3 - Manage the extension lifecycle (update, disable, enable, remove) (Priority: P3)

A maintainer manages the installed extension over time: updating it to a newer version, temporarily disabling it without losing state, re-enabling it, and finally removing it. Removal leaves the host repository exactly as it would be without SpecOps — no modified integration-managed files — while preserving the maintainer's own work products such as feature ledgers.

**Why this priority**: Reversibility and clean lifecycle management are what make the extension safe to adopt. They are essential but build on a working install (P1), so they follow it.

**Independent Test**: From an installed state, run update, disable, enable, and remove in sequence and verify each is idempotent, disable/enable are state-preserving, and remove leaves no integration-managed file modified while retaining feature ledgers.

**Acceptance Scenarios**:

1. **Given** an installed SpecOps, **When** the maintainer disables it, **Then** its hooks and command are unregistered from the host's active surface and take no effect, while its configuration and ledgers are preserved.
2. **Given** a disabled SpecOps, **When** the maintainer enables it, **Then** its hooks and command are re-registered from the retained configuration and its previous behavior resumes without reconfiguration.
3. **Given** an installed SpecOps, **When** the maintainer updates it, **Then** the registered command and hooks reflect the new version and the operation is idempotent when repeated.
4. **Given** an installed SpecOps, **When** the maintainer removes it, **Then** no integration-managed file remains modified by SpecOps and the maintainer's feature ledgers are left in place.

---

### Edge Cases

- What happens when the install action runs in a directory that is not a recognized Spec Kit repository? The action must decline with a clear diagnostic and change nothing.
- How does the system handle an integration whose native extension mechanism is present but reports an incompatible version? SpecOps must refuse to register unsafely, report the incompatibility, and leave the repository unchanged.
- What happens when the install action runs but the Python CLI engine is missing or is an incompatible version? SpecOps must refuse to register, report the missing or incompatible CLI, and leave the repository unchanged (it does not install or upgrade the CLI itself).
- What happens when more than one compatible integration is installed in the same repository? SpecOps must register with each compatible integration through its own registration mechanism, without assuming a single integration.
- How does the system handle an interrupted install, migration, or removal (e.g., process killed mid-operation)? A subsequent run must be able to complete or safely reverse the partial operation, leaving a consistent state.
- What happens when migration finds legacy markers but the surrounding host prompt file has been hand-edited by the user? SpecOps must remove only its own marker-delimited blocks and preserve all surrounding content; a pre-edit backup taken before the strip lets migration restore the file untouched if the block boundaries cannot be resolved safely.
- How does the system behave when the extension is disabled but a lifecycle stage is exercised? The underlying host stage must still work standalone, with SpecOps directives degrading to no-ops.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SpecOps MUST install into a Spec Kit repository through the host's native extension mechanism, registering its review command and its lifecycle hooks without modifying any file owned or managed by the host integration.
- **FR-002**: SpecOps MUST register its lifecycle hooks so that its directives execute at the correct lifecycle seams (the phase-bearing stages) via the host's own hook mechanism rather than by editing prompt files.
- **FR-003**: SpecOps MUST register its command through the host's integration-neutral command registration mechanism and MUST support every compatible installed integration without assuming a single specific one.
- **FR-004**: Install, update, disable, enable, and remove MUST each be available as explicit lifecycle operations.
- **FR-005**: Repeated install, update, and migration operations MUST be idempotent — running an operation again from its resulting state MUST produce a semantically equivalent state (identical set of registrations and enabled/version state, no duplicated registrations) and no error. Idempotency is judged by semantic equivalence, not byte-identity, so benign host-produced ordering, formatting, or timestamp differences do not constitute a violation.
- **FR-006**: SpecOps MUST detect whether the current repository has no SpecOps, a native SpecOps installation, or a legacy marker-injected installation, and report which state was detected.
- **FR-007**: SpecOps MUST provide a non-destructive migration from a legacy marker-injected installation to a native installation that preserves existing configuration and every feature ledger unchanged in meaning.
- **FR-008**: Migration MUST remove SpecOps' own marker-delimited directive blocks from host prompt files while preserving all content outside those markers.
- **FR-008a**: Before editing any host-owned file during migration, SpecOps MUST create a recoverable backup of that file, and MUST automatically restore all such backups if the migration fails or is aborted, leaving the host files exactly as they were before migration began.
- **FR-009**: Removal MUST leave no integration-managed file modified by SpecOps and MUST NOT delete the maintainer's work products by default (feature ledgers and configuration are retained).
- **FR-009a**: SpecOps MUST provide an explicit opt-in purge that, in addition to the default removal behavior, deletes SpecOps configuration and feature ledgers. Purge MUST NOT be the default and MUST require an explicit action from the maintainer.
- **FR-010**: Disable MUST unregister SpecOps' hooks and command from the host so they are absent from the host's active surface and take no effect, while preserving SpecOps configuration and ledgers; enable MUST re-register them from the retained configuration, restoring prior behavior without requiring reconfiguration.
- **FR-011**: All installed SpecOps behavior MUST continue to function with no network access once the extension and CLI artifacts are present.
- **FR-012**: SpecOps MUST retain the Python CLI as the deterministic execution engine; the extension layer MUST delegate state transitions, validation, evidence, and verdicts to the CLI rather than reimplementing them.
- **FR-013**: When the target directory is not a recognized Spec Kit repository, or a detected integration is version-incompatible, SpecOps MUST refuse to register, report the reason, and leave the repository unchanged.
- **FR-014**: Install, migration, and removal MUST be interruption-safe — a run interrupted partway MUST be completable or safely reversible by a subsequent run, never leaving a partially registered inconsistent state.
- **FR-015**: The legacy marker-injection initialization path MUST remain available and functional; it MUST NOT be removed as part of this feature.
- **FR-016**: The install action MUST verify that a compatible Python CLI engine is present before registering, and MUST refuse to register — reporting the missing or incompatible CLI and leaving the repository unchanged — when no compatible CLI is available. The install action MUST NOT install or upgrade the CLI itself.

### Key Entities

- **Extension registration**: The record, held by the host integration, that SpecOps' command and lifecycle hooks are present, enabled or disabled, and at which version. Owned by the host mechanism, written by SpecOps' lifecycle operations.
- **Installation state**: One of *absent*, *native*, or *legacy (marker-injected)*, derived by detection over the repository.
- **Lifecycle hook binding**: The association between a phase-bearing lifecycle stage and the SpecOps directive that should run at that seam.
- **Feature ledger**: A maintainer work product (per-feature execution state) that MUST survive install, migration, disable/enable, and removal.
- **Configuration**: The SpecOps client configuration that MUST survive migration and disable/enable, and is retained on removal unless explicitly purged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A maintainer can install SpecOps into a clean Spec Kit repository in a single action, with zero files owned by the host integration reported as modified afterward.
- **SC-002**: Running install, update, or migration twice from the resulting state produces a semantically equivalent registration state on the second run — identical set of registrations and enabled/version state with no duplicates — ignoring benign ordering, formatting, or timestamp differences (idempotency holds 100% of the time).
- **SC-003**: 100% of existing configuration entries and feature ledgers are preserved through a legacy-to-native migration, with none lost or altered in meaning.
- **SC-004**: After removal, the repository has zero SpecOps-attributable modifications remaining in integration-managed files, while all pre-existing feature ledgers remain present.
- **SC-005**: All installed SpecOps operations succeed with networking disabled, demonstrating offline operation after installation.
- **SC-006**: A repository with two or more compatible installed integrations receives SpecOps registration in each of them from a single install action, with none skipped.
- **SC-007**: An install, migration, or removal interrupted midway can be re-run to reach a consistent state without manual repair in 100% of tested interruption points.
- **SC-008**: When a migration is aborted or fails at any point, 100% of host-owned files it touched are restored to their exact pre-migration content.
- **SC-009**: The legacy marker-injection installation path (`specops init`) continues to pass its existing test suite unchanged — zero regressions — after the native extension is introduced.

## Assumptions

- The host Spec Kit integration exposes a native extension mechanism capable of registering commands and lifecycle hooks; where a compatible integration lacks such a mechanism, SpecOps reports it as unsupported for native install rather than falling back to marker injection.
- "Integration-managed files" means the prompt and command files the host integration owns; SpecOps-authored files (its own command definition, configuration, and ledgers) are not integration-managed and may be created or updated.
- Removal preserves the maintainer's work products (feature ledgers) and configuration by default; an explicit opt-in purge (FR-009a) additionally deletes them and is in scope for this feature but is never the default.
- The Python CLI is installed and versioned through its own package manager; this feature governs extension registration and lifecycle, not CLI package installation or uninstallation. The install action verifies CLI presence and compatibility (FR-016) but never installs or upgrades the CLI on the maintainer's behalf.
- Legacy installations are exactly those created by the current marker-injected directive-block approach; detecting "legacy" relies on the presence of SpecOps' own marker delimiters.
- "Preserve offline use" assumes the extension and CLI artifacts are already present locally; the install action itself may require whatever access is needed to obtain those artifacts.
- Backward read compatibility of ledgers is assumed from their current representation; this feature does not redesign the ledger schema (deferred to Feature 006).
