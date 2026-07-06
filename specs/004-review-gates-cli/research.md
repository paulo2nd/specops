# Research: Deterministic Review Gates in the CLI

**Feature**: `specs/004-review-gates-cli` | **Date**: 2026-07-06

No NEEDS CLARIFICATION markers remained in the Technical Context; the items
below record the technical decisions and their verification against the
current codebase (empirical checks, not memory).

## R1 — Subprocess semantics for lint/test gates

- **Decision**: Run `lint_command`/`test_command` with
  `subprocess.run(cmd, shell=True, capture_output=True, text=True)`.
- **Rationale**: This is the exact convention `complete-task --auto` already
  uses for `test_command` (verified at `src/specops/status.py:269`).
  Commands in `specops.json` are user-authored shell strings (may contain
  pipes/flags), so `shell=True` is required; capturing keeps the report
  owner (the CLI) in control of truncation and streams. No timeout, per the
  spec clarification.
- **Alternatives considered**: `shlex.split` + `shell=False` (rejected —
  breaks compound client commands and diverges from existing behavior);
  streaming output live (rejected — the report needs the tail, and live
  streaming would interleave client output with the gate report).

## R2 — Output truncation

- **Decision**: Combine captured stdout + stderr (in that order), keep the
  last 50 lines, and prefix the block with a note of total line count when
  truncated (e.g., `[output: 412 lines, showing last 50]`).
- **Rationale**: Spec clarification (Session 2026-07-06). Tail carries the
  failure summary for common tools (pytest, ruff); the note keeps
  truncation honest.
- **Alternatives considered**: interleaved capture via a single pipe
  (rejected — loses stream identity for no reporting gain).

## R3 — Working-tree dirty check

- **Decision**: New helper `gitops.dirty_files(repo) -> list[str]` wrapping
  `repo.git.status("--porcelain")`, returning the porcelain lines.
- **Rationale**: `gitops.py` (verified) has no dirty-tree helper today;
  porcelain output is stable, and returning the raw lines gives the report
  the file list the spec requires. Keeps GitPython usage centralized in
  `gitops.py` like the existing `name_only_diff`.
- **Alternatives considered**: `repo.is_dirty()` (rejected — boolean only,
  no file list); direct `git` subprocess in `review.py` (rejected — git
  access belongs in `gitops.py`).

## R4 — Effective diff and baseline

- **Decision**: Baseline = ledger `baseline` field (written by
  `status init-spec`, verified at `src/specops/status.py:161`). Effective
  diff = `gitops.name_only_diff(repo, baseline, "HEAD")` (existing helper,
  verified). Empty result → gate fails with "no effective diff — nothing to
  review". Missing/empty `baseline` in the ledger → gate fails with an
  explanatory message (cannot determine the diff), since `init-spec` always
  records it and its absence means a hand-edited or pre-SpecOps ledger.
- **Rationale**: Same baseline notion the template and `reconcile` warnings
  already use (verified at `src/specops/reconcile.py:54`); no new concept
  introduced.
- **Alternatives considered**: merge-base with the default branch (rejected
  — introduces a second baseline notion foreign to the ledger).

## R5 — Module placement and error flow

- **Decision**: New business module `src/specops/review.py` exposing
  `run_gates(root: Path) -> str` (rendered report on success). On gate
  failure it raises `SpecopsError` whose message contains the failing
  gate's report and evidence; ledger problems surface as the existing
  `LedgerParseError` (exit 2). `cli.py` registers the command through the
  existing `_handle_errors` decorator — the single CLI-boundary mapper.
- **Rationale**: Matches the 002 errors contract exactly (business modules
  never import Typer, never print; success is returned, failure is raised;
  violations→stderr, reports→stdout). Verified against
  `specs/002-cli-hardening-dx/contracts/errors.md` and the
  `reconcile`/`consistency` wiring in `cli.py`.
- **Alternatives considered**: returning a (report, ok) tuple and mapping in
  the CLI (rejected — would create a second exit-mapping pattern beside the
  established one).

## R6 — Reconcile gate reuse

- **Decision**: Call `reconcile.run(root)` in-process; violations fail the
  gate, warnings are echoed in the report and pass (spec clarification).
- **Rationale**: `reconcile.run` (verified) already returns
  `(warnings, violations)` and raises `SpecopsError`/`LedgerParseError` for
  environmental failures — exactly the semantics the gate needs; spawning a
  child `specops` process would duplicate interpreter startup and lose the
  typed errors.
- **Alternatives considered**: subprocess `specops reconcile` (rejected —
  FR-003 forbids it; loses typed error mapping).

## R7 — Template collapse mechanics

- **Decision**: Edit `src/specops/templates/review.md` directly: replace
  Steps 2–4 with a single "Step 2 — Deterministic Gates" instructing the
  agent to run `specops review`, report its output on non-zero exit, and
  stop with REJECTED. Renumber the remaining steps; leave Step 1 (skills),
  surgical review, revision report, verdict transition, and Active Learning
  functionally unchanged.
- **Rationale**: `review.md` is a SpecOps-owned template installed verbatim
  by `initializer._install_review` (verified at
  `src/specops/initializer.py:223-234`, including skills-mode frontmatter
  wrapping) — no initializer code change is needed; re-running
  `specops init` delivers the new content (spec FR-011).
- **Alternatives considered**: marker-delimited injection into the template
  (rejected — markers are for modifying *Speckit's* files; this file is
  SpecOps' own asset).

## R8 — Report format and streams

- **Decision**: One line per gate, fixed order:
  `[gate] reconcile ... PASS` / `FAIL` / `SKIPPED (reason)`, followed by
  detail blocks (reconcile warnings, truncated output, file lists). Full
  pass report → stdout, exit 0. On failure, the report-so-far plus the
  failing gate's evidence form the `SpecopsError` message → stderr, exit 1
  (consistent with `reconcile`/`consistency` streams per FR-009).
- **Rationale**: Machine-gateable by exit code alone (SC-004) while keeping
  the human/agent-readable evidence in one place (SC-001).
- **Alternatives considered**: JSON output mode (deferred — no consumer
  yet; the future dispatch phase reads a file, not stdout).
