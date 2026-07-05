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
- `specify_path` and `tasks_path` are resolved with a best-effort helper
  (`_find_optional_prompt_file`): they return a `Path` when the manifest lists a
  `speckit{sep}specify` / `speckit{sep}tasks` entry and the file exists,
  otherwise `None`.
- **Refinement from the original plan** (discovered during implementation):
  specify/tasks are best-effort, NOT fail-closed. `plan_path`/`implement_path`
  remain fail-closed (`ManifestResolutionError`). Rationale: partial Speckit
  layouts (e.g., a secondary integration exposing only plan/implement) must keep
  working — this is the graceful-degradation requirement (FR-008/SC-006). A
  fail-closed specify/tasks would break such layouts and the existing
  second-integration test.
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
  `tasks_path` pointing at existing files for the full Claude fixture; returns
  `None` for both when a partial layout omits the specify/tasks entries.
- `test_init.py`: after `run`, all four stage prompts contain their block; a
  second `run` yields `unchanged`; `remove_block` on all four restores original
  bytes.
