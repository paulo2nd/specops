# Quickstart: Native Spec Kit Extension — validation guide

Runnable scenarios that prove the feature end-to-end. These run against **throwaway fixture
repositories** created by the test suite — never against this repository (SpecOps is not
self-applied here). Implementation lives in `tasks.md` / the implement phase.

## Prerequisites

- `pip install -e ".[dev]"` (Typer, PyYAML, GitPython, pytest, ruff, mypy).
- A fixture Spec Kit repo: a temp dir containing `.specify/templates/`,
  `.specify/integration.json` (with `installed_integrations`), and the per-integration
  `.specify/integrations/<agent>.manifest.json` + host `SKILL.md` prompt files.

## Scenario 1 — Native install into a clean repo (US1 · SC-001, SC-005)

1. In a clean fixture repo, run `specops extension install`.
2. **Expect**: exit 0; `.specify/extensions.yml` now contains the four SpecOps hook entries and a
   `commands:` entry per installed integration; the review command file exists.
3. **Assert non-modification**: every host `SKILL.md` hash matches its pre-install value
   (zero host-owned files modified).
4. **Offline**: repeat step 1 with networking disabled → identical result (SC-005).

## Scenario 2 — Idempotent re-install (US1 · SC-002)

1. Run `specops extension install` twice.
2. **Expect**: second run reports `unchanged`; the parsed manifest is semantically equal to the
   first (no duplicate hook entries, no duplicate command registration).

## Scenario 3 — CLI incompatibility fails closed (FR-016)

1. Simulate a missing/older CLI version (patch `importlib.metadata.version` in the fixture).
2. Run `specops extension install`.
3. **Expect**: exit 1; message names the missing/incompatible CLI; `.specify/extensions.yml` is
   **not** created and no file changed.

## Scenario 4 — Legacy → native migration with backup (US2 · SC-003, SC-008)

1. Build a fixture with legacy markers injected (run the existing `specops init` path) plus a
   `specops.json` and at least one feature ledger under `specs/*/`.
2. Run `specops extension migrate`.
3. **Expect**: exit 0; host prompt files contain **no** `SPECOPS:BEGIN` markers; `extensions.yml`
   registered; `specops.json` and every ledger unchanged (SC-003).
4. **Failure path**: inject a fault after the first file is stripped (e.g. a corrupted marker in a
   later file) → migration restores **all** touched host files to exact pre-migration bytes and
   exits 1 (SC-008).

## Scenario 5 — Disable / enable round-trip (US3 · FR-010)

1. From an installed repo, `specops extension disable`.
2. **Expect**: SpecOps hook entries and command file removed from the host surface;
   `specops.json` and ledgers retained; `specops extension status` reports `absent` native.
3. `specops extension enable` → registration reproduced identically to a fresh install.

## Scenario 6 — Remove and purge (US3 · SC-004, FR-009a)

1. `specops extension remove` → no integration-managed file modified; ledgers retained.
2. `specops extension remove --purge` (from an installed state) → additionally deletes
   `specops.json` and feature ledgers.

## Scenario 7 — Multi-integration registration (SC-006)

1. Fixture with two installed integrations in `integration.json`.
2. `specops extension install` → a command registration exists for **each** integration; the four
   hook entries are written once (integration-neutral).

## Scenario 8 — Interruption safety (SC-007)

1. Interrupt install/migrate/remove at each write boundary (parametrized test).
2. **Expect**: a subsequent run reaches a consistent state without manual repair at 100% of tested
   interruption points; no partially-registered inconsistent manifest remains.

## Quality gates (run before marking tasks done)

```bash
ruff check .
mypy src/specops
pytest            # full suite incl. tests/unit/test_extension.py, test_migration.py, test_compat.py,
                  # and tests/integration/test_extension_lifecycle.py
```
