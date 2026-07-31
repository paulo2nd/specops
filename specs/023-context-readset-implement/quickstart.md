# Quickstart Validation: Context Read-Set Consumption in IMPLEMENT

**Feature**: 023-context-readset-implement | **Date**: 2026-07-31

How to prove the feature works end-to-end. All validation is fixture-based —
never run `specops` against this repository (No Self-Application).

## Prerequisites

```bash
conda run -n specops pip install -e ".[dev]"   # if not already installed
```

## 1. Full gate (lint + types + tests)

```bash
conda run -n specops ruff check src tests
conda run -n specops mypy src
conda run -n specops pytest
```

Expected: all pass; no test outside this feature's two test files changes
behavior (no runtime code was touched).

## 2. Directive delivery (both paths)

```bash
conda run -n specops pytest tests/unit/test_implement_directive.py -v
```

Expected: the native `after_implement` hook prompt and the legacy inject both
carry the Context Read Set section, inject stays idempotent, and the content
assertions of [contracts/implement-directive.md](contracts/implement-directive.md)
(C1–C7) hold.

## 3. Acceptance gate on a mapped fixture

```bash
conda run -n specops pytest tests/unit/test_contextmap_consume.py -v -k "implement or readset"
```

Expected (mirrors the spec's acceptance gate):

- **Coverage**: for every plan-declared path, the package resolved per path
  (`--phase implement`) is contained in the union of the declared contexts'
  id-resolved packages (SC-001).
- **Degradation**: no map → `no_map_present`, PASS/exit 0 (SC-003); invalid
  map → exit 1 from `resolve` (frozen contract) which the directive maps to
  "proceed without scoping" (SC-002/SC-004 — asserted as directive content in
  step 2, and as CLI statuses here).

## 4. Manual spot-check (optional, throwaway fixture)

In a scratch directory (never this repo):

```bash
git init demo && cd demo
specops context init                       # scaffold a starter map
specops context resolve --id <some-id> --phase implement
specops context resolve --id <some-id> --phase IMPLEMENT   # → usage error (exit 2): flag is lowercase
cd .. && rm -rf demo
```

And on a directory with no map: `specops context resolve --id x --phase
implement` → "context: no map present", exit 0.

## 5. Documentation parity

```bash
grep -n "implement" docs/commands.md | grep -i "read set\|consum"
grep -n -i "read set\|read-set" README.md README.pt-br.md
```

Expected: `docs/commands.md`'s consumption section names implement-time
consumption; `README.md` and `README.pt-br.md` describe it equivalently
(EN/PT parity in the same PR).
