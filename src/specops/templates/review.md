## /specops-review

Token-optimized review command for SpecOps. Follow the steps below in strict order — reject as early as possible to avoid reading unnecessary code.

### Step 1 — Load Skills

Load all required skills from `skills_dir` (see `specops.json`). Do not proceed without them.

### Step 2 — Reconcile Gate

Run `specops reconcile`.

- Exit code ≠ 0 → **REJECTED**. Report the reconcile output. Stop here. Do not read any code.

### Step 3 — Lint and Test Pre-filter

Run `lint_command` and `test_command` (from `specops.json`).

- Either command fails → **REJECTED**. Report which command failed and its exit code. Stop here.

### Step 4 — Scope Check

Run `git status --porcelain`.

- Any file in the output that is NOT declared in `plan.md` → **REJECTED** out of scope. Name the file(s). Stop here. Do not read any code.
- No changed files (empty diff) → **REJECTED** no effective diff. Stop here.

### Step 5 — Surgical Diff Review

Read only the files that changed and are in scope (from `plan.md`).

Review against:
- The spec Success Criteria and acceptance conditions.
- The plan's declared architecture and path declarations.
- The Constitution's Core Principles (correctness, not style).

### Step 6 — Write Revision Report

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

After writing the report, run:
```
specops status transition-phase REVIEW -r <APPROVED|REJECTED>
```
