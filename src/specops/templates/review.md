## /specops-review

Token-optimized review command for SpecOps. Follow the steps below in strict order — reject as early as possible to avoid reading unnecessary code.

### Step 1 — Load Skills

Check `skills_dir` (from `specops.json`). If the directory contains skill files, load them before proceeding. If it is empty or missing, continue — skills are optional.

### Step 2 — Deterministic Gates

Run `specops review`.

- Exit code ≠ 0 → **REJECTED**. Report the command's output. Stop here. Do not read any code.
- Exit code 0 → all gates passed (reconcile, lint, test, working tree, drift). If the report shows any gate as `SKIPPED`, remember it for the revision report (Step 4). Continue.

The **drift gate** (Feature 010) blocks the review when the effective diff contains any
`unexplained` path — one that is neither declared in `plan.md` nor recorded as a
`discovered-and-acknowledged` path (`specops trace acknowledge`). Paths that are planned
or acknowledged pass. SpecOps/Speckit-managed artifacts (`specs/**`, `.specify/**`,
`specops.json`) are excluded — they are methodology state, not product drift.

### Step 2a — Context Drift & Impact (Feature 009)

If a context map exists (`.specify/specops/context-map.yaml`):

- The `specops review` output appends a non-blocking `[warning] context-map drift: …`
  line (after the gate report) when the map digest changed since planning. This never
  rejects the review on its own — note it in the revision report (Step 4) so the
  change is visible.
- Run `specops context impact` to see the contexts affected by the effective diff
  (directly-owned plus their reverse dependents). Use it to scope the diff review in
  Step 3: every expanded context is attributable to an `ownership`/`dependency` edge —
  do not widen the read beyond what the map explains.

When no map is present, skip this step (supported no-op).

### Step 3 — Surgical Diff Review

Read only the files listed by the working-tree gate in the `specops review` output — that list is the effective diff against the ledger baseline. Do not review anything outside it.

Review against:
- The spec Success Criteria and acceptance conditions.
- The plan's declared architecture and path declarations.
- The contexts reported by `specops context impact` (Step 2a) when a map is present.
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

If the gate report showed any `SKIPPED` gate, record each one in `revision-X.md` on its own line — `Skipped gate: <name> (<reason>)` — so a gate that never ran is visible in the verdict, not silently approved.

If no non-conformities: write `revision-X.md` with a single line `APPROVED` (followed by any `Skipped gate:` lines).

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
