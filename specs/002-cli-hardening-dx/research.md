# Research: CLI Hardening & Developer Experience

**Feature**: `specs/002-cli-hardening-dx` | **Date**: 2026-07-05

No NEEDS CLARIFICATION markers remained in the Technical Context; the four
spec-level decisions were resolved in `/speckit-clarify` (strict evidence
grammar, plain-text `show`, CI on 3.10 + latest, 85% blocking coverage).
This document records the implementation-level decisions and their rationale.

## R1 — Review-result application order (P1 bug)

**Decision**: In `cmd_transition_phase`, validate and apply the supplied `-r`
result in this order: (1) normalize/validate result value — anything other
than APPROVED or REJECTED fails with exit 1 before any state is read;
(2) for `DONE` with `-r APPROVED`: write APPROVED + completion date onto the
latest open review cycle **in memory**, then evaluate the DONE gate against
that in-memory state; (3) `DONE -r REJECTED` fails the gate explicitly with a
message pointing to `transition-phase IMPLEMENT -r REJECTED`. One ledger save
at the end — the result recording and phase advance land in the same write
(FR-003).

**Rationale**: Fixes the ordering inversion (gate currently reads the cycle
before the result is applied) with the smallest state-machine change; the
single-save property makes the pair atomic together with R4.

**Alternatives considered**: A dedicated `record-review <RESULT>` command —
rejected in the spec (Assumptions): the two-command surface already covers
both review outcomes; new surface can be specified later if agents need to
record without transitioning.

## R2 — Result value vocabulary

**Decision**: `-r/--result` accepts exactly APPROVED or REJECTED,
case-insensitive on input, stored uppercase. Help text updated from
`APPROVED|REJECTED|note`. Any other value → exit 1, ledger untouched.

**Rationale**: Free-text results were never functional (the DONE gate and the
corrective path both check specific values); documenting them was misleading.
The spec clarification confirmed dropping them.

**Alternatives considered**: Keeping free text for non-gating annotations —
rejected: nothing consumes it, and it would silently satisfy nothing.

## R3 — Packaged review directive correction

**Decision**: `src/specops/templates/review.md` Step 6 currently instructs
`specops status transition-phase REVIEW -r <APPROVED|REJECTED>` — an invalid
call (the ledger is already in REVIEW; REVIEW→REVIEW is not a transition).
Replace with the two real outcomes: APPROVED → `transition-phase DONE -r
APPROVED`; REJECTED → `transition-phase IMPLEMENT -r REJECTED`.

**Rationale**: Constitution Principle IV — directive changes ship in the
packaged templates so client repos receive them on next `specops init`. The
broken instruction is the agent-facing half of the P1 bug.

**Alternatives considered**: None viable; the current instruction always
fails at runtime.

## R4 — Atomic ledger writes

**Decision**: `_save_ledger` writes to a fixed-name sibling temp file
(`status.yaml.tmp` in the same feature directory), fsyncs, then `os.replace()`
onto `status.yaml`. Fixed name (not `NamedTemporaryFile`) so an interrupted
run leaves at most one stale temp file, silently overwritten by the next save.

**Rationale**: `os.replace` is atomic on POSIX and Windows when source and
destination are on the same filesystem — guaranteed here because both live in
the same directory. Covers SC-004 with ~5 lines and no new dependency.

**Alternatives considered**: `tempfile.NamedTemporaryFile(dir=...)` +
rename — equivalent atomicity but accumulates randomly-named orphans on
crash; file locking (portalocker) — concurrency is out of scope, new
dependency unjustified.

## R5 — Evidence validation single path

**Decision**: Delete the dead `_EVIDENCE_RE` module constant. Rewrite
`_validate_evidence` as the single validation path: split on `; ` exactly,
and require every part to match `^(CLI_LOG|TEST_REPORT|SCREENSHOT_PATH|CODE_DIFF):(?=\S).+$`
(recognized class, non-empty non-whitespace-leading summary). Any failing
part invalidates the whole string.

**Rationale**: Matches the clarified strict-rejection semantics; one
compiled regex built from `EVIDENCE_CLASSES` keeps class vocabulary and
validation from drifting apart.

**Alternatives considered**: Lexical splitting only at `; <VALID_CLASS>:`
boundaries — rejected in clarification (more complex parser, ambiguous
grammar).

## R6 — Error hierarchy and exit-code mapping

**Decision**: New module `src/specops/errors.py`:

- `SpecopsError(Exception)` — carries user-facing `message`; default
  `exit_code = 1` (blocking failure).
- `LedgerParseError(SpecopsError)` — `exit_code = 2` (unexpected/parse).
- `config.ConfigError` re-parented to `SpecopsError`.

Business modules (`status`, `reconcile`, `consistency`) raise these and
**return** their success output (rendered text / result data); they no longer
import `typer` or call `sys.exit`. `cli.py` wraps every command body in one
helper that catches `SpecopsError`, prints `message` to stderr, and raises
`typer.Exit(exit_code)`. Messages are kept byte-identical to today's output
(FR-010 / SC-006). `initializer.py` keeps its Typer usage — it is the one
interactive command (confirm prompt) and is out of FR-009's scope.

**Rationale**: One failure vocabulary, one exit-code mapper, modules become
library-usable and unit tests assert on exceptions instead of `SystemExit`.
Integration tests keep asserting process exit codes via the Typer runner, so
the contract is regression-checked end to end.

**Alternatives considered**: Result objects (`(ok, message)` tuples) —
rejected: loses stack context for the exit-2 unexpected class and forces
plumbing through every call level; keeping `sys.exit` but centralizing
message formatting — rejected: doesn't fix library usability or test quality.

## R7 — Numeric feature-dir ordering

**Decision**: In `resolve_feature_dir`'s fallback, filter names matching
`^(\d+)` and sort by `int` of the captured prefix (descending), tie-broken by
full name. `specs/10-bar` now beats `specs/9-foo`.

**Rationale**: Direct FR-008; lexicographic sort silently picks the wrong
feature once a project reaches its 10th spec with unpadded prefixes.

**Alternatives considered**: Requiring zero-padded prefixes — rejected:
convention-dependent and fails closed on someone else's naming.

## R8 — `status show` rendering

**Decision**: `cmd_show` loads the ledger read-only (no task re-sync, no
save) and renders structured plain text, one fact per line:

```
feature: <name>
branch: <branch>
phase: <PHASE>
active task: <id or none>
tasks: N total — N pending, N in progress, N done, N orphaned
review cycles: N
  round 1: APPROVED (2026-07-05 → 2026-07-05)
  round 2: open
```

Missing `review_cycles` / empty `tasks` render as zero counts (legacy-ledger
edge case). Exit 0 on success; standard exit-1 "ledger not found" otherwise.

**Rationale**: Covers FR-004's required facts, trivially greppable by agents,
no format dependency. JSON deliberately out of scope per clarification.

**Alternatives considered**: Rich tables — `rich` was removed in feature 001
by constitutional decision; not reintroduced.

## R9 — `--version` plumbing

**Decision**: Root-level eager `--version` option on the Typer callback using
`importlib.metadata.version("specops-cli")`; prints `specops <version>` and
exits 0 before any git check. `src/specops/__init__.py.__version__` reads from
the same metadata (fallback to `0.0.0.dev0` when not installed) so
`pyproject.toml` is the single version source.

**Rationale**: Standard Typer pattern; `importlib.metadata` is stdlib (3.10+);
removes the hand-maintained `__version__ = "0.1.0"` drift risk.

**Alternatives considered**: A `specops version` subcommand — `--version` is
the universal convention; hardcoded dual version strings — drift-prone.

## R10 — Lint / type / coverage tooling

**Decision**: Dev extras: `ruff`, `mypy`, `pytest-cov`, `types-PyYAML`.
Configuration in `pyproject.toml`:

- `[tool.ruff]`: target `py310`; lint rule families `E,F,W,I,UP,B,SIM`
  (errors, pyflakes, warnings, import order, upgrade, bugbear, simplify) —
  these catch every dead-code item found in review (duplicate imports, unused
  vars, imports misplacement).
- `[tool.mypy]`: `python_version = 3.10`, strict-leaning on `src/`
  (`disallow_untyped_defs`, `warn_unused_ignores`, `check_untyped_defs`);
  tests exempt from `disallow_untyped_defs`. GitPython ships a `py.typed`
  marker; PyYAML needs `types-PyYAML`.
- `[tool.pytest.ini_options]`: `addopts = --cov=specops
  --cov-report=term-missing --cov-fail-under=85` so every local test run
  enforces the blocking threshold (SC-008).

Local gate commands (documented in quickstart): `ruff check .`,
`mypy src/specops`, `pytest`. The threshold in `addopts` targets full-suite
runs; subset runs (single test files) use `--no-cov` to avoid spurious
threshold failures.

**Rationale**: Community-default toolchain (spec Assumptions); config lives in
`pyproject.toml` to avoid new dotfiles; coverage-in-addopts makes the local
and CI gates identical.

**Alternatives considered**: flake8+isort+pylint — superseded by ruff;
pyright — mypy chosen for pyproject-native config and ubiquity; separate
`.ruff.toml`/`mypy.ini` — unnecessary file sprawl.

## R11 — CI pipeline

**Decision**: `.github/workflows/ci.yml`, triggered on `push` and
`pull_request`. Single `test` job with a matrix over Python `3.10` and
`3.14` (floor + latest stable per clarification): checkout → setup-python →
`pip install -e .[dev]` → `ruff check .` → `mypy src/specops` → `pytest`
(coverage threshold enforced via addopts). Any step failure fails the job.

**Rationale**: One job with sequential steps keeps the pipeline readable and
each gate's verdict visible per step (SC-007); the matrix covers both ends of
the support range with 2 runs.

**Alternatives considered**: Separate lint/type/test jobs — more parallel but
3× environment setup for a tiny suite; tox/nox — indirection unjustified at
this size.

## R12 — Dead-code removal inventory

**Decision**: Removals bundled with the refactor, each guarded afterward by
Ruff rules:

| Item | Location |
|---|---|
| Duplicate `import sys` | `src/specops/status.py` (module header) |
| Dead `_EVIDENCE_RE` constant | `src/specops/status.py` (superseded by R5 single path) |
| Unused `_ok()` helper | `src/specops/status.py` |
| Unused `end`/`start` computations | `src/specops/gitops.py` `commits_in_range` |
| Unused `command_name` variable | `src/specops/initializer.py` `_install_review` |
| Unused `exit_ok`/`exit_fail`/`exit_error` helpers | `src/specops/cli.py` (superseded by R6 single mapper) |
| `import re` / directive-regex import inside loop | `src/specops/consistency.py` (hoisted; consumes new public helper) |
| Cross-module private `_ACTION_SUFFIX_RE` usage | `src/specops/consistency.py` → public helper in `speckit.py` |

**Rationale**: FR-011 enumerates these; pairing removal with Ruff enforcement
prevents recurrence (SC-007).

**Alternatives considered**: Suppressing via `# noqa` — defeats the purpose.
