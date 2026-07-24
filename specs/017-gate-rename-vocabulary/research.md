# Research: Gate Rename & Vocabulary Pass

**Feature**: 017 | **Date**: 2026-07-24 | **Phase**: 0 (Outline & Research)

All Technical Context items were resolvable from the repository; there are no open
`NEEDS CLARIFICATION` markers. The two spec-level ambiguities were resolved in
`/speckit-clarify` (conservative sweep; non-suppressible notice). This document records
the implementation-level decisions and the conservative-sweep catalogue.

## D1 — How to register `preflight` + the `review` alias (Typer)

**Decision**: Extract the current `review()` body into a private shared implementation
`_run_gate(command_name: str, json_out, soft, sarif)`. Register two Typer commands that
delegate to it:

- `@app.command("preflight")` → `_run_gate("preflight", …)` (canonical).
- `@app.command("review", help="[DEPRECATED — use 'specops preflight'] …")` → writes the
  single custom deprecation notice to stderr, then `_run_gate("review", …)`.

The shared impl passes `command_name` straight into `outcome.render(command_name, …)` so
the JSON `command` value mirrors the invoked name (FR-004). Every option (`--json`,
`--soft`, `--sarif`) is declared identically on both commands.

**Rationale**: `outcome.render()` already takes `command` as its first parameter
(`outcome.py:78`); only the CLI's hard-coded `"review"` literal needs to become the
invoked name. Twin registration is the minimal, idiomatic Typer way to alias a command
while keeping one behavior source.

**Do NOT use Click/Typer `deprecated=True`** (empirically verified against the installed
Typer 0.27.0 / Click 8.4.2): a command with `deprecated=True` **auto-emits its own stderr
line** on every invocation — `"DeprecationWarning: The command 'review' is deprecated.\n"`
— which (a) would be a *second* line on top of our custom notice, breaking FR-002/SC-002
("exactly one deprecation line"), and (b) does not name `specops preflight` or the removal
window, so it fails FR-002's content requirement on its own. FR-014's help marker is
therefore satisfied by putting an explicit `[DEPRECATED — use 'specops preflight']` prefix
in the command's `help`/`short_help` text, not by the `deprecated=` flag.

**Alternatives considered**:
- *A hidden Click alias group / callback shim* — more machinery than a second
  `@app.command`; rejected as over-engineering for a two-name alias.
- *Rename the function/module `review.py` → `preflight.py`* — internal identifier, no
  user-facing surface; out of scope (FR-012). Rejected to keep the diff minimal and avoid
  touching import sites that downstream features bind to.
- *Emit the notice inside `_run_gate` when `command_name == "review"`* — viable, but
  keeping the notice in the alias command body (not the shared impl) makes the
  canonical path provably notice-free and keeps the shared impl name-agnostic.

## D2 — Where and how the deprecation notice is emitted

**Decision**: A single line to **stderr** via `typer.echo(<notice>, err=True)`, emitted
once per `review` invocation, unconditionally (no flag, no env var — Clarification Q2).
It is written **before** the gate runs so it appears even when the gate later exits
non-zero. The canonical `preflight` command emits nothing extra. This is the **only**
source of the deprecation line — see D1: the `deprecated=True` flag is deliberately NOT
used because it would auto-emit a competing second line, so the notice is entirely
hand-emitted and its wording/content is fully under our control.

Proposed text (implementation may refine wording, not behavior):
`specops review is deprecated; use 'specops preflight' (this alias will be removed no earlier than the next minor release).`

**Rationale**: FR-002/FR-003. stderr keeps stdout (including `--json`) byte-identical for
consumers that parse stdout (`test_review_cli.py` reads `r.stdout` for JSON; separate
`result.stderr` capture proves the split). Emitting before execution guarantees the nudge
is not swallowed on a rejecting/erroring run.

**Alternatives considered**: Python `warnings.warn` / `DeprecationWarning` — rejected:
not reliably visible to CLI users, filtered by default, and harder to assert in tests.

## D3 — Output command-label value under the alias (FR-004)

**Decision**: Mirror the invoked name. `specops preflight …` renders `"command":
"preflight"`; `specops review …` renders `"command": "review"`. No change to `outcome.py`.

**Rationale**: This is the least-breaking option (spec Assumption): existing `specops
review --json` consumers observe byte-identical stdout, and new `preflight` consumers get
the honest name. The `"command"` **key** is unchanged, so SC-005 (no JSON key renamed)
holds — only a free-form string value differs by invocation, which it already did per
command. No `OUTPUT_VERSION` bump is warranted (shape unchanged).

**Alternatives considered**: Always emit `"preflight"` regardless of invocation — rejected:
would change `specops review` stdout and break byte-stability during the deprecation window.

## D4 — Which occurrences change vs. which are frozen

**Decision**: Change only **living** surfaces that name the gate; leave frozen history and
reserved "review" usages untouched.

Change:
- `src/specops/cli.py` (command defs + the line-284 comment).
- `src/specops/templates/review.md` — the `/specops-review` directive's instruction to
  run the gate (`Run specops review` → `Run specops preflight`); the directive stays
  named review.
- `src/specops/templates/workflows/specops/workflow.yml` — the two `shell: specops
  review` steps (`review-soft`, `terminal-gate`) → `specops preflight`, plus the header
  comment. **Do not** touch `command: specops.review` (the semantic directive).
- `.specify/memory/constitution.md` — gate references → preflight (PATCH amendment, D6).
- `README.md`, `README.pt-br.md` — gate references → preflight + document the alias.
- `CHANGELOG.md` — a new entry (not a rewrite of historical entries).

Do **not** change (over-correction guard, FR-013):
- `command: specops.review` in workflow.yml, the `/specops-review` directive name, the
  `REVIEW` phase identifier, the `APPROVED/REJECTED` verdict, `review_cycles` ledger keys.
- Any artifact under `specs/004|007|011|012|016-*` (frozen history, roadmap Rule 7).
- Internal identifiers `review.py`, `review_mod`, `run_gates`, etc. (out of scope, FR-012).

**Rationale**: Separates "the gate" (renamed) from "genuine review" (reserved) and honors
the historical record. The workflow's `command: specops.review` is the exact reserved case
the spec warns about.

## D5 — Deprecation window & changelog

**Decision**: The alias ships in this feature and is **not** removed here. Removal is a
separate future change, no earlier than the next MINOR release and never in a PATCH
(FR-006). The CHANGELOG entry states: the rename, that `specops review` is a deprecated
alias, the removal window, that behavior is unchanged, and the one-line migration ("move
callers to `specops preflight`").

**Rationale**: FR-006/FR-015; matches the repo's "only dated CHANGELOG sections are
tagged" practice — this lands under `[Unreleased]` until a release is cut.

## D6 — Constitution amendment classification

**Decision**: PATCH bump 1.8.0 → 1.8.1. Update the Sync Impact Report comment; change gate
references to `preflight`; explicitly reserve "review" for the phase, the `/specops-review`
directive, and the verdict. No principle text is removed or redefined.

**Rationale**: The Governance section requires a version bump + Sync Impact Report +
template propagation for any constitution change, and classifies wording clarifications as
PATCH. Propagation targets (directive template, workflow.yml) are already in this change set.

## D7 — Test strategy for the rename

**Decision**:
- `test_workflow_definition.py`: update the run-string assertions for `review-soft`
  (`… specops preflight --json --soft`) and `terminal-gate` (`== "specops preflight"`);
  **keep** `semantic-review.command == "specops.review"` unchanged.
- `test_review_cli.py`: re-point the behavior assertions (verdict, exit code, stdout,
  `result.stderr == ""`) to `specops preflight`; add an alias test class asserting that
  for the same repo state `specops review` yields byte-identical stdout and identical exit
  code to `preflight`, plus **exactly one** stderr line, and that `--json` stdout is clean
  JSON. Consider renaming the file to `test_preflight_cli.py`.
- `test_outcome_contract.py`: add a `render("preflight", …)` case asserting `"command":
  "preflight"`; the existing `render("review", …)` cases remain valid (render is generic).

**Rationale**: Proves FR-001..FR-005 and SC-001/SC-002/SC-005 directly; guards FR-013 by
pinning the untouched semantic-review command string.

## D8 — Conservative vocabulary sweep catalogue

Per Clarification Q1, the gate is the **only** rename; every other overloaded user-facing
term is **documented** here with its disposition (SC-008). Candidates examined:

| Term | Where it appears | Overloaded? | Disposition |
|---|---|---|---|
| `review` (the gate command) | `specops review` CLI, workflow shell steps, docs | **Yes** — names a mechanical gate "review" | **RENAME → `preflight`** (the whole feature) |
| `review` (the phase) | `REVIEW` phase id, `status transition-phase` | No — genuinely the review phase | Keep (reserved); documented |
| `review` (the directive) | `/specops-review`, `command: specops.review`, `templates/review.md` | No — genuinely orchestrates the agent's review | Keep (reserved); documented |
| `review` (the verdict/cycle) | `APPROVED/REJECTED`, `review_cycles` | No — the review's outcome | Keep (reserved); documented |
| `gate` | `specops gate list/validate/report`, "gate profiles", native Spec Kit `gate` step | Mild — SpecOps gate *profiles* vs Spec Kit human `gate` step | **Document** — already disambiguated in the constitution/README (Feature 012 note); no rename. Renaming would churn a stable command surface and collide with the native term. |
| `reconcile` | `specops reconcile` | No — accurately names the ledger/repo reconciliation | Keep; documented |
| `consistency` | `specops consistency` | No — accurate | Keep; documented |
| `handoff` | `specops handoff …` | No — accurate (corrective handoff) | Keep; documented |

**Outcome**: exactly one rename (`review → preflight`); all other terms documented as
"keep", none left unaddressed — satisfying the conservative-sweep invariant (SC-008).
`gate` is the only near-miss and is deliberately kept because it is a stable command
surface with existing disambiguation and a rename would fight Spec Kit's own vocabulary.
