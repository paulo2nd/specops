# Phase 0 — Research: Structured Corrective Handoff

All decisions are grounded in the current worktree (Feature 006 ledger v4, Feature 009
provenance, Feature 010 `trace.py`). No `NEEDS CLARIFICATION` remain; the three
`/speckit-clarify` answers and the 15 deferred `handoff.md` checklist items are resolved here.

Format per decision: **Decision** / **Rationale** / **Alternatives rejected**.

---

## R1 — Ledger v4 → v5: where findings and handoffs live

**Decision**: Nest a `handoff` object **inside each `review_cycles[i]` record**:
`handoff: {authorized_paths: [str], closed_at: str|null, findings: [Finding]}`. A round's
findings live in that round's handoff. No top-level findings/handoffs list is added. Bump
`ledger.CURRENT_SCHEMA` 4 → 5; a deterministic migration backfills nothing onto findings
(pre-feature cycles simply have no `handoff` key) — mirroring `backfill_acknowledgements`.

**Rationale**: The handoff is *defined* as bound to a review-cycle round (FR-002); the ledger
already owns `review_cycles` with `round`/`result`/`context_provenance` (Feature 006/009).
Nesting extends that record without inventing a parallel keyspace and keeps carry-forward
(FR-024) trivially correct: a round-1 finding stays in round-1's handoff at state `VERIFIED`,
round-2 findings go in round-2's handoff, and the feature-global approval scan is a flat map
over all cycles' findings. This is the CHK032 compatibility guarantee — additive, existing
cycle records read unchanged.

**Alternatives rejected**: (a) Top-level `findings`/`handoffs` lists — duplicates the
round↔cycle binding already in `review_cycles` and needs a foreign key back to the round.
(b) A separate `findings.yaml` file — violates single-ledger repo-as-state (Principle II) and
the Feature 006 CAS/atomicity guarantees.

## R2 — Finding ID scheme (CHK001)

**Decision**: `R<round>-F<NN>` — the review-cycle round, then a zero-padded 2-digit sequence
assigned in creation (append) order within that round (`R2-F01`, `R2-F02`, …). IDs are stable:
neither the round nor the per-round sequence is ever renumbered. A recurrence at a previously
seen `file:line` in a later round is a **new** finding with a new `R<round>-F<NN>` (FR-024).

**Rationale**: Deterministic and human-readable; round-scoping makes the ID self-locating and
immune to cross-round renumber churn; append-order sequence is reproducible from the ledger.

**Alternatives rejected**: Content-hash IDs (opaque; churn whenever action/rule text is edited).
Global `F-NNN` (a discarded/renumbered round would shift later IDs, breaking stability).

## R3 — Finding record shape & field optionality (CHK005)

**Decision**: Fields — `id`, `severity` (`blocking`|`advisory`), `rule` (str), `file`
(repo-relative, normalized via `trace._norm`), `line` (int|**null**, optional), `action` (str),
`expected_evidence` (str descriptor), `closure_criteria` (str), `state`
(`OPEN`|`FIXED`|`VERIFIED`), and the correction link set filled at `FIXED`: `task` (str|null),
`commits` (list[str], default `[]`), `evidence` (str `<CLASS>:<summary>` |null), plus
`fixed_at`/`verified_at` (str|null, aware timestamps). Presence rules: `expected_evidence` and
`closure_criteria` are **required for `blocking` findings** (a blocking finding missing closure
is an FR-010(b) defect); **optional for `advisory`**. `line` is optional. `task`/`commits`/
`evidence` are null until `FIXED`.

**Rationale**: Mirrors the shape `trace._findings` already emits (`file`/`line`/`text`/`round`)
plus the lifecycle/link fields the spec requires; optionality matches the gate semantics
(advisory never gates, so its closure is not load-bearing).

**Alternatives rejected**: Making closure mandatory for advisory too — no gate consumes it and it
would burden the common non-blocking note.

## R4 — Handoff record shape & the zero-findings case (CHK006)

**Decision**: `handoff` is present on a cycle **only once the round records at least one finding**.
`authorized_paths` defaults to `[]` and is set/extended by `handoff authorize`. `closed_at` is
`null` until close (FR-023). A review round with zero findings has **no** `handoff` key — the
zero-findings edge (approval unblocked) is exactly "no handoff present" (FR-007).

**Rationale**: Absence-as-zero keeps the degrade path (FR-008) and the zero-findings edge a single
predicate ("no structured findings on any cycle"), identical in spirit to Feature 010's
"acknowledgements: [] ⇒ everything unexplained" fallback.

## R5 — Lifecycle state machine, preconditions & the two-surface coherence (CHK018/CHK019/CHK021/CHK027)

**Decision**: Monotonic `OPEN → FIXED → VERIFIED`.
- `OPEN → FIXED` precondition: a **known** task id (in ledger tasks), **≥1 commit**, and an
  **actual evidence** `<CLASS>:<summary>` string. Missing any → usage error **exit 2**, state
  unchanged.
- `FIXED → VERIFIED` precondition (mechanical): the actual linked evidence is present and the
  task/commit links resolve, satisfying the finding's expected-evidence descriptor. Recorded
  during a review pass; **no auto-verify**. Precondition unmet, or reached from `OPEN`, or any
  backward move → usage error **exit 2**, state unchanged (FR-004, FR-006).

**Two-surface coherence** (CHK019/CHK021): the **transition guard** is the primary defense — it
makes a `VERIFIED`-without-evidence or a duplicate-ID state *unreachable* through the CLI
(exit 2). **Validation** (`handoff validate`, exit 1) is the **audit backstop** — it detects such
a state only if a ledger was hand-corrupted or written by a future/foreign tool. The two never
contradict: the guard prevents, validation reports; they cover disjoint entry paths (live CLI vs
external corruption). Duplicate-ID: creation rejects a colliding id as usage error (exit 2);
validation reports a pre-existing duplicate as a defect (exit 1).

**Rationale**: Same primary-guard/audit-backstop split Feature 006 already uses (invariants block
writes *and* are re-validated on read). Documenting it removes the apparent FR-006↔FR-010(c)
tension.

## R6 — Blocking-approval invariant wiring (FR-007)

**Decision**: Add `handoff.blocking_approval_check(data) -> list[str]` returning the ids of
unverified `blocking` findings across **all** cycles' handoffs (feature-global). Call it inside
`status.cmd_transition_phase` at the existing DONE/APPROVED gate (status.py ~573–603) **before**
recording `APPROVED` on the open cycle and before entering `DONE`; a non-empty result raises the
fail-closed error (exit 1) naming the findings. **Degrade** (FR-008): when no cycle has a
`handoff`, the check returns `[]` and the pre-existing Feature 006 cycle-result gate governs
unchanged — an upgraded/legacy repo is never retroactively blocked (Rule 5).

**Rationale**: Composes the existing gate (Rule 8, FR-007) at its single choke point; the check is
a pure read over the ledger, so it also drives `handoff report`'s "remaining blocking" set.

**Alternatives rejected**: A second review gate in `review.GATE_ORDER` — the approval decision is
a phase transition, not a `specops review` gate; putting it in the transition keeps one authority.

## R7 — Handoff close: closable vs closed (FR-023)

**Decision**: `specops handoff close` verifies every `blocking` finding in the current round's
handoff is `VERIFIED`, then stamps `closed_at` (recorded, never a deletion); idempotent re-close
is a no-op (exit 0); an unverified blocking finding fails closed (exit 1) naming it. The
**approval invariant (R6) keys on closability** (all blocking `VERIFIED`), **not** on `closed_at`
being set — so a fresh session that recovers a fully-verified handoff is never blocked merely for
not having called `close`. `close` is the audit stamp and the review directive's explicit final
action; `closed_at` is surfaced in reports.

**Rationale**: FR-007's own wording is "while the round's handoff is not **closable**." Keying the
gate on derivable finding state (not a separate flag) preserves the resumability guarantee (FR-020,
SC-002) — repository state alone determines the gate outcome.

## R8 — Rendering `revision-X.md` from structured state (FR-013, CHK008)

**Decision**: The review directive **authors structured findings first** (via `handoff finding
add`), and `revisions/revision-X.md` is **rendered** from the ledger. The rendered per-finding
line keeps the existing **`[File]:[Line] - <action>`** format (matching `trace._FINDING_RE`), with
`APPROVED` and `Skipped gate:` lines preserved. Stable finding **IDs live in the ledger**, not in
the human line, so the Markdown stays byte-compatible with prior consumers (SC-006) and Feature
010's legacy regex still matches. Render order is the canonical order (R11).

**Rationale**: Keeping the human line unchanged is what makes "compatible with prior revision-report
consumers" objectively true; putting IDs in the ledger (surfaced by `handoff report`) avoids
breaking the 010 parser while still delivering per-finding identity.

**Alternatives rejected**: Prefixing the line with the ID (`R2-F01 file:line - action`) — breaks
`trace._FINDING_RE` and prior consumers.

## R9 — Feature 010 trace re-sourcing (FR-015, CHK033)

**Decision**: Change `trace._findings(feature_dir)` to prefer **structured findings** from the
ledger's cycle handoffs when any exist — emitting each finding's stable `id`, `file`, `line`,
`round`, mapped from R3 — and to **fall back** to parsing `revisions/revision-*.md` (its current
behavior) when no cycle has a handoff. The Feature 010 report/graph contract is unchanged except
that finding nodes now carry an `id` when structured (additive field).

**Rationale**: Legacy 010 fixtures have no handoffs → they hit the unchanged fallback (no
regression, SC-009). Structured ledgers resolve to stable IDs (the per-finding anchor 010 deferred).

## R10 — Legacy revision-prose import (FR-014)

**Decision**: `specops handoff import [--round N]` reads existing `revision-X.md`
`[File]:[Line] - <action>` lines (via the same regex 010 uses) and creates structured findings
preserving `file`, `line`, and `action` verbatim, assigning `R<round>-F<NN>` ids and **severity
`advisory`** (state `OPEN`) by default. Import is **explicit/opt-in** and never runs implicitly.

**Rationale**: Zero-loss import (SC-007) for audit continuity. Defaulting imported findings to
`advisory` guarantees import can never *retroactively block* an already-approved feature (Rule 5,
FR-008); a maintainer may escalate to `blocking` deliberately. Pure-legacy repos that never import
keep reading via the FR-014 supported-prior-shape path.

## R11 — Canonical ordering & determinism (FR-025, CHK004/CHK013/CHK014/CHK015)

**Decision**: Canonical finding sort key = **(round asc, severity [`blocking` < `advisory`],
file [Unicode codepoint], line [nulls first], finding id)**. All outputs — human report, JSON,
`handoff validate`, and rendered `revision-X.md` — use it. Serialization is canonical: JSON via
`outcome.render` (compact, key order fixed by construction), `\n` newlines, UTF-8, **no wall-clock
timestamps in read-command output** (stored `*_at` fields are ledger state, not echoed by
read commands; only stable ids/paths/states are emitted). ID stability is verified by
re-render/re-read equality across sessions (SC-001).

**Rationale**: Reuses Feature 008/009/010's exact determinism recipe (codepoint order, no
timestamps in read output), so byte-for-byte reproducibility (CHK014) is objectively testable.

## R12 — Status enumeration, exit taxonomy & `output_version` (CHK002/CHK010/CHK018)

**Decision**: A single `_STATUS_CLASS` table (mirroring `trace`) is the source of truth. Statuses:
`finding-recorded`, `handoff-authorized`, `finding-fixed`, `finding-verified`, `handoff-closed`,
`handoff-already-closed`, `validate-ok`, `report-ok` → class **PASS** (exit 0);
`approval-blocked`, `close-blocked`, and each validation defect (`uncovered-blocking`,
`dangling-reference`, `missing-closure`, `contradictory-state`, `duplicate-id`) → class
**GATE_REJECTION** (exit 1); `illegal-transition`, `precondition-unmet`, `unknown-task`,
`unknown-finding`, `duplicate-id-create`, `not-a-repo`, `bad-args` → class **INFRA_ERROR**
(exit 2). Every JSON output embeds `output_version = 1` (FR-012). Human vs JSON **parity**
(CHK010): both render from the same in-memory result object, so the finding chain and the
remaining-blocking set are identical by construction.

**Rationale**: Reuses `outcome.render` and the `0/1/2` taxonomy (Principle VI); the single table
makes the CHK018 overlap audit mechanical (no status maps to two classes).

## R13 — CLI surface: the `handoff` Typer group (FR-002/004/005/006/010/012/023, CHK009)

**Decision**: A new `handoff_app` group (mirroring `trace_app`) registered under
`specops handoff`, with a `HandoffResult` dataclass + `_emit_handoff` bridge (mirroring
`TraceResult`/`_emit_trace`):
- `handoff finding add --severity --rule --file [--line] --action --expected-evidence --closure`
  (creates the current round's handoff if absent; assigns the R3 id).
- `handoff authorize --path <p> [--path …]` (set/extend authorized corrective paths).
- `handoff finding fix <ID> --task <t> --commit <sha> [--commit …] (--evidence <e> | --auto)`.
- `handoff finding verify <ID>` (mechanical precondition; review pass).
- `handoff close`.
- `handoff validate [--json]`, `handoff report [--json]` (read-only).
- `handoff import [--round N]` (R10).
The "current round" is the latest `review_cycles` entry (the open corrective cycle). State-changing
commands route through `status._load_for_write` + `status._finalize` (identity gate + CAS +
atomic write); reads use `ledger.load_raw`.

**Rationale**: One cohesive surface matching the roadmap's "create, validate, report, close" plus
the three transitions; identical plumbing to the proven Feature 010 CLI.

## R14 — Constitution amendment (MINOR 1.6.0 → 1.7.0)

**Decision**: A **MINOR** amendment extends the Principle IV **Token-Optimized Review** directive
(the review agent now authors *structured* findings via `handoff finding add`, runs `handoff
finding verify`, and `handoff close` instead of writing free-form `revision-X.md` prose — the file
becomes a rendered projection) and the **Ledger & Phase Wiring** directive (implement marks
findings `FIXED`). Additive (no principle removed/redefined), propagated to
`src/specops/templates/directives/` and `src/specops/templates/review.md`, submitted in the same
change set for explicit human approval (roadmap §3).

**Rationale**: The delivered lifecycle behavior (structured handoff replaces prose) is only real if
the review/implement directives drive it; Governance requires the version bump + template
propagation.

## R15 — Validated dependencies (CHK043)

**Decision**: Each load-bearing dependency is an existing, validated capability bound to a concrete
symbol: **Feature 006 ledger** — `ledger.load_raw`, `ledger.save` (atomic + revision-CAS),
`review_cycles` records, `migrate_to_current`/`CURRENT_SCHEMA`, `validate_invariants`;
**write path** — `status._load_for_write`/`status._finalize` (identity gate + CAS);
**Feature 010** — `trace._norm` (path normalization), `trace._FINDING_RE` (legacy line format),
the finding↔path↔cycle linkage and `authorized_paths`↔drift relationship; **evidence** — the
`<CLASS>:<summary>` string validated by `status._validate_evidence` (Principle III);
**reconcile** — commit-existence authority (`reconcile`, Principle II) that validation defers to
for dangling commit references. No new runtime dependency (Typer/PyYAML/GitPython only).

**Rationale**: Turns the spec's Assumptions into concrete, verifiable bindings so the plan's paths
are empirically anchored (roadmap §3).
