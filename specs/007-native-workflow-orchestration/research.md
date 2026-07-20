# Research: Native Workflow Orchestration

All decisions are grounded in the current worktree (`src/specops/*`) and Spec Kit's installed
engine (`specify_cli/workflows/*`). Each resolves a design question raised by the spec; there are
no remaining `NEEDS CLARIFICATION` markers.

## R1 — Deliver the `specops` workflow via the extension install

- **Decision**: `specops extension install` gains a step that installs the SpecOps-owned workflow
  from a new template `src/specops/templates/workflows/specops/workflow.yml` into the client repo at
  `.specify/workflows/specops/workflow.yml`, and registers a single `specops` entry in Spec Kit's
  `.specify/workflows/workflow-registry.json`. It reuses the existing fail-closed preflight,
  idempotency (`created`/`updated`/`unchanged`), and SpecOps-owned-only merge/prune logic in
  `extension.py`. `disable`/`remove` prune only the `specops` workflow entry, exactly like the
  command-prune path (`_prune_specops`).
- **Rationale**: One install brings commands **and** the workflow (Clarification Q1); reuses
  Feature 005 machinery and Spec Kit's own registry; strictly additive, so the bundled `speckit`
  workflow (`author: GitHub`, `source: bundled`) is never touched (Constitution Principle I, FR-001a).
- **Alternatives**: (a) `specify workflow add specops` as a separate manual step — rejected: two-step
  install, weaker cohesion, and no idempotency reuse. (b) Editing the bundled `speckit` workflow —
  rejected: violates Principle I.
- **Verified**: `extension.py:install` writes only `.specify/extensions.yml` today (hooks+commands);
  workflow registration is net-new but slots into the same preflight/merge/prune structure.

## R2 — CLI outcome contract (exit codes + machine-readable JSON)

- **Decision**: Formalize a stable outcome contract and expose it as data:
  - **Exit codes** (already in `errors.py`, now documented as contract): `0` = ok / gate pass;
    `1` = blocking gate result or review **REJECTED** (corrective); `2` = infrastructure / data /
    usage error (`LedgerParseError`, missing command, not a Git repo, missing integration).
  - **`--json`** added to `review`, `reconcile`, and `consistency`, emitting a stable object
    `{ "command", "outcome": "ok|blocked|error", "class": "pass|gate-rejection|infra-error",
    "verdict"?: "APPROVED|REJECTED", "diverged_dimension"?, "gates"?: [...] }` to stdout.
  - The workflow's `do-while`/`if` conditions branch on the **JSON verdict/class**, not on
    exit-code arithmetic; a hard crash of an *integration* lifecycle command is surfaced by Spec Kit's
    engine as an abort (execution failure) and recovered via `specify workflow resume`.
- **Rationale**: Distinguishes the three failure classes deterministically (FR-021/022/023) and
  disambiguates two conditions that both currently exit `1` — a review **REJECTED** (→ corrective loop)
  vs a reconcile **divergence** (→ `rebaseline`) — by *which step* ran and by the JSON `class`. JSON is
  the stable automation surface the roadmap requires; exit codes stay Principle VI-compatible.
- **Alternatives**: (a) A distinct numeric exit code per class — rejected: brittle across shells,
  breaks existing 0/1/2 consumers and tests. (b) Verdict only in human-readable text — rejected: not
  machine-parseable by `evaluate_condition`.
- **Verified**: `review.run_gates` raises `SpecopsError(report)` on first FAIL (→ exit 1 via
  `_handle_errors`) and returns the report on pass (→ exit 0); `reconcile`/`consistency` already exit
  1 on violations. `errors.py` already encodes 1 vs 2.

## R3 — Ledger↔workflow reconciliation and the divergence remedy

- **Decision**: Extend `specops reconcile` with an additional **workflow/ledger-state dimension**
  (does the ledger phase/active artifact match the effective repository and the Spec Kit workflow run
  state?) on top of its existing commit-hash reachability check. The workflow definition runs
  `reconcile` as a **fail-closed precondition step before every state-changing** `status` step, and
  **once immediately after resume** (FR-010 — not before read-only steps). An irreconcilable divergence
  exits `1` with `diverged_dimension` in JSON; the **only** remedy is the existing
  `specops status rebaseline` (Clarification Q3) — no new override/repair command (FR-012).
- **Rationale**: Reuses `reconcile.run` + the `rebaseline` escape hatch shipped in Feature 006
  (referenced by `status._identity_mismatch`); minimal new surface; keeps reconciliation a git-verifiable
  gate (Principle II/VI).
- **Alternatives**: (a) New `specops workflow repair` — rejected: duplicates `rebaseline` (Q3).
  (b) Reconcile after every step including read-only — rejected: wasteful and unnecessary (FR-010).
- **Verified**: `reconcile.run(root) -> (warnings, violations)`; `status rebaseline` exists and is the
  documented identity-divergence remedy.

## R4 — Corrective loop and terminal deterministic gate

- **Decision**: Model the corrective loop as Spec Kit's native `do-while`:
  - **body** = [ `implement` command step → `specops review` shell gate → `status transition-phase`
    step recording the verdict ],
  - **condition** = review JSON `verdict == "REJECTED"`,
  - **`max_iterations`** = the native bound (Spec Kit default when omitted).
  Each REJECTED round is recorded via `specops status transition-phase REVIEW→IMPLEMENT -r REJECTED`,
  which opens the next review cycle (existing Feature 006 behavior). **After** the loop, a **terminal
  deterministic gate** — a final `specops review`/verdict check — fails closed (exit 1) whenever the
  verdict is not `APPROVED`, so an exhausted-loop, still-rejecting feature halts (engine abort) and the
  human decides out-of-band (FR-019, Clarification/CHK012). It is **not** a native human `gate`.
- **Rationale**: No SpecOps loop control; reuses the review-cycle representation (FR-017/027);
  the terminal gate — not the bare `max_iterations` — is what prevents fall-through to completion
  (verified: `engine.py` do-while exits and continues when the bound is exhausted). Deterministic
  completion aligns with Principle VI.
- **Alternatives**: Native human `gate` as terminal — rejected: a human "approve" could bypass a
  still-failing deterministic review (CHK012).
- **Verified**: `engine.py:951-975` do-while re-evaluates `condition` per iteration and simply
  continues after `max_iterations`; `status.cmd_transition_phase` requires `-r REJECTED` for
  REVIEW→IMPLEMENT and opens a strictly-increasing review cycle.

## R5 — Human skip gate for optional quality steps

- **Decision**: Before each optional step (clarify, checklist, analyze) the definition places a native
  `gate`/`prompt` step **defaulting to run**; the human's run/skip choice is recorded via a `specops
  status` CLI step into the additive ledger `workflow.skipped_steps` field. No implicit auto-skip and
  no config-only toggle (FR-006).
- **Rationale**: Uses a Spec Kit native primitive (complement principle); records the decision in the
  authoritative ledger as FR-006 requires; auditable.
- **Alternatives**: automatic `if`-condition skip (rejected: Clarification Q2 — implicit); config-only
  (rejected: not explicit/per-run).

## R6 — Step wiring and state ownership

- **Decision**: Lifecycle steps are Spec Kit `command` steps invoking the integration's registered
  command (`speckit.specify`, `speckit.plan`, …); every deterministic SpecOps action
  (`status init-spec`/`transition-phase`/`complete-task`, `reconcile`, `review`) is a `shell` step
  invoking the `specops` CLI. All ledger mutation happens through those CLI steps (FR-008/009); Spec
  Kit's workflow state stays navigational only (FR-009).
- **Rationale**: FR-002/008 — compose native steps, keep transitions in SpecOps.
- **Verified**: the bundled `speckit` workflow already uses `command` steps for lifecycle commands and
  `gate` steps for review; SpecOps CLI subcommands (`reconcile`, `review`, `consistency`, `status …`)
  all exist and are gate-composable.

## R7 — Additive ledger `workflow` block + migration

- **Decision**: Add an additive `workflow` block to the ledger: `{ run_id, skipped_steps: [{ step,
  decision, at }] }`. Populated for new ledgers; back-filled as an empty block by a forward migration
  for existing Feature 006 v2 ledgers, gated by the existing schema-version machinery, with a migration
  test per the Feature 006 pattern (`test_ledger_migration.py`). Read-compatible with v2.
- **Rationale**: FR-006 (skip recording must live in the ledger) and FR-016 (run correlation for
  reconciliation) need durable state; Feature 006 already introduced `workflow_lane`/`active_artifact`
  in this same area, so this is a small, consistent additive extension — not the finding-schema
  redesign forbidden by FR-027.
- **Alternatives**: Store skip/run state only in Spec Kit workflow state — rejected: FR-006 mandates the
  ledger, and the ledger must stay authoritative (FR-009).
- **Verified**: `ledger.py` already normalizes `workflow_lane` and `active_artifact`; migration
  back-fill fits the existing `migration.py` forward-migration flow.
