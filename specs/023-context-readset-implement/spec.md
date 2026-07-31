# Feature Specification: Context Read-Set Consumption in IMPLEMENT

**Feature Branch**: `023-context-readset-implement`

**Created**: 2026-07-31

**Status**: Draft

**Input**: User description: "Consume the context map's minimal read set during IMPLEMENT: the implement directive resolves the phase read set with the existing `context resolve --phase` surface and scopes agent reads to it, out-of-set discoveries flow through the existing acknowledgement path, behavior degrades to a no-op without a map, and no new gate or resolution engine is introduced." (ROADMAP Feature 023, Lifecycle Coverage cycle)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Implement sessions read only what the map prescribes (Priority: P1)

A team maintains a context map describing which files matter for each area of
their repository, per lifecycle phase. Today that investment pays off at plan
time (topology validation, minimal read-set display) and at review time
(impact scoping) — but during IMPLEMENT, the phase where the agent reads the
most, nothing consumes it: the agent still decides on its own what to read.
With this feature, at the start of an IMPLEMENT session — before the first
task — the agent resolves the IMPLEMENT-phase minimal read set for the work at
hand and scopes its reads to that resolved context package instead of reading
the repository wholesale.

**Why this priority**: this is the feature's reason to exist — it closes the
Feature 009 loop by making the phase that reads the most actually consume the
minimal read set. Without it, nothing else in this feature has value.

**Independent Test**: on a repository fixture with a valid context map, run an
IMPLEMENT session under the updated directive and verify that every read the
directive prescribes for each task is covered by the resolved context package.

**Acceptance Scenarios**:

1. **Given** a repository with a valid context map and a feature in the
   IMPLEMENT phase, **When** the agent starts an implement session, **Then**
   the directive instructs it — before the first task — to resolve the
   IMPLEMENT-phase read set for the work and scope its reads to the resolved
   context package.
2. **Given** the resolved context package for a task, **When** the agent
   implements that task, **Then** the reads the directive prescribes are
   covered by the resolved package (the agent is not directed to read files
   outside it).
3. **Given** the same map and the same inputs, **When** the read set is
   resolved twice, **Then** the result is identical — resolution reuses the
   existing deterministic mechanism and introduces no new resolution engine.

---

### User Story 2 - Genuine discoveries outside the read set follow the paved road (Priority: P2)

While implementing a task, the agent discovers it genuinely needs a file
outside the resolved read set (an overlooked dependency, a config file the map
does not cover). The read set is guidance plus record — never a gate: the
agent reads the file, and acknowledges the genuine discovery through the
existing discovered-paths acknowledgement flow so the trace stays complete and
review does not later flag it as unexplained.

**Why this priority**: without a sanctioned escape hatch the scoping guidance
would either be ignored (useless) or treated as a hard boundary (harmful).
The paved road keeps the record honest while never blocking work.

**Independent Test**: on a mapped fixture, have a task require a file outside
the resolved read set; verify the acknowledgement is recorded through the
existing flow and the session proceeds without any block.

**Acceptance Scenarios**:

1. **Given** a task whose implementation genuinely requires a file outside the
   resolved read set, **When** the agent reads it and acknowledges the
   discovery through the existing acknowledgement flow, **Then** the
   acknowledgement is recorded and implementation continues unblocked.
2. **Given** an out-of-set read, **When** it occurs, **Then** no gate fails,
   no exit code changes, and no new blocking outcome is introduced — the read
   set never blocks a read.

---

### User Story 3 - Unmapped repositories behave exactly as today (Priority: P3)

A team uses the tool without a context map (or with one that fails
validation). Their implement sessions must behave exactly as they do today:
the read-set step is a supported no-op, with no new warnings, failures, or
required actions.

**Why this priority**: safe degradation is a standing rule (Rule 5) and a
precondition for shipping the directive change to every client repository —
but it protects existing behavior rather than adding new value.

**Independent Test**: run an implement session on a fixture without a context
map and verify the directive's read-set step is skipped and behavior is
indistinguishable from today's.

**Acceptance Scenarios**:

1. **Given** a repository without a context map, **When** an implement session
   starts, **Then** the read-set step is a supported no-op and the session
   proceeds exactly as it does today.
2. **Given** a repository whose context map is invalid, **When** an implement
   session starts, **Then** the read-set step degrades safely (no block, no
   crash) and the session proceeds as if no map were present.
3. **Given** an environment where the CLI is not installed, **When** the
   implement prompt runs, **Then** the existing graceful-degradation rule
   already covers the new step — the prompt still works standalone.

---

### Edge Cases

- **Task paths owned by no context**: resolution reports "no matching
  context" (an existing supported state) — for that task the agent falls back
  to reading normally; no acknowledgement is required for reads that had no
  resolved set to be outside of.
- **Map edited mid-feature**: the map digest recorded at planning already
  surfaces as a non-blocking drift warning at review (existing behavior); the
  implement session simply resolves against the current map — no new handling.
- **Corrective rounds**: re-entering IMPLEMENT to fix review findings is a new
  session — the read set is resolved again at session start, same as the first
  round.
- **Read set larger than the change**: the resolved package bounds what the
  agent is directed to read, not what it must read — reading less than the
  package is always acceptable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The implement directive MUST instruct the agent, at session
  start before the first task, to resolve the IMPLEMENT-phase minimal read set
  for the feature's work using the existing phase-aware context-resolution
  surface (`specops context resolve --phase implement` — the flag value is the
  map's lowercase phase key; the uppercase IMPLEMENT names the ledger phase),
  and to scope its reads to the resolved context package.
- **FR-002**: Read-set resolution MUST reuse the existing deterministic
  resolution mechanism and its stable machine-readable output (Feature 008);
  no new resolution engine, no change to context-resolution semantics, and no
  change to the context-map schema.
- **FR-003**: The resolved read set MUST function as guidance plus record,
  never a gate: an out-of-set read MUST NOT be blocked, fail any gate, or
  alter any exit-code contract.
- **FR-004**: The directive MUST route a genuine out-of-set discovery through
  the existing discovered-paths acknowledgement flow (Feature 010,
  `specops trace acknowledge`), so the discovery is recorded once and review
  does not later flag it as unexplained drift.
- **FR-005**: With no context map present, the read-set step MUST be a
  supported no-op: an implement session on an unmapped repository MUST behave
  exactly as it does today, with no new warnings, failures, or required agent
  actions.
- **FR-006**: With an invalid context map, the read-set step MUST degrade
  safely — no block and no crash — proceeding as if no map were present.
- **FR-007**: The directive change MUST be delivered through the product
  templates so every client repository receives it on the next extension
  install/update (Principle IV); the legacy injected-block path receives the
  equivalent text.
- **FR-008**: English and Portuguese documentation MUST be updated
  equivalently in the same change.
- **FR-009**: Any surfacing of the resolved read set in additional command
  output (for example at task start) MUST be additive-only under the Feature
  021 contract freeze — existing fields, formats, and exit codes are
  unchanged.

### Key Entities

- **Context package (resolved read set)**: the ordered, phase-specific,
  deduplicated set of files the map prescribes for the work — produced by the
  existing resolution mechanism; this feature consumes it, never redefines it.
- **Out-of-set discovery**: a file genuinely needed during implementation that
  the resolved package does not cover; recorded through the existing
  acknowledgement flow, linked to the task and a reason.
- **Implement directive**: the product-owned prompt asset that imposes the
  behavior on agents in client repositories; the sole behavioral delivery
  vehicle for this feature.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a mapped fixture, 100% of the reads the directive prescribes
  during an IMPLEMENT session are covered by the resolved context package for
  each task.
- **SC-002**: An out-of-set discovery is acknowledged through the existing
  flow and implementation proceeds unblocked — zero sessions blocked by the
  read set, and the acknowledged path passes review's drift check without
  manual explanation.
- **SC-003**: On an unmapped repository, an implement session is
  indistinguishable from today's behavior — zero new prompts, warnings,
  failures, or required actions.
- **SC-004**: No exit-code contract, gate outcome, or machine-output field
  changes shape; any new surfacing of the read set is strictly additive.
- **SC-005**: English and Portuguese documentation describe the new behavior
  equivalently in the same release.

## Assumptions

- The existing phase-aware resolution surface is sufficient for scoping
  implement-session reads (per task path or feature-level); the plan decides
  the exact invocation pattern, and only if it proves the surface insufficient
  may a new CLI surface be considered (per the roadmap's explicit non-goal).
- Whether the resolved read set is also surfaced in task-start output is a
  plan-time decision, constrained to additive-only changes under the Feature
  021 contract freeze (FR-009).
- No ledger schema change is needed: context provenance snapshotting at task
  close and review open already exists (Feature 009) and is unchanged.
- The acceptance fixture strategy follows the established pattern: behavior is
  validated through the automated test-suite fixtures, never by running the
  tool against this repository (No Self-Application).
- Issue #51 (the implement directive's corrective round lacking a
  findings-discovery step) is an independent defect fix and is not part of
  this feature's scope.
