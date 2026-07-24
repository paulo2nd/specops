# Phase 1 Data Model: Lightweight Workflow Lane

Derives the entities from the spec's *Key Entities* and *Functional Requirements*, made concrete
as the `lane.yaml` record schema plus the in-memory structures of `lane.py` / `safety.py`.
`status.yaml` (the full ledger) is unchanged except for the additive promotion-provenance keys.

---

## 1. Lane record — `specs/<feature>/lane.yaml` (schema_version: 1)

The single minimal record for one lightweight-lane pass. Mutated **only** by `specops lane *`.

```yaml
schema_version: 1
lane_id: "013-lightweight-workflow-lane"   # feature dir name (stable identity)
feature: "013-lightweight-workflow-lane"
branch: "013-lightweight-workflow-lane"
baseline: "<commit-sha>"                    # HEAD at `lane start` (start of the lane's diff range)
created_at: "2026-07-24T12:00:00+00:00"     # RFC3339 UTC (ledger.now_utc)
updated_at: "2026-07-24T12:34:00+00:00"

state: "OPEN"                               # OPEN | CLOSED | PROMOTED  (terminal: CLOSED, PROMOTED)

eligibility:                                # FR-003/FR-004 — human confirmation vs. explicit criteria
  confirmed: true
  criteria_version: 1                       # the checklist version confirmed against
  answers:                                  # one per criterion (stable, deterministic set)
    - key: "small"
      confirmed: true
    - key: "reversible"
      confirmed: true
    - key: "no-high-risk-category"
      confirmed: true
  bundled: false                            # FR-017 — set true when bundling adjacent changes
  bundle_note: null                         # optional human note describing the bundle

decisions: []                               # ordered stop-and-ask log (see §2); empty until a trip

closure: null                               # populated on CLOSED (see §3)
promotion: null                             # populated on PROMOTED (see §4)
```

### Field rules / invariants

- **L-1**: `state ∈ {OPEN, CLOSED, PROMOTED}`; `CLOSED`/`PROMOTED` are terminal (no re-open).
- **L-2**: `eligibility.confirmed` MUST be `true` for `state` to leave the implicit
  pre-open stage — `lane start` fails closed (exit 1) if any criterion answer is not confirmed.
- **L-3**: `baseline` MUST resolve to a commit in the current clone (`gitops.commit_exists`);
  every commit later recorded in `closure`/`promotion` MUST be reachable from HEAD
  (`gitops.is_ancestor`) — the Principle II reachability invariant, applied to the lane.
- **L-4**: exactly one of `closure` / `promotion` is non-null when `state` is terminal; both
  are null while `OPEN`.
- **L-5**: `decisions` is append-only; a `promote`/`halt` resolution is recorded before the
  lane leaves `OPEN`.

---

## 2. Stop-and-ask decision (element of `decisions[]`)

One entry per safety-core checkpoint that fired or per always-on attestation answered.

```yaml
- seq: 1
  kind: "detected" | "attestation"          # detected = diff-flagged category; attestation = root-cause
  category: "migration"                      # one of the six categories; "root-cause" for attestation
  signal: "path:db/migrations/003.sql"       # what triggered it (detected) | "always-on" (attestation)
  answer: "promote" | "halt" | "confirmed" | "ambiguous"
  resolution: "promote" | "halt"             # the terminal action taken (attestation "ambiguous" ⇒ halt-or-promote)
  at: "2026-07-24T12:20:00+00:00"
```

### Rules

- **D-1** (FR-008, non-pierceable): a `detected` or `ambiguous` checkpoint offers **only**
  `halt` or `promote` — there is no "record reason and continue" resolution. The schema has no
  bypass field by construction.
- **D-2** (FR-007 hybrid): `kind: attestation, category: root-cause` MUST be present on every
  lane pass before closure (always-on). `answer: confirmed` allows closure to proceed;
  `answer: ambiguous` forces a `halt`/`promote` resolution.
- **D-3**: the five detected categories (`migration`, `secret`, `dependency`,
  `public-contract`, `destructive`) are produced by `safety.py` from the diff, never
  hand-entered.

---

## 3. Closure block (`closure`, present when `state == CLOSED`)

```yaml
closure:
  at: "2026-07-24T12:34:00+00:00"
  commit_range: "<baseline>..<head>"
  gate_evidence:                             # Feature 012 structured evidence (reused verbatim)
    verdict: "APPROVED"                      # preflight verdict for the change
    gates:                                   # per-gate disposition taxonomy
      - name: "lint"
        disposition: "required"
        status: "PASS"
        evidence_id: "<id>"
      - name: "test"
        disposition: "required"
        status: "PASS"
        evidence_id: "<id>"
  retrospective:                             # concise, structured (FR-012)
    summary: "One-line what/why of the change."
    eligibility_basis: ["small", "reversible", "no-high-risk-category"]
    decisions: 0                             # count of stop-and-ask entries encountered
    commits: ["<sha7>", "..."]
```

### Rules

- **C-1** (FR-013, fail-closed): closure only writes a `closure` block and sets
  `state: CLOSED` when the preflight verdict is APPROVED (no required-gate FAIL/unavailable).
  Otherwise `lane close` exits `1` and the record stays `OPEN`.
- **C-2**: `gate_evidence` is produced by reusing `review`/`gateprofiles`/`evidence`; the lane
  introduces **no** new evidence format.
- **C-3**: a human-readable `retrospective.md` is rendered under `specs/<feature>/` as a
  projection of `closure.retrospective` (authoritative state stays in `lane.yaml`), mirroring
  the `handoff render` pattern.

---

## 4. Promotion block (`promotion`, present when `state == PROMOTED`) + synthesized ledger

```yaml
promotion:
  at: "2026-07-24T12:40:00+00:00"
  reason: "safety-trip" | "scope-growth"     # both use one lossless path (FR-016)
  synthesized_ledger: "specs/<feature>/status.yaml"
  imported_commits: ["<sha>", "..."]         # baseline..HEAD, preserved (zero loss)
  resumed_phase: "PLAN"
```

The synthesized **full ledger** (`status.yaml`, schema v6) is created from the existing
template with these promotion-specific values (additive provenance keys shown `*`):

```yaml
schema_version: 6
feature: "<feature>"
branch: "<branch>"
baseline: "<lane baseline>"
workflow_lane: "full"
current_phase: "PLAN"                         # Q2: resume at PLAN
# ...standard template fields (recovery, tasks: [], review_cycles: [], acknowledgements: [], workflow)...
promoted_from_lane: true                      # * additive provenance
lane_provenance:                              # * additive provenance
  lane_id: "<lane_id>"
  eligibility: { ...copied from lane.eligibility... }
  decisions: [ ...copied from lane.decisions... ]
  evidence: [ ...any closure gate_evidence gathered... ]
```

### Rules

- **P-1** (FR-014, zero loss): `imported_commits == gitops.commits_in_range(baseline, HEAD)`;
  promotion never rewrites history, only reads and records shas. Each MUST be reachable
  (`is_ancestor`) — else `lane promote` exits `2` (infra error: history diverged, run
  `status rebaseline` guidance).
- **P-2** (FR-015): the synthesized ledger's `lane_provenance` MUST be non-empty (carries
  eligibility answers, decisions, and any gathered evidence) — it never "starts empty".
- **P-3** (FR-016): `reason ∈ {safety-trip, scope-growth}` selects the *trigger*, not the path —
  both call the identical synthesis routine.
- **P-4**: after promotion the lane record is `state: PROMOTED` and read-only; the full
  `specops` workflow proceeds from `status.yaml` at PLAN.

---

## 5. Eligibility criteria (in-code constant, versioned)

A stable, deterministic checklist (FR-004). Version `1`:

| key | question (surfaced by the workflow gate) |
|-----|------------------------------------------|
| `small` | Is this change small (localized, low line/file count in your judgment)? |
| `reversible` | Is it reversible (easily revertable, no data/contract commitment)? |
| `no-high-risk-category` | Does it avoid all six safety-critical categories at entry? |

`criteria_version` is stored on the record so a later criteria change is auditable. SpecOps
**presents** the checklist and **records** the human's confirmation; it does not itself judge
"small" (that is the human's call, per the Design Philosophy "record, do not validate"). The
safety core independently re-checks the diff-detectable categories continuously (§2), so a wrong
`no-high-risk-category: true` answer is still caught at `lane check`/closure.

---

## 6. Safety-core detection model (`safety.py`)

Pure function `detect(diff_status: list[(status, path)], overrides: dict) -> list[Detection]`,
where each `Detection` is `(category, signal_path, status_code)`. Categories and their generic
default signals are enumerated in research R5. `overrides` comes from an optional `lane` block in
`specops.json` (adds/replaces globs per category; never removes the built-in floor for a
category unless explicitly disabled with an audited flag — TBD in tasks, defaulting to
non-removable to protect the core).

State transition (lane lifecycle):

```
                 lane start (eligibility ✓)
   (no lane) ───────────────────────────────▶ OPEN
                                                │
             lane check / attest (per pass)     │  detected category OR attestation=ambiguous
                                                ▼
                                        stop-and-ask (halt | promote)
                                          │              │
                              halt        │              │  promote
                          (stay OPEN,     │              ▼
                           human acts)    │        PROMOTED  ──▶ full `specops` @ PLAN
                                          │
                            lane close (preflight APPROVED + attestation=confirmed)
                                          ▼
                                        CLOSED  (retrospective + evidence)
```
