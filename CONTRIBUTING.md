# Contributing to SpecOps

Thanks for your interest in SpecOps. This project is at `0.x` — the CLI surface,
ledger format, and injected directives may still change. Contributions are
welcome; please read the workflow below before opening a pull request.

## Development setup

Prerequisites: Python ≥ 3.10, Git ≥ 2.30.

```bash
pip install -e ".[dev]"   # install project + dev tools in editable mode
```

## Quality gates

Run the same checks CI runs before pushing:

```bash
ruff check .              # lint
mypy src/specops          # type check (strict: untyped defs disallowed)
pytest                    # tests + coverage (≥ 85% required)
```

CI runs on every push and pull request against a Python 3.10 / 3.14 matrix. A
pull request must pass all three gates.

## Project principles

SpecOps is governed by its constitution (`.specify/memory/constitution.md`).
Two principles matter most for contributors:

- **Speckit extension, never replacement.** SpecOps only adds an additive,
  marker-delimited layer on top of Speckit. Never fork or overwrite Speckit's
  files; injection must be idempotent and reversible to a byte-identical state.
- **Repo-as-state.** All feature state lives in `status.yaml` and is written
  only through `specops` commands — never hand-edit the ledger or `tasks.md`
  checkboxes.

## Language policy

All operational output (CLI messages, packaged assets, directive blocks) is in
English. SpecOps parses only structural tokens (`SC-\d+`, `T\d+`, action
suffixes) — never client prose — so `spec.md`, `plan.md`, and task descriptions
may be authored in any language.

## Pull requests

1. Branch from `main`.
2. Keep changes focused; add or update tests for any behavior change.
3. Update `CHANGELOG.md` under `## [Unreleased]`.
4. Ensure all three quality gates pass locally.
5. Describe the change and its rationale in the PR body.
