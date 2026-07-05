
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

### Consistency Gate

- Before handing off the plan, run: `specops consistency`
- Exit code ≠ 0 means an SC is uncovered or a path declaration is invalid.
- Fix the violation before proceeding — do not hand off a failing plan.

### Stop-and-Ask

- Stop and ask the human when:
  - Two path declaration patterns coexist and the correct one is ambiguous.
  - A required path is missing from the worktree with no clear alternative.
  - A structural token in `spec.md` or `tasks.md` cannot be parsed unambiguously.
