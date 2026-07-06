## /specops-review

Token-optimized review command for SpecOps. Follow the steps below in strict order — reject as early as possible to avoid reading unnecessary code.

### Step 1 — Load Skills

Check `skills_dir` (from `specops.json`). If the directory contains skill files, load them before proceeding. If it is empty or missing, continue — skills are optional.

### Step 2 — Deterministic Gates

Run `specops review`.

- Exit code ≠ 0 → **REJECTED**. Report the command's output. Stop here. Do not read any code.
- Exit code 0 → all gates passed (reconcile, lint, test, working tree). Continue.

### Step 3 — Surgical Diff Review

Read only the files that changed (from the effective diff).

Review against:
- The spec Success Criteria and acceptance conditions.
- The plan's declared architecture and path declarations.
- The Constitution's Core Principles (correctness, not style).

### Step 4 — Write Revision Report

Create `revisions/revision-X.md` where X = (max existing revision number + 1).

Each non-conformity on its own line, format:
```
[File]:[Line] - [rule violated and short action]
```

Example:
```
src/specops/status.py:42 - L2 violated: two tasks IN_PROGRESS simultaneously; enforce single-active-task guard
```

If no non-conformities: write `revision-X.md` with a single line `APPROVED`.

Set the review decision:
- At least one non-conformity → **REJECTED**
- Zero non-conformities → **APPROVED**

After writing the report, execute the outcome:
- APPROVED → `specops status transition-phase DONE -r APPROVED`
- REJECTED → `specops status transition-phase IMPLEMENT -r REJECTED`

### Active Learning

If the review reveals recurring failures or knowledge gaps that a skill could prevent:
- Add a line to `revision-X.md` under a `## Skill Suggestions` section:
  ```
  Suggest: create skill '<name>' covering <topic> to prevent recurrence of [File]:[Line] pattern.
  ```
- Do not create the skill yourself — record the suggestion for the human to act on.
