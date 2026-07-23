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

### Step 4 — Record Structured Findings (Feature 011)

Findings are **first-class ledger state**, not free-form prose. For each non-conformity, record a structured finding:

```
specops handoff finding add \
  --severity <blocking|advisory> --rule "<rule violated>" \
  --file <path> --line <n> --action "<short corrective action>" \
  --expected-evidence "<what evidence will close it>" --closure "<closure criteria>"
```

- `blocking` findings gate approval; `advisory` findings are recorded but never block. `--expected-evidence`/`--closure` are required for `blocking`.
- Each finding gets a stable id `R<round>-F<NN>`. Record the paths the correction is expected to touch with `specops handoff authorize --path <p> …`.

If the gate report showed any `SKIPPED` gate, record each as an **advisory** finding so a gate that never ran is visible in the verdict, not silently approved:

```
specops handoff finding add --severity advisory --rule "skipped-gate" \
  --file . --action "Skipped gate: <name> (<reason>)"
```

Render the human-readable revision report — a projection of the structured state, in the compatible `[File]:[Line] - [action]` line format:

```
specops handoff render --round X    # writes revisions/revision-X.md
```

**Corrective round (re-review):** for each finding the implementer marked `FIXED`, verify it once its evidence is present:

```
specops handoff finding verify <R…-F…>
```

If a finding turns out to be a false positive (nothing to fix) or belongs to a superseded round, withdraw it instead of forcing a fix — it stops gating approval:

```
specops handoff finding dismiss <R…-F…> --reason "<why it is withdrawn>"
```

Set the review decision:
- Any **blocking** finding not yet `VERIFIED` → **REJECTED**
- Every blocking finding `VERIFIED` (advisory may remain open) → **APPROVED**

Execute the outcome:
- APPROVED → `specops handoff close` then `specops status transition-phase DONE -r APPROVED`
- REJECTED → `specops status transition-phase IMPLEMENT -r REJECTED`

`specops status transition-phase DONE` fails closed while any blocking finding is unverified — approval cannot bypass the corrective handoff. A repository with no structured findings (legacy) degrades to the prior cycle-result gate.

### Active Learning

If the review reveals recurring failures or knowledge gaps that a skill could prevent, record the suggestion as an **advisory** finding (it never blocks approval):
```
specops handoff finding add --severity advisory --rule "skill-suggestion" \
  --file <path> --line <n> \
  --action "Suggest: create skill '<name>' covering <topic> to prevent recurrence"
```
Do not create the skill yourself — the advisory finding records the suggestion for the human to act on.
