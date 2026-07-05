# Contract: Injection Target Resolution

Applies to `speckit.resolve_prompt_targets(root)` and `initializer.run(root)`.

## `resolve_prompt_targets` return contract

Each element of the returned list MUST contain, in addition to today's keys:

```python
{
    "integration": str,
    "separator": str,
    "plan_path": Path,        # existing
    "implement_path": Path,   # existing
    "specify_path": Path,     # NEW — resolved via role="specify"
    "tasks_path": Path,       # NEW — resolved via role="tasks"
}
```

**Rules**:
- `specify_path` and `tasks_path` are resolved with the existing
  `_find_prompt_file(root, files, agent, sep, role)` helper.
- Fail-closed (unchanged contract): if the manifest lacks a `speckit{sep}specify`
  or `speckit{sep}tasks` entry, or the listed file is absent, raise
  `ManifestResolutionError`. No partial results.
- Order of existing keys and list ordering MUST NOT change (back-compat for
  current callers/tests).

## `initializer.run` injection contract

After resolving targets, for each integration `run` MUST:

1. Install `/specops-review` (unchanged).
2. `inject_block(plan_path, "plan", …)` (unchanged).
3. `inject_block(implement_path, "implement", …)` (unchanged, content augmented).
4. `inject_block(specify_path, "specify", …)` — **new**.
5. `inject_block(tasks_path, "tasks", …)` — **new**.
6. Echo one status line per target in the existing format:
   `  <relative-path>: <role> directive <created|updated|unchanged>`.

**Idempotency**: a second `run` on an already-injected repo MUST report
`unchanged` for all four blocks and change no bytes (SC-007).

**Reversibility**: `remove_block` on each of the four block IDs MUST restore the
prompt to a byte-identical pre-injection state (SC-005).

## Test contract

- `test_speckit.py`: `resolve_prompt_targets` returns non-null `specify_path` and
  `tasks_path` pointing at existing files for the Claude fixture; raises
  `ManifestResolutionError` when the specify/tasks entry is missing.
- `test_init.py`: after `run`, all four stage prompts contain their block; a
  second `run` yields `unchanged`; `remove_block` on all four restores original
  bytes.
