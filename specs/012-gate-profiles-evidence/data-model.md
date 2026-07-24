# Phase 1 Data Model: Gate Profiles and Structured Evidence

Two persisted surfaces: the **gate-profile config** (`.specify/specops/
gate-profiles.yaml`, a new versioned file) and additive extensions to the **Feature
006 ledger** (`specs/<feature>/status.yaml`, migrated v5 → v6). Plus in-memory
result types produced by selection/evaluation.

## 1. Gate-profile config (`.specify/specops/gate-profiles.yaml`)

```yaml
output_version: 1          # bump on any incompatible schema change
profiles:                  # ORDERED list — declared order == execution order
  - name: unit-tests       # stable, unique within the file
    command: "pytest -q"   # client shell string (Principle V — stays in config)
    applies: { always: true }
    timeout: 600           # seconds (int > 0)
    required: true         # default true
    on_nonzero: block      # block | advise (default derived from `required`)
    # artifact: reports/junit.xml   # optional local path to digest
  - name: schema-guard
    command: "scripts/check-migrations.sh"
    applies:               # the single predicate (any combination of keys)
      contexts: [persistence]        # affected context ids
      paths: ["migrations/**"]       # changed-path globs
      risk: { persisted: true }      # named-key presence/equality on ctx.risk
      gate_ref: schema-guard         # honored if a ctx.gates list names it
    timeout: 120
    required: true
```

### `GateProfile` (one list entry)

| Field | Type | Rules |
|---|---|---|
| `name` | string | Required; unique within the file; stable identity (used as gate name + gate-ref target). |
| `command` | string | Required; non-empty client shell string. |
| `applies` | ApplicabilityPredicate | Optional; omitted/empty ⇒ `{always: true}`. |
| `timeout` | int (seconds) \| None | Optional; `> 0`; default `600` for an authored gate, **`None` (unbounded)** for the synthesized default profile (preserves pre-012 lint/test behavior). |
| `required` | bool | Optional; default `true`. The **single** failure-semantics knob — a required gate's non-zero exit blocks, an optional one never does (no separate `on_nonzero`). |

Artifact digesting (`evidence.digest_artifact` + the `artifact_digest` evidence field)
is the mechanism for the **deferred** gate-evidence persistence (R9a); no `artifact`
config key is exposed in this feature.

### `ApplicabilityPredicate` (`applies`)

| Key | Type | Match rule (R9) |
|---|---|---|
| `always` | bool | `true` ⇒ always selected. |
| `contexts` | [string] | Selected if any listed context id is affected (Feature 009 `impact`). |
| `paths` | [glob] | Selected if any changed path matches. |
| `risk` | map | Selected if an affected context's free-form `risk` mapping contains the key (value optional; **named-key presence/equality**, no ordinal scale — Principle V). |
| `gate_ref` | string | Selected if an affected context's `gates` list names this id (implicit context-id match). |

**Validation (`gateprofiles.validate`, read-only, exit `1` on defect — FR-014)**,
each a distinct diagnostic: duplicate `name`; empty/missing `command`; non-positive
`timeout`; unknown `applies` key or unparseable predicate; a `contexts`/`gate_ref`
reference to a context id absent from the map (when a map exists); unsupported
`output_version`. Path-pattern validation is syntactic/safety only (reuse the
`contextmap` `_classify_pattern` idiom — no filesystem access). An **ordering-cycle**
diagnostic is **reserved** — profiles are a v1 linear ordered list, so a cycle is only
possible once a future `after:`/`requires:` ordering hint exists; it is **not** a v1
validation defect.

**Absent file — or a present file with an empty `profiles` list** ⇒ synthesized
default profile from `specops.json` (`test_command`/`lint_command`, R11), preserving
the `lint`/`test` gate names — a supported state, never a defect, never zero gates.

## 2. Ledger v6 additive extensions (`status.yaml`)

`schema_version: 6`. New **top-level** list + record references; every prior v5 field
is preserved and semantically unchanged (FR-019). Back-filled idempotently in
`migrate_to_current` via a new `backfill_evidence(data)` (after the existing
context-provenance / acknowledgements backfills).

```yaml
schema_version: 6
# … all v5 fields unchanged …
evidence:                          # NEW top-level list (explicit [] when none)
  - id: "EV-9f2c1a7b3e04"          # cache-key-derived (R4)
    producer: "gate:unit-tests@0.3.0"   # gate/command identity + CLI version
    command: "pytest -q"
    exit_code: 0
    timestamp: "2026-07-23T14:05:11+00:00"   # zone-aware (Feature 006 idiom)
    commit_range: "a1b2c3d..e4f5a6b"          # baseline..HEAD (or single sha)
    affected_paths: ["src/x.py", "tests/test_x.py"]   # sorted
    summary: "TEST_REPORT: 643 passed"
    artifact_digest: "sha256:…"     # optional (R5); omitted when no artifact
    superseded_by: null             # set to a newer EV-id when a cache-key change replaces it
tasks:
  - id: T001
    # … v5 fields (evidence string retained) …
    evidence: "TEST_REPORT:643 passed; CODE_DIFF:+12/-3"   # legacy string kept
    evidence_refs: ["EV-9f2c1a7b3e04"]                     # NEW — ids into `evidence`
review_cycles:
  - round: 1
    handoff:
      findings:
        - id: "R1-F01"
          # … Feature 011 fields …
          evidence_id: "EV-…"        # NEW — the actual evidence linked at FIXED (Feature 011 FR-005)
```

### `StructuredEvidence` (top-level `evidence[]`)

| Field | Type | Rules |
|---|---|---|
| `id` | string `EV-<hex12>` | Deterministic `sha256(canonical cache_key)[:12]` (R4); unique. |
| `producer` | string | `gate:<name>@<cli-version>` (or `auto` for `complete-task --auto`). |
| `command` | string | The exact command executed (or the harvest description for `--auto`). |
| `exit_code` | int | Process exit; timeout ⇒ synthetic non-zero + `summary` notes `timeout`. |
| `timestamp` | string (ISO-8601, aware) | Feature 006 `to_aware` serialization. |
| `commit_range` | string | `baseline..HEAD`, or a single sha when no range applies. |
| `affected_paths` | [string] | Sorted; the paths the evidence covers. |
| `summary` | string | Concise human summary (captured tail / classifier text). |
| `artifact_digest` | string? | `sha256:<hex>` of a local artifact; omitted when none. |
| `superseded_by` | string?/null | Id of the record that replaced this one on a cache-key change (append-only history). |

**Cache key** = `{producer, command, commit_range, affected_paths, context_map_digest}`.
A gate is `cached` iff a non-superseded record with the **same id** exists (all key
fields matched); any key difference yields a new id ⇒ fresh run ⇒ new record, and the
prior record's `superseded_by` is set (never mutated otherwise).

**Migration (v5 → v6)**: `backfill_evidence` parses each task's legacy `evidence`
string (`<CLASS>:<summary>[; …]`, classes `CLI_LOG|TEST_REPORT|SCREENSHOT_PATH|
CODE_DIFF`) into structured record(s) — `producer="auto"`, `command="(migrated)"`,
`exit_code=0`, `timestamp = task.completed_at or ledger.updated_at`, `commit_range`
from `task.commits`, `affected_paths=[]` (unknown at migration → empty, reported
explicitly), `summary` = the original class:summary — appends them, and sets
`evidence_refs`. Idempotent; the string is retained; absent list ⇒ explicit `[]`.

## 3. In-memory result types (`gateprofiles.py`, `review.py`)

### `SelectedGate`
`{ name, command, applies, timeout, required, on_nonzero, artifact, selected: bool,
reason: str }` — one per declared profile; `reason` is the machine-readable
applied/skipped justification (R9).

### `GateResult` (extended in `review.py`)
Existing `{ name, status: PASS|FAIL|SKIPPED, detail: [str] }` **plus**
`disposition: required|optional|skipped|cached|failed|unavailable` (None for the
non-profile gates). Blocking mapping per research R8.

### `GateReport`
Unchanged public shape: `results: [GateResult]`, `passed` = no required `FAIL`. The
`--json` path adds `disposition`, the covered `commit_range`/`affected_paths`, and the
supporting `evidence_id` to each gate object (FR-011/FR-012).

## Entity relationships

```text
gate-profiles.yaml ──selection(effective diff + context impact)──▶ [SelectedGate]
       │                                                                │ run (required, in order)
       ▼                                                                ▼
   validate (FR-014)                                            GateResult{disposition}
                                                                        │ records / reuses
                                                                        ▼
ledger.evidence[] (StructuredEvidence, id = cache-key hash) ◀── task.evidence_refs
       ▲                                                        └── finding.evidence_id (F011)
       │ migrate v5→v6 (backfill_evidence, zero-loss)
   legacy task.evidence "<CLASS>:<summary>" (retained)
                                                                        │ project (opt-in)
                                                                        ▼
                                                             SARIF 2.1.0 (findings → results)
```

## Invariants

- **EV-1**: Every `evidence[].id` equals the hash of its cache key; identical key ⇒
  identical id (FR-018). A new record is appended on any key change; supersession sets
  `superseded_by` and never mutates the superseded record (FR-009, Principle II).
- **EV-2**: Exactly one `disposition` per profile gate; `unavailable ≠ failed`
  (FR-008).
- **EV-3**: A `required` gate with `disposition ∈ {failed, unavailable}` ⇒
  `GateReport.passed = False` (fail-closed, FR-004/FR-007-adjacent). `optional` never
  flips `passed`.
- **EV-4**: `cached` ⇒ no command executed; the reused record is byte-identical to the
  stored one (FR-009).
- **EV-5**: v6 migration is idempotent and zero-loss; a v5 ledger (legacy strings, no
  `evidence` list) round-trips readable, with `evidence: []` + `evidence_refs: []`
  back-filled explicitly, never omitted (FR-007/FR-019, mirrors `backfill_*`).
- **EV-6**: Read-only commands (`gate list/validate/report`, `--json`) never mutate
  ledger or config (before/after byte comparison, FR-015).
- **EV-7**: Output ordering follows the canonical sort keys (gates by declared order
  then name; evidence by producer then timestamp then commit_range) — FR-021.
</content>
