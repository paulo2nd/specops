# Phase 0 Research: Lightweight Workflow Lane

All open decisions from the spec's *Assumptions* and the plan's Technical Context are resolved
below. There are **no remaining NEEDS CLARIFICATION** items (the Session 2026-07-24
clarifications settled: dedicated lite record, promotion at PLAN, hybrid safety detection, and
the operating model — agent-driven via directive + workflow, human only at gates).

---

## R1 — Delivery vehicle: a second additive workflow definition

**Decision**: Ship the lane as `.specify/workflows/specops-lite/workflow.yml`, registered as a
second entry (`specops-lite`) in `workflow-registry.json`, installed by generalizing
`extension.install_workflow`. The existing single-workflow install (`WORKFLOW_ID = "specops"`)
is refactored to iterate a small registry of SpecOps-owned workflow ids
(`("specops", "specops-lite")`), each with its own template path and registry entry.

**Rationale**: Feature 016's full workflow is already delivered exactly this way (template →
`_atomic_write` → upsert registry key, preserving foreign entries and never touching the
bundled `speckit` workflow). Reusing that path keeps Principle I intact and adds no new install
mechanism. `unregister_workflow` is generalized symmetrically so `extension remove` cleans up
both.

**Alternatives considered**:
- *A single workflow with an internal "lite" branch* — rejected: it would force every full run
  through lane-specific gates and blur the two lanes; the roadmap explicitly wants a *separate*
  proportional lane.
- *A SpecOps-built lane runner* — rejected outright by Roadmap Rule 8 / Principle I (no
  orchestrator; compose native steps).

---

## R2 — Lane record: dedicated `lane.yaml`, own schema (v1)

**Decision**: A new file `specs/<feature>/lane.yaml` with its **own** `schema_version` starting
at `1`, independent of the full ledger's `CURRENT_SCHEMA = 6`. `status.yaml` is **not** created
while a lane is open. The record is mutated only through `specops lane *`; direct edits are out
of contract (Principle II).

**Rationale**: The Q1 clarification chose a dedicated lightweight store, not a "lite mode" of
`status.yaml`. A separate schema means: (a) no migration of existing v6 ledgers is required;
(b) the lite record can stay genuinely minimal (no phases, no per-task array); (c) the
full-ledger module (`ledger.py`) stays uncoupled from lane concerns. The lane record carries
just: identity/branch/baseline, eligibility answers, an ordered list of stop-and-ask
decisions/attestations, and the terminal outcome.

**Alternatives considered**:
- *Reuse `status.yaml` at `workflow_lane: "lite"`* — rejected by Q1; also would drag the full
  phase machine and L1 task invariants onto a lane that has neither.
- *No SpecOps record at all (git-only)* — rejected by Q1; loses mid-lane auditability of the
  eligibility basis and stop-and-ask decisions.

---

## R3 — The reserved `workflow_lane` field and promotion provenance

**Decision**: On **promotion**, the synthesized `status.yaml` keeps `workflow_lane: "full"`
(it is now a full-lane feature) and additionally records lane provenance: the originating lane
id and the fact that it was `promoted_from_lane`. The pre-existing reserved field
(`ledger.DEFAULT_WORKFLOW_LANE = "full"`, already emitted by `migrate_to_current`) needs no
schema bump — provenance is carried in a small additive block on the synthesized ledger.

**Rationale**: `workflow_lane` was clearly pre-provisioned for this feature (the only two lanes
are "full" and the new lite lane). With the Q1 dedicated-record decision, the lite lane does not
live in `status.yaml`, so the field's role narrows to marking the full ledger and its
provenance. Keeping it additive avoids touching the v6 schema or any migration path.

**Alternatives considered**:
- *Bump `status.yaml` to v7 to add a formal `promoted_from` block* — deferred: not needed; an
  additive key on a v6 ledger is sufficient and migration-free. Revisit only if a later feature
  needs to query provenance structurally.

---

## R4 — Promotion synthesizes a full ledger positioned at PLAN

**Decision**: `specops lane promote` builds a full `status.yaml` from the `status.yaml`
template, sets `current_phase: "PLAN"`, `baseline` = the lane's baseline, imports the branch
commits (baseline→HEAD via `gitops.commits_in_range`) as existing work/recovery context, copies
the lane's eligibility answers + stop-and-ask decisions + any gathered evidence into the ledger,
then marks the `lane.yaml` record `resolved: promoted`. It reuses `status.cmd_init_spec`'s
template-fill logic (extracted/reused, not duplicated) and `ledger.write_new`.

**Rationale**: Q2 chose PLAN so a now-non-trivial change gets real spec/plan/review before DONE.
Positioning at PLAN (not SPECIFY) reflects that a spec-level description already exists implicitly
(the change is underway) while still requiring `plan.md` + tasks + review. Commit preservation is
guaranteed because promotion never rewrites history — it only reads `baseline..HEAD` and records
those shas; `gitops.is_ancestor` verifies each recorded commit remains reachable (Principle II).

**Alternatives considered**:
- *Resume at IMPLEMENT/REVIEW* — rejected by Q2: skips planning for a change that grew past the
  lane, weakening the audit story.
- *Human-chosen re-entry phase* — rejected by Q2: extra decision point and forked acceptance
  tests; PLAN is the safe default.

---

## R5 — Hybrid safety-core detection

**Decision**: `safety.py` exposes a deterministic detector over the effective diff
(`gitops.effective_diff_status`, baseline→HEAD or staged) that flags the five diff-detectable
categories, plus a model for the always-on attestation:

| Category | Signal (generic, built-in defaults; overridable in `specops.json`) |
|----------|--------------------------------------------------------------------|
| persisted-schema / migration | path globs (`**/migrations/**`, `**/*.sql`, `**/alembic/**`, `**/schema.*`) |
| secrets | filename/patterns (`**/.env*`, `**/*secret*`, `**/*.pem`, `**/id_rsa*`, high-entropy add heuristics) |
| dependency change | manifest/lock paths (`**/requirements*.txt`, `**/pyproject.toml`, `**/package.json`, `**/*.lock`, `**/go.mod`, `**/Cargo.toml`, …) |
| public-contract surface | configurable path set (defaults to none until configured) + generic markers |
| destructive / irreversible | diff status `D` on non-trivial paths, deletions of whole modules/data dirs |

The sixth category — **ambiguous / unconfirmed root cause** — is *not* diff-detectable and is
enforced by an **always-on** attestation checkpoint the lane presents on every pass (a native
`prompt`/`gate` step recorded via `specops lane attest`).

**Rationale**: Q3 chose hybrid. Built-in generic defaults ensure SC-002 holds for a zero-config
repo (a repo cannot silently disable the core by omitting config); `specops.json` overrides keep
it tunable without stack coupling (Principle V). Detection is a pure function of the diff → fully
unit-testable per category. The attestation is a deterministic step → testable that it is always
presented and that "ambiguous" halts.

**Alternatives considered**:
- *Deterministic-only (drop the attestation)* — rejected by Q3: a real hole in the guarantee.
- *Always-ask full six-category checklist on every close* — rejected by Q3: reintroduces the
  ceremony the lane exists to remove.
- *Entropy/AST content analysis for secrets/contracts* — deferred: heavier and stack-adjacent;
  generic path/pattern heuristics + attestation are sufficient for v1 and stay domain-agnostic.

---

## R6 — Closure reuses `preflight` + Feature 012 evidence

**Decision**: `specops lane close` runs the existing `review` (preflight) gate-profile suite
against the change and records the resulting Feature 012 structured evidence, then writes a
concise retrospective (a small structured block on `lane.yaml` plus a rendered `retrospective.md`
projection under `specs/<feature>/`). Closure is fail-closed: a *required* gate failure or
unavailability blocks (exit `1`), mirroring the full lane.

**Rationale**: Reuse over new surfaces (Principle III + Roadmap Rule 8). The gate suite, the
outcome taxonomy (`required|optional|skipped|cached|failed|unavailable`), and evidence records
already exist and are exactly what "applicable deterministic gate profiles + structured
evidence" (FR-009/FR-011) require. The retrospective mirrors the `handoff render` pattern
(authoritative structured state → rendered projection) established in Feature 011.

**Alternatives considered**:
- *A parallel lite evidence format* — rejected: duplicates Feature 012 and fragments audit
  tooling.

---

## R7 — CLI surface: a `specops lane` sub-app

**Decision**: Add a `lane` Typer sub-app mirroring the existing sub-app pattern
(`status`/`trace`/`handoff`/`gate`): `start`, `status`, `check`, `attest`, `close`, `promote`.
All emit human text by default and a stable object under `--json` via `outcome.render`; all are
non-interactive (Principle VI). Human decisions (eligibility confirm, halt/promote choice,
root-cause attestation) are captured by native workflow `gate`/`prompt` steps whose chosen value
is passed to the corresponding `lane` command as an argument.

**Rationale**: Consistency with the established CLI architecture; keeps every human interaction
in the workflow layer and every deterministic effect in a composable, exit-code-gated command.
The `lane` sub-app is **agent/workflow-facing**, not a human workflow — see R9.

**Alternatives considered**:
- *Top-level flat commands* (`specops lane-start`) — rejected: the sub-app grouping is the
  repo's established idiom and reads better in `--help`.

---

## R9 — Operating model: agent-driven, human only at gates (directive + workflow)

**Decision** (clarified Session 2026-07-24): the human never invokes a `specops` command. Deliver
the lane through **both** Principle IV vehicles, mirroring the full lane:
1. A new injected directive `src/specops/templates/directives/lite.md` — installed via the same
   extension/initializer mechanism as the existing lifecycle directives, injected at the
   lifecycle-entry seam (the specify stage / pre-lifecycle hook). It instructs the agent to
   recognize a small/reversible change, **propose** the lightweight lane through a human
   confirmation (never auto-classify / never auto-enter), and on confirmation drive the
   `specops-lite` workflow. It degrades to a no-op when SpecOps is not initialized.
2. The `specops-lite` workflow (R1) as the execution backbone — every `specops lane *` step is a
   native `shell`/`command` step run by the agent/engine; the only human steps are native
   `gate`/`prompt` (eligibility, root-cause attestation, halt/promote).

`extension.py` gains the directive in its injected-directive set (and `unregister` removes it);
`initializer.py` mirrors it on the legacy marker-block path for parity with the other directives.

**Rationale**: FR-022/FR-023 and the user's explicit intent ("specops identified by the agents in
the speckit workflow, without the human driving the CLI"). Using both vehicles is exactly the
Principle IV contract the constitution already defines for the full lane; the directive is what
makes SpecOps *recognized and driven by agents* rather than a CLI the human must operate. Adding
it is a MINOR constitution amendment (directive list extended) authored during
`/speckit-implement`, per the established pattern.

**Alternatives considered**:
- *Workflow-only, explicit selection* — rejected by the Session 2026-07-24 re-open: it makes the
  agent merely *execute* a pre-chosen lane rather than *recognize and propose* it, so a human
  still has to know to pick the lite workflow.
- *Directive-only (no workflow)* — rejected: loses the engine's structure, resume, and native
  gate handling; the lane would be an unstructured agent protocol.

**No auto-classification guarantee**: the directive proposes; a human confirmation gate is
mandatory before `lane start`. This upholds the spec non-goal and Design Philosophy (record, do
not silently decide).

---

## R8 — No new runtime dependencies; test strategy

**Decision**: Implement entirely with Typer + PyYAML + GitPython. Tests: per-category unit tests
for `safety.py`, schema/lifecycle/promotion-synthesis unit tests for `lane.py`, additive-install
tests for the generalized `extension.py`, and integration tests driving the two headline flows
(clean close with retrospective+evidence; safety trip → lossless promote). Fixtures under
`tests/fixtures/lane/`. The workflow YAML's step *structure* is validated statically (as the
full workflow's is); its end-to-end agent behavior needs a live integration and is not
CI-reproducible (documented, mirroring the note already in the full `workflow.yml`).

**Rationale**: Matches the Constitution's Technical Constraints (deps limited to the three) and
the existing Feature 007/012/016 test posture. No self-application (fixtures only).
