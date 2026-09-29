# Feature Specification: Native Code Review in `/specops-review`

**Feature Branch**: `028-native-code-review`

**Created**: 2026-09-29

**Status**: Draft

**Input**: User description: "Make `/specops-review` actually use the native code-review capability of the agent integration configured by Spec Kit. Render the review command per integration so it names that integration's real native review command: for Claude Code, the `/code-review` skill via the Skill tool, with configurable effort (default high); for other integrations, a command only where one is documented, otherwise 'no native review'. Make invoking it mandatory where it exists, including for delegated subagents. Make the map overridable in `specops.json`. Ship it to installed projects through the normal update flow and document it in the changelog." Refined 2026-09-29: do not change the review process or its records. Only add the agents' native review, without over-engineering proof of whether the native reviewer actually ran.

## Overview

Step 3a of the generated `/specops-review` command tells the reviewer to use "a
native code-review capability *if your environment provides one* (e.g. `/code-review`
in Claude Code, or an equivalent…)". Otherwise it says to review by hand. In a field run
(an adopter project, one feature, three review rounds), the review ran inside a
delegated subagent that had no access to Claude Code's skill-invocation mechanism.
`/code-review` was never called. The reviewer fell back to a manual pass without
saying so, and nothing in the verdict showed the gap.

This feature replaces the conditional example with a concrete instruction per
integration:

- Each installed copy of the review command names the exact native review command of
  its own integration, or states that the integration has none.
- Where the command exists, invoking it is mandatory.
- If it cannot run, the reviewer records that through the existing advisory-finding
  mechanism, the same way a skipped gate is recorded today. The gap then shows up in
  the revision report instead of disappearing.

**Explicitly unchanged**: the review steps, the ledger schema, the finding model, the
revision report format, and the approval gates. No new CLI command and no new ledger
field. The native reviewer is an input to the existing review, not a new layer of
verification. SpecOps does not try to prove that the native reviewer ran.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The review command names and requires the native reviewer (Priority: P1)

A maintainer's project uses Claude Code. The installed `/specops-review` tells the
reviewer, without conditionals, to invoke `/code-review` through the Skill tool, at
the configured effort, against the round's effective diff. The reviewer then turns
the confirmed findings into structured findings with the existing commands, and still
does its own review pass. The instruction also says that a subagent doing the review
needs the Skill tool. If the native reviewer cannot run, the reviewer records an
advisory `native-review-not-run` finding instead of falling back silently.

**Why this priority**: This is the whole fix for the field failure. The silent
fallback came from an ambiguous instruction.

**Independent Test**: Install SpecOps into a fixture repository with Claude Code
installed and read the rendered review command. It names `/code-review` and the Skill
tool, states the step is mandatory, includes the subagent rule and the
`native-review-not-run` fallback, and contains no "if your environment provides… /
e.g." wording.

**Acceptance Scenarios**:

1. **Given** Claude Code is installed, **When** SpecOps installs the review command, **Then** the Claude Code copy's Step 3a names `/code-review`, invoked through the Skill tool, with the configured effort, targeting the effective diff, and states that invoking it is mandatory.
2. **Given** any rendered copy for an integration with a native command, **When** the reviewer reads Step 3a, **Then** it states that a delegated subagent must have the integration's invocation mechanism, and that a run without it means the native review did not run.
3. **Given** the native reviewer could not run (mechanism unavailable, tool error) or was deliberately skipped, **When** the reviewer follows the instruction, **Then** it records an advisory finding with rule `native-review-not-run` via the existing finding command, naming the command and the reason, and continues with its own review.
4. **Given** the native reviewer ran and reported findings, **When** the reviewer follows the instruction, **Then** each confirmed finding becomes a structured finding through the existing commands. Blocking defects go through individual entry. Bulk JSON/SARIF import is used where the format allows, and those findings stay advisory as today. The reviewer's own pass still happens.
5. **Given** a rendered revision report for a round where the native review did not run, **When** a human reads it, **Then** the `native-review-not-run` advisory finding appears among the round's findings. This needs no change to the report.

---

### User Story 2 - Integrations without a native reviewer get an honest instruction (Priority: P2)

A project also has another integration installed (for example Codex, as in the field
project). Each integration's copy of the review command is rendered for that
integration. An integration with a documented native review command gets its exact
name. One without gets a plain statement that there is no native review, plus the
instruction to perform the code review manually, which is today's behavior.

**Why this priority**: Multi-integration projects exist in the field. A copy that
names a command the integration does not have would be a new silent failure.

**Independent Test**: Install into a fixture repository with two integrations
installed, one with and one without a native command. Assert that each copy names its
own command, or its absence, and that neither mentions the other integration's
command.

**Acceptance Scenarios**:

1. **Given** several integrations installed, **When** SpecOps installs, **Then** each copy's Step 3a refers only to its own integration's native command, or to its absence.
2. **Given** an integration with no native review command, or one the built-in map does not know, **When** SpecOps renders its copy, **Then** Step 3a states that there is no native review for it and instructs a manual review. It does not instruct recording `native-review-not-run`, because there is nothing that failed to run.

---

### User Story 3 - Projects can override the map (Priority: P3)

A project can override the native review settings in `specops.json`. It can change
the effort level, name a different command for an integration (for example a
project-specific review skill), or declare that an integration has none. After it
reinstalls or updates, the rendered commands reflect the override.

**Why this priority**: The built-in map covers the common case. Overrides handle
projects whose tooling differs.

**Independent Test**: Set an effort override and a command override. Reinstall, and
assert the rendered text uses both.

**Acceptance Scenarios**:

1. **Given** `native_review` sets the effort, **When** SpecOps renders, **Then** the native invocation uses that effort.
2. **Given** `native_review` overrides the command for an integration, or sets it to none, **When** SpecOps renders, **Then** that integration's copy uses the override, or the no-native-review instruction.
3. **Given** an invalid `native_review` block (for example an effort level the command does not accept, including Claude Code's user-only `ultra`), **When** SpecOps installs, **Then** it reports a configuration error with a non-zero exit and does not render an invalid instruction.

---

### Edge Cases

- **Configuration changed after install.** The rendered text reflects the configuration at the time of the last install or update. Changing `native_review` takes effect on the next run of the normal update flow, the same as any other template change.
- **Integration not in the built-in map.** Spec Kit adds integrations over time. An unknown integration renders as "no native review" unless `specops.json` declares a command for it.
- **Native findings need blocking severity.** Bulk-imported findings are always advisory (Feature 015). A confirmed native finding that is a real defect is recorded as blocking through individual finding entry, as the instruction says.
- **The native reviewer finds nothing.** Nothing is recorded beyond the reviewer's own findings. A clean native run needs no artifact.
- **In-flight features at upgrade.** A feature under review simply picks up the new instruction in its next round. There is no state to migrate.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: SpecOps MUST ship a built-in map from Spec Kit integration identifier to native review command. For Claude Code the entry is the `/code-review` skill, invoked through the Skill tool, targeting the round's effective diff, with a configurable effort level that defaults to `high`.
- **FR-002**: An entry for any other integration MUST exist only where that tool's own documentation shows a native code-review command, and planning research MUST cite that documentation. Integrations without such evidence, and integrations unknown to the map, MUST resolve to "no native review".
- **FR-003**: The `/specops-review` command MUST be rendered per installed integration, using that integration's own map entry. This is the integration each command file already belongs to at install time.
- **FR-004**: For an integration with a native command, Step 3a MUST name the exact command, its invocation mechanism, its effective-diff target, and, for built-in entries, its effort level, and MUST state that invoking it is mandatory. The conditional "if your environment provides… (e.g. …)" wording MUST be removed.
- **FR-005**: For an integration with a native command, Step 3a MUST state that a subagent performing the review needs the integration's invocation mechanism (the Skill tool for Claude Code). A run without it means the native review did not run.
- **FR-006**: For an integration with a native command, Step 3a MUST instruct recording an advisory finding with rule `native-review-not-run` whenever the native reviewer did not run. The finding names the command and the reason and is recorded through the existing finding command, analogous to `skipped-gate`. The reviewer MUST NOT fall back to a manual-only pass silently.
- **FR-007**: Step 3a MUST instruct turning the native reviewer's confirmed findings into structured findings through the existing finding commands, and MUST keep the reviewer's own review pass as complementary.
- **FR-008**: For an integration without a native command, Step 3a MUST state that no native review exists for it and instruct a manual code review of the effective diff. This is today's fallback, made explicit.
- **FR-009**: `specops.json` MUST accept an optional `native_review` block that sets the effort level and overrides the command per integration, including declaring that an integration has none. Absent the block, built-in defaults apply. Unknown keys stay preserved, as today.
- **FR-010**: An invalid `native_review` block MUST produce a configuration error with a non-zero exit at install or update. Examples are an effort level the integration's command does not accept, and `ultra` for Claude Code.
- **FR-011**: The normal SpecOps update and reinstall flow MUST replace previously installed review command files with the rendered versions. It MUST remain idempotent and MUST leave foreign files untouched.
- **FR-012**: The CHANGELOG MUST document the new per-integration instruction, the `native_review` configuration block, and the `native-review-not-run` convention.
- **FR-013**: The review process, ledger schema, finding model, revision report format, CLI command set, and approval gates MUST remain unchanged.

### Key Entities

- **Native review map entry**: One per integration. It holds the integration identifier, the native command (or none), the invocation mechanism, the accepted effort levels, and the default effort.
- **Native review configuration** (`specops.json` → `native_review`): An optional effort level and per-integration command overrides.
- **`native-review-not-run` finding**: An ordinary advisory finding, recorded by the reviewer by convention through the existing command. It carries no new schema.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With Claude Code installed, the rendered review command names `/code-review` and the Skill tool, and contains zero conditional or example wording about the native reviewer. This is verified by a test on the rendered text.
- **SC-002**: In a multi-integration fixture, 100% of rendered copies refer only to their own integration's native command or its absence.
- **SC-003**: Every built-in map entry other than Claude Code cites a documentation source. Integrations without one render as "no native review".
- **SC-004**: An already-installed project receives the new review command through one run of the existing update/reinstall flow, with no manual edits.
- **SC-005**: The existing review, ledger, and approval test suites pass without modification.

## Assumptions

- Whether the native reviewer really ran is the reviewer's responsibility, as with the rest of the semantic review. SpecOps does not verify it. The mandatory instruction plus the `native-review-not-run` convention exist to remove the ambiguity that caused the silent fallback. They are not proof.
- Integration identity comes from the per-integration install targets SpecOps already resolves from Spec Kit's configuration. No separate "active integration" resolution is needed, because each copy is rendered for the integration it belongs to.
- The built-in map for integrations other than Claude Code is established during planning research, from each tool's own documentation. Planning may conclude that an integration has none.
- Effort levels are integration-specific. For Claude Code the configured values are `low`, `medium`, `high`, `xhigh`, and `max`, with default `high`. `ultra` is user-launched and billed, so it is excluded.
- The lightweight lane has no semantic review and is out of scope.
- A ROADMAP entry for this feature is added as part of the feature's own work.
