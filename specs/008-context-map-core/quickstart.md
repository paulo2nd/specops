# Quickstart & Validation: Context Map Core

A run/validation guide proving the feature end-to-end. Per the constitution, all validation runs
against **test fixtures**, never against this repository (No Self-Application). Implementation detail
lives in [data-model.md](./data-model.md) and [contracts/](./contracts/).

## Prerequisites

- Editable install: `pip install -e ".[dev]"` (exposes the `specops` entrypoint).
- A throwaway Spec Kit repo/fixture with `.specify/templates/` present (see `tests/conftest.py`
  `fake_speckit_repo`).

## Author → validate → resolve → explain (happy path)

```bash
# 1. Scaffold a starter map (idempotent)
specops context init                 # -> writes .specify/specops/context-map.yaml (status: created)
specops context init                 # -> status: already_exists, no mutation  [SC-009]

# 2. Edit the map to describe your repo, then validate
specops context validate             # exit 0; reports context count + schema_version
specops context validate --json      # {"status":"valid", ...}

# 3. Resolve a path and an ID (explicit selectors)
specops context resolve --path src/api/auth/login.py --phase implement --json
specops context resolve --id api-auth --json          # [SC-001 determinism: identical across runs]

# 4. Explain why a context won
specops context explain --path src/api/auth/login.py --json   # reason trace [SC-007, SC-014]
```

## Success-criteria validation (via fixtures)

| SC | How it is proven | Test |
|---|---|---|
| SC-001 | Repeat `resolve`/`explain` on a fixed map; assert byte-for-byte identical output | `test_contextmap.py::test_resolution_is_deterministic` |
| SC-002 | One failing fixture per defect class; assert distinct `code` + attribution | `test_contextmap.py::test_validate_defect_classes` |
| SC-003 | Resolve/explain against an invalid map fail closed before any package | `test_contextmap.py::test_fail_closed_no_package` |
| SC-004 | All three read-only commands on an absent map → `no_map_present`, no writes | `test_context_cli.py::test_absent_map` |
| SC-005 | Fixture per state (absent/malformed/schema-invalid/empty/valid); each distinguishable | `test_context_cli.py::test_five_states` |
| SC-006 | JSON shape unchanged across runs (contract snapshot) | `test_context_cli.py::test_json_shape_stable` |
| SC-007 | Overlapping-rules + tie fixtures; most-specific wins / tie → ambiguous | `test_contextmap.py::test_specificity_order` |
| SC-008 | Cycle fixture; reported with IDs, bounded time (no hang) | `test_contextmap.py::test_dependency_cycle` |
| SC-009 | `init` twice → one unmodified map | `test_context_cli.py::test_init_idempotent` |
| SC-010 | Unsupported/too-new version fixture → version diagnostic | `test_contextmap.py::test_unsupported_version` |
| SC-011 | Dependency-expansion fixture → dedup, order, per-edge `via` | `test_contextmap.py::test_expanded_read_set` |
| SC-012 | base-inheritance + no-base fixtures; `read_set_source` reported | `test_contextmap.py::test_phase_fallback` |
| SC-013 | Exit-code matrix across valid/invalid/absent/no-match/usage | `test_context_cli.py::test_exit_code_matrix` |
| SC-014 | Fixture per deciding dimension + tie; `deciding_dimension` named | `test_contextmap.py::test_explain_deciding_dimension` |
| SC-015 | Selector contract: both/neither → exit 2; unknown id → no-match | `test_context_cli.py::test_selector_contract` |

## Repository quality gates

```bash
ruff check . && mypy src/specops && pytest -q
```

All must pass at repository thresholds (Global Definition of Done). No `context` command is run
against this repository; the starter template ships as a product asset only.
