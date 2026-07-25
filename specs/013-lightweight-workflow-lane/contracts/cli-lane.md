# Contract: `specops lane` CLI sub-app

All commands follow the SpecOps outcome contract (`outcome.render`): exit `0` = ok / `pass`,
`1` = blocked / `gate-rejection`, `2` = infra / usage error. `--json` emits a stable object with
at least `{command, outcome, class}`; human text otherwise. **No command prompts interactively**
— human choices arrive as arguments supplied by the workflow's native `gate`/`prompt` steps
(Principle VI). Read-only commands (`status`, `check`) never mutate `lane.yaml` or the repo.

Preconditions common to all: run inside a Git repo with `specops.json` present; the active
feature is resolved via `.specify/feature.json` (same as other commands).

---

## `specops lane start [--answers small,reversible,no-high-risk-category] [--bundle NOTE] [--json]`

Open a lane. Records eligibility confirmation and writes `lane.yaml` at `state: OPEN`.

| Outcome | Condition | Exit | class |
|---------|-----------|------|-------|
| ok | all eligibility criteria confirmed; `lane.yaml` created | 0 | pass |
| blocked | any criterion not confirmed, OR a diff-detectable high-risk category already present at entry | 1 | gate-rejection |
| error | `lane.yaml` already exists, or `status.yaml` already exists (use the full workflow), not a git repo | 2 | infra-error |

`--json` extra keys: `lane_id`, `baseline`, `eligibility` (echo of confirmed answers).

---

## `specops lane status [--json]`

Read-only. Print the current lane record summary (state, baseline, decision count, terminal
outcome). Exit `0` always when a readable `lane.yaml` exists; `2` if absent/unparseable.

`--json` extra keys: `state`, `baseline`, `decisions` (count), `closure`/`promotion` (when set).

---

## `specops lane check [--staged] [--json]`

Read-only. Run the hybrid safety-core **detection** over the effective diff
(`baseline..HEAD`, or staged with `--staged`) and report flagged diff-detectable categories.
This is the deterministic gate the workflow branches on.

| Outcome | Condition | Exit | class |
|---------|-----------|------|-------|
| ok | no diff-detectable category flagged | 0 | pass |
| blocked | one or more of the four detectable categories detected | 1 | gate-rejection |
| error | cannot read diff / lane not open | 2 | infra-error |

`--json` extra keys: `detections` (list of `{category, path, status}`), `categories` (deduped
set). Does **not** cover root-cause ambiguity or public-contract breaks (those are the two
always-on attestations, not diff-detectable — see `lane attest`).

---

## `specops lane attest --root-cause {clear|flag} --public-contract {clear|flag} [--json]`

Record the two always-on attestations (FR-007 hybrid: root-cause and public-contract). Appends an
`attestation` decision per dimension. Both MUST be answered before `lane close`.

| Outcome | Condition | Exit | class |
|---------|-----------|------|-------|
| ok | both dimensions `clear` recorded | 0 | pass |
| blocked | either dimension `flag` recorded (caller must then halt or promote) | 1 | gate-rejection |
| error | lane not open | 2 | infra-error |

---

## `specops lane close [--json]`

Fail-closed closure. Requires both attestations recorded `clear` (`--root-cause clear
--public-contract clear`) and no unresolved detection. Runs the `preflight` gate-profile suite,
records Feature 012 evidence, writes the retrospective, sets `state: CLOSED`, renders
`retrospective.md`.

Preconditions (all fail-closed): the **product working tree must be clean** (SpecOps/Speckit
methodology artifacts — the lane's own `lane.yaml`/`retrospective.md` under `specs/<feature>/`,
`specops.json`, `.specify/**` — are excluded, as in the drift gate), so no staged/uncommitted
high-risk change escapes the safety scan by sitting outside `baseline..HEAD`.

| Outcome | Condition | Exit | class |
|---------|-----------|------|-------|
| ok | preflight APPROVED; closure + retrospective written | 0 | pass |
| blocked | an unclean product working tree, OR required gate FAIL/unavailable, OR a missing/`flag` attestation, OR an unresolved detection | 1 | gate-rejection |
| error | lane not open, OR the lane baseline no longer resolves in the clone | 2 | infra-error |

`--json` extra keys: `verdict`, `gates` (disposition list), `retrospective_path`.

---

## `specops lane promote --reason {safety-trip|scope-growth} [--json]`

Lossless promotion. Synthesizes `status.yaml` (schema v6) at `current_phase: PLAN`, imports
`baseline..HEAD` commits, copies lane context into `lane_provenance`, sets `state: PROMOTED`.

`--reason` is validated against the enum `{safety-trip, scope-growth}` (usage error otherwise).

| Outcome | Condition | Exit | class |
|---------|-----------|------|-------|
| ok | ledger synthesized at PLAN (+ a `spec.md` stub); commits imported; lane marked PROMOTED | 0 | pass |
| blocked | `status.yaml` already exists (already promoted) | 1 | gate-rejection |
| error | the lane baseline is not an ancestor of HEAD (history diverged → `status rebaseline` guidance), an invalid `--reason`, or not a git repo | 2 | infra-error |

`--json` extra keys: `synthesized_ledger`, `imported_commits` (count), `resumed_phase` (`PLAN`).

**Invariant (tested)**: the set of commits reachable from HEAD is identical before and after
`promote` (zero commit loss, FR-014).
