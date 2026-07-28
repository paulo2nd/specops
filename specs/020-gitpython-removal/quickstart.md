# Quickstart: Validating GitPython Removal

Validation scenarios proving the replacement is byte-identical and the
dependency is gone. All run in the SpecOps dev environment (`conda run -n
specops …`); none run `specops` against this repository (No Self-Application).

## Prerequisites

- `conda` env `specops` with dev extras installed (`pip install -e ".[dev]"`).
- A functional `git` on PATH (already required today).
- Feature 018 golden-capture harness available in `tests/`.

## Scenario 1 — Dependency footprint (SC-001)

```bash
pip uninstall -y gitpython gitdb smmap    # ensure a clean slate
pip install -e .                          # install with the new pyproject
pip show gitpython gitdb smmap            # expect: not found for all three
python -c "import specops.gitops"         # imports without a git library
python -c "import git" && echo "LEAK" || echo "ok: no gitpython importable"
```

**Expected**: `gitpython`/`gitdb`/`smmap` absent; `import specops.gitops`
succeeds; the dependency tree names only Typer, PyYAML, packaging.

## Scenario 2 — Single seam (SC-003)

```bash
# No production module except gitops imports a git library or names git.Repo:
grep -rn "import git\b\|from git\|git\.Repo\|gitops\.git\b" src/specops/ | grep -v "gitops.py"
```

**Expected**: no matches. (`gitops.py` itself imports only `subprocess`.)

## Scenario 3 — Byte-identical behavior (SC-002)

```bash
# On pre-change ref: capture golden output for every git-dependent command.
# On this branch: replay and diff.
conda run -n specops pytest tests -k "golden or smoke" -q
```

**Expected**: golden replay reports zero differences except the two sanctioned
deltas (doctor git-availability finding; init git-absent diagnostic).

## Scenario 4 — Error-path parity (SC-004, FR-005)

Drive each failure mode over shared fixtures and assert identical diagnostics /
exit codes / degradations:

- not-a-repo → `_require_git` diagnostic, exit 1
- unknown commit / revision / absent path → same `[]`/`None`/`False`
- unborn HEAD, detached HEAD → same branch/HEAD fallback
- rename-aware vs decomposed diff → same `(status, path)` shapes

```bash
conda run -n specops pytest tests/unit/test_gitops.py -q
```

## Scenario 5 — Git-availability precondition (SC-008, FR-012/FR-013)

With a PATH that has no `git`:

```bash
env PATH="/nonexistent" conda run -n specops specops init --non-interactive; echo "exit=$?"
env PATH="/nonexistent" conda run -n specops specops doctor --json | jq '.domains[].findings[] | select(.id=="git-availability")'
```

**Expected**: `init` fails closed with a clear diagnostic and `exit=1` (no
traceback); `doctor` reports the `git-availability` finding as `blocking`. With a
normal PATH, `doctor` shows it as `ok` with the detected version.

## Scenario 6 — Encoding / path fidelity (SC-007, FR-007)

On a fixture repo containing a non-UTF-8 / non-ASCII filename (and on the Windows
CI leg):

```bash
conda run -n specops pytest tests -k "encoding or path or windows" -q
```

**Expected**: status/diff/ls-files output byte-identical to the GitPython capture.

## Scenario 7 — Static checks (SC-005) + suite

```bash
conda run -n specops ruff check .
conda run -n specops mypy src        # passes with the git.* override removed
conda run -n specops pytest -q       # full suite, coverage ≥85%
```

**Expected**: ruff clean; mypy green with no `git.*` override and no replacement
suppression; full suite passes on every CI platform.

## Scenario 8 — Constitution amendment (SC-006)

```bash
grep -i "gitpython" .specify/memory/constitution.md   # expect: absent from the dependency list
```

**Expected**: the Technical Constraints dependency enumeration no longer names
GitPython and records the removal rationale, in the same change set.
