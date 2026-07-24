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
| blocked | one or more of the five categories detected | 1 | gate-rejection |
| error | cannot read diff / lane not open | 2 | infra-error |

`--json` extra keys: `detections` (list of `{category, path, status}`), `categories` (deduped
set). Does **not** cover root-cause ambiguity (that is the always-on attestation, not
diff-detectable).

---

## `specops lane attest --root-cause {confirmed|ambiguous} [--json]`

Record the always-on root-cause attestation (FR-007 hybrid). Appends an `attestation` decision.

| Outcome | Condition | Exit | class |
|---------|-----------|------|-------|
| ok | `confirmed` recorded | 0 | pass |
| blocked | `ambiguous` recorded (caller must then halt or promote) | 1 | gate-rejection |
| error | lane not open | 2 | infra-error |

---

## `specops lane close [--json]`

Fail-closed closure. Requires a prior `attest --root-cause confirmed` and no unresolved
detection. Runs the `preflight` gate-profile suite, records Feature 012 evidence, writes the
retrospective, sets `state: CLOSED`, renders `retrospective.md`.

| Outcome | Condition | Exit | class |
|---------|-----------|------|-------|
| ok | preflight APPROVED; closure + retrospective written | 0 | pass |
| blocked | required gate FAIL/unavailable, OR missing `confirmed` attestation, OR an unresolved detection | 1 | gate-rejection |
| error | lane not open / infra failure | 2 | infra-error |

`--json` extra keys: `verdict`, `gates` (disposition list), `retrospective_path`.

---

## `specops lane promote --reason {safety-trip|scope-growth} [--json]`

Lossless promotion. Synthesizes `status.yaml` (schema v6) at `current_phase: PLAN`, imports
`baseline..HEAD` commits, copies lane context into `lane_provenance`, sets `state: PROMOTED`.

| Outcome | Condition | Exit | class |
|---------|-----------|------|-------|
| ok | ledger synthesized at PLAN; all commits reachable; lane marked PROMOTED | 0 | pass |
| blocked | `status.yaml` already exists (already promoted) | 1 | gate-rejection |
| error | a recorded commit is unreachable (history diverged → `status rebaseline` guidance), not a git repo | 2 | infra-error |

`--json` extra keys: `synthesized_ledger`, `imported_commits` (count), `resumed_phase` (`PLAN`).

**Invariant (tested)**: the set of commits reachable from HEAD is identical before and after
`promote` (zero commit loss, FR-014).
