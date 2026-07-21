
## SpecOps Planning Directives

### Graceful Degradation

- If the `specops` command is not available in this environment, skip the SpecOps
  steps in this block (including the consistency gate) and write `plan.md`
  normally.

### Empirical Verification (§17.4)

- Do NOT declare file paths or code conventions from memory.
- Every path declaration in `plan.md` MUST carry one of these action suffixes:
  `(create)`, `(modify)`, `(remove)`, or `(create OR modify)`.
- Verify each declared path against the worktree before writing it:
  - `(modify)` — file must exist right now.
  - `(create)` — parent directory must exist right now.
  - `(remove)` — file must exist locally or in Git history.
- If a path cannot be verified, stop and ask before declaring it.

### SC Coverage Tags

- Coverage tags (`[SC-xxx]`) are authored during the tasks stage — see the
  SpecOps task-generation directive. At the plan stage, only ensure every spec
  Success Criterion is coverable by the planned work.

### Context Topology (Feature 009)

- When a context map exists (`.specify/specops/context-map.yaml`), declare the
  context(s) this work touches with a single line in `plan.md`:
  `**SpecOps-Contexts**: <id>, <id>, …`
- Before handing off the plan, run: `specops context plan-check`
  - Exit `0` — declared topology is valid (an `unowned` declared path is reported
    but is non-blocking). The command also displays the minimal phase read set.
  - Exit `1` — a required declaration is missing, a declared context id is unknown,
    or a declared path is owned by an undeclared context. Fix it before handing off.
- When no map is present, this step is a supported no-op (exit `0`) — skip it.

### Consistency Gate

- Before handing off the plan, run: `specops consistency`
- Exit code ≠ 0 means an SC is uncovered or a path declaration is invalid.
- Fix the violation before proceeding — do not hand off a failing plan.

### Stop-and-Ask

- Stop and ask the human when:
  - Two path declaration patterns coexist and the correct one is ambiguous.
  - A required path is missing from the worktree with no clear alternative.
  - A structural token in `spec.md` or `tasks.md` cannot be parsed unambiguously.
