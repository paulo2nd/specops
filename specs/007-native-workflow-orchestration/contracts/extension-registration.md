# Contract: Workflow Registration via the Extension

Extends `specops extension install|update|disable|enable|remove` to manage the `specops` workflow
asset additively, reusing the existing preflight / idempotency / SpecOps-owned-only merge/prune logic
in `extension.py`.

## Files written (client repo)

| Path | Owner | Action |
|---|---|---|
| `.specify/workflows/specops/workflow.yml` | SpecOps | created/overwritten from `src/specops/templates/workflows/specops/workflow.yml` |
| `.specify/workflows/workflow-registry.json` | Spec Kit (shared) | SpecOps writes/updates **only** the `specops` key; all other keys preserved verbatim |
| `.specify/extensions.yml` | SpecOps | unchanged shape; may add a `specops:` reference to the workflow id for traceability |
| `.specify/workflows/speckit/*` | Spec Kit (bundled) | **never touched** (Principle I, FR-001a) |

## Rules

- **E1 (additive)**: registration never modifies, reorders, or removes non-SpecOps registry entries
  or the bundled `speckit` workflow. — FR-001a, Principle I; SC (backward compat, CHK025).
- **E2 (idempotent)**: repeated `install` yields `unchanged` when the workflow file and registry entry
  already match (semantic equality), mirroring the command-registration path. — Feature 005 parity.
- **E3 (fail-closed preflight)**: nothing is written unless all pre-checks pass (an installed
  integration exists, target dir writable), reusing `extension.preflight`. — FR-024.
- **E4 (prune on remove/disable)**: `remove`/`disable` delete the `specops` workflow file and its
  registry key only, preserving foreign entries — mirrors `_prune_specops`.
- **E5 (offline)**: registration is a local file operation; no network. — FR-007.
- **E6 (invocation)**: after install, the workflow is runnable as `specify workflow run specops`
  (Spec Kit's own runner discovers it via the registry). — Clarification Q1.

## Tested by

`tests/integration/test_extension_lifecycle.py` (install/update/remove now assert the workflow file +
registry key lifecycle and non-mutation of foreign/bundled entries) and
`tests/unit/test_extension.py` (idempotency + prune of the workflow entry).
