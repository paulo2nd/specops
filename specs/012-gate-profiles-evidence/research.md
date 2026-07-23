# Phase 0 Research: Gate Profiles and Structured Evidence

All `/speckit-clarify` decisions (Session 2026-07-23) are settled; no
`NEEDS CLARIFICATION` remains. This file records the empirical grounding and the
design decisions that flow from the spec + the current codebase.

## Grounding (verified against the repository, 2026-07-23)

- Review pipeline: `src/specops/review.py` — `GATE_ORDER = ["reconcile", "lint",
  "test", "working-tree", "drift"]`; `evaluate(root)` iterates the order, snapshots
  `dirty_at_start` + `baseline_at_start` once, early-stops on first `FAIL`;
  `_command_gate(name, command, root)` runs a single client command (empty →
  `SKIPPED`), `GateResult(name, status ∈ {PASS,FAIL,SKIPPED}, detail)`,
  `GateReport.passed = all(status != FAIL)`. `run_gates` renders + appends the
  non-blocking map-digest drift warning.
- Outcome contract: `src/specops/outcome.py` — exit `0` ok / `1` blocked / `2`
  error; classes `pass|gate-rejection|infra-error`; `render(command, cls, **extra)`.
- Ledger: `src/specops/ledger.py` — `CURRENT_SCHEMA = 5`, `OLDEST_SUPPORTED = 1`;
  `classify`, `migrate_to_current` (pure, idempotent), `backfill_*` helpers
  (context-provenance v3, acknowledgements v4), `load_raw`, `save(feature_dir, data,
  base_revision=…)` (compare-and-swap). Migration preserves evidence representation.
- Evidence today: `src/specops/status.py` — `EVIDENCE_CLASSES = {CLI_LOG,
  TEST_REPORT, SCREENSHOT_PATH, CODE_DIFF}`; `complete-task --auto` records
  `f"TEST_REPORT:{…}; CODE_DIFF:{…}"`; grammar `<CLASS>:<summary>[; …]`. Task record:
  `{id, status, started_commit, commits, evidence, completed_at, context_provenance}`.
- Context map: `src/specops/contextmap.py` — `MAP_RELPATH = .specify/specops/
  context-map.yaml`; each `Context` has `.gates` (list of gate ids) and `.risk`
  (free-form `dict[str,Any]`); `cmd_impact(root, paths=…)` returns
  `affected=[{context_id, via, reason, gates, risk}]`; `map_digest(root)`;
  `OUTPUT_VERSION = 1`. Feature 008 stores gates/risk as metadata and **defers
  execution/interpretation to Feature 012**.
- Runner: `src/specops/shell.py` — `run_client_command(command, cwd)` = `subprocess.
  run(shell=True, capture_output=True, text=True, errors="replace")`. **No timeout.**
- CLI: `src/specops/cli.py` — Typer sub-apps via `add_typer` (`status`, `context`,
  `trace`, `handoff` → nested `finding`); each read command has a `--json` option
  emitting the Feature 007 outcome JSON.

## R1 — Profile config: location, format, schema

**Decision**: A new versioned YAML file `.specify/specops/gate-profiles.yaml`
(sibling of the context map). Top-level `output_version` + `profiles:` — an **ordered
list**; each entry: `name` (stable, unique), `command` (client shell string),
`applies` (the single predicate, R9), `timeout` (seconds, int), `required` (bool,
default `true`), `on_nonzero` (`block` | `advise`, defaulting from `required`),
optional `artifact` (a path to digest). Loaded/validated by `gateprofiles.py`,
mirroring `contextmap` (a `profiles_path(root)`, a `validate(root) → ValidateResult`,
a stack-neutral parser that never touches the filesystem for path patterns).

**Rationale**: Reuses the shipped `.specify/specops/` namespace and the 008 validation
idiom; richer than the flat `specops.json` keys, so it earns its own file; keeps
`specops.json` (`test_command`/`lint_command`) as the legacy source (R11).

**Alternatives rejected**: (a) embed profiles in `specops.json` — conflates flat
client config with an ordered, predicated schema; (b) reuse the context map's per-
context `gates` as the *definition* — the map only holds gate *ids* (references), not
commands/timeouts, and Feature 008 deliberately deferred definition here.

## R2 — Module layout & the `review.py` integration seam

**Decision**: `gateprofiles.py` (schema + selection), `evidence.py` (records +
migration + digest), `sarif.py` (export). Integrate by **replacing** the `lint`/`test`
branches in `review.evaluate`: the pipeline becomes `reconcile → [selected profile
suite] → working-tree → drift`. `GATE_ORDER` gains a synthetic `profiles` slot in
place of `lint`/`test`; each selected gate becomes one `GateResult` with an added
taxonomy annotation (R8). No standalone runner (clarify decision); read-only `specops
gate list/validate/report` expose selection + evidence.

**Rationale**: The acceptance gate is about the *review verdict*; the current
`lint`/`test` already run before `working-tree`, so the position is preserved and the
change is minimal. Sets up the Feature 017 `preflight` rename with no parallel surface.

**Alternatives rejected**: a standalone `specops gate run` (rejected in clarify — a
parallel surface that would let a workflow author pass gates without the verdict, the
same miscomposition 016/017 warn about).

## R3 — Ledger v5 → v6 evidence migration shape

**Decision**: Bump `CURRENT_SCHEMA` to `6`. Add a **top-level `evidence` list** of
structured records (R4 shape). Tasks gain `evidence_refs: [<id>, …]` and **retain**
their legacy `evidence` string; Feature 011 findings gain an `evidence_id` reference
alongside their existing `<CLASS>:<summary>` link. A new `backfill_evidence(data)`
(idempotent, called from `migrate_to_current` after the existing backfills) parses
every task's legacy `evidence` string into structured record(s), appends them to the
top-level list, and sets the task's `evidence_refs` — **without deleting the string**.
Pre-v6 ledgers with no `evidence` list gain an explicit empty list (never an omitted
key), matching the `backfill_acknowledgements` pattern.

**Rationale**: Purely additive, forward-migrated, zero-loss; v5 readers still see the
string field; the structured list makes evidence queryable and id-addressable. One
schema bump covers US2 + US3.

**Alternatives rejected**: replacing `task.evidence` with a structured object in place
(breaks v5 read-compat and Feature 010/011 rendering); nesting evidence only under
tasks (findings and gate results also need records → a shared top-level list with ids
is the single source).

## R4 — Cache-key-derived evidence id

**Decision**: `id = "EV-" + sha256(canonical_json(cache_key))[:12]` where
`cache_key = {producer, command, commit_range, affected_paths (sorted),
context_map_digest}`. Volatile fields (timestamp, exit code, summary, artifact digest)
are **excluded** from the id. Identical inputs → identical id; any cache-key change →
a different id → a **new** record that supersedes (append-only; the prior record is
retained for audit).

**Rationale**: Makes FR-009 caching a direct id/equality check and makes FR-018
determinism fall out by construction. Append-only supersession preserves auditability
(Principle II) and never mutates an immutable record.

**Alternatives rejected**: sequential `E1,E2,…` (breaks byte-for-byte determinism
across runs and forces a separate key comparison); structural tuple refs with no id
(verbose cross-references, easy to desync — clarify rejected this).

## R5 — Local-artifact digest

**Decision**: When a gate declares `artifact: <path>`, digest that local file's bytes
with `sha256` at production time and store `artifact_digest: "sha256:<hex>"`. No remote
copy is stored (FR-019); a later content change is detectable by re-digesting. Absent
`artifact` → field omitted.

**Rationale**: Stdlib `hashlib`, no dependency; satisfies "optional artifact digest"
and "no remote storage".

## R6 — Deterministic timeout enforcement

**Decision**: Extend `shell.run_client_command(command, cwd, timeout=None)` to pass
`subprocess.run(..., timeout=timeout)`; catch `subprocess.TimeoutExpired` and surface
a sentinel result (a synthetic non-zero return + a `timed_out` flag). A timed-out gate
records outcome `failed` with reason `timeout` and, for a `required` gate, fails the
verdict closed. The **recorded** evidence stores only the *fact* of the timeout and the
configured limit — never elapsed wall-clock ms — so output stays byte-for-byte
deterministic (FR-010/FR-017).

**Rationale**: Additive, backward-compatible (default `None` = today's behavior);
keeps determinism by recording the limit, not the duration.

## R7 — SARIF 2.1.0 projection (opt-in output)

**Decision**: `sarif.py` builds a SARIF **2.1.0** document from Feature 011 findings:
one `run` with a `tool.driver` named `specops` (+ CLI version), each finding → a
`result` with `ruleId` = the finding's rule, `level` mapped from severity
(`blocking → error`, `advisory → warning`), and a `physicalLocation` from the
finding's `file[:line]`. Emitted only when `--sarif` is passed (FR-013); deterministic
ordering (findings by the Feature 011 canonical sort key). Plain `json.dumps` — no
dependency.

**Rationale**: SARIF 2.1.0 is the current OASIS standard consumed by CodeQL/semgrep/
GitHub code-scanning; the projection is a thin, deterministic mapping. This is the
**output** adapter only — the SARIF **input** adapter is Feature 015 (out of scope).

## R8 — Outcome taxonomy ↔ existing PASS/FAIL

**Decision**: Keep `GateResult.status ∈ {PASS,FAIL,SKIPPED}` (drives `GateReport.
passed`) and add `GateResult.disposition ∈ {required, optional, skipped, cached,
failed, unavailable}` for profile gates. Mapping to the blocking decision:

| disposition | status (blocking) | when |
|---|---|---|
| `required` | PASS | required gate ran, exit 0 |
| `cached` | PASS | required/optional gate reused a matching evidence record |
| `optional` | PASS (non-blocking) | optional gate ran, exit 0 — or exit≠0 recorded but `passed` unaffected |
| `skipped` | SKIPPED | predicate did not match this run |
| `failed` | FAIL (if required) | ran and did not satisfy required status (incl. timeout) |
| `unavailable` | FAIL (if required) | command/tool absent — **distinct** from `failed` |

The non-profile gates (`reconcile`, `working-tree`, `drift`) keep bare PASS/FAIL/
SKIPPED (no disposition).

**Rationale**: The taxonomy is an annotation over the proven `passed` semantics, so
the Feature 007 outcome contract and the do-while corrective loop keep working
unchanged; `unavailable` vs `failed` is the one genuinely new distinction (FR-008).

## R9 — Selection inputs (single predicate, map-aware)

**Decision**: The predicate `applies` supports keys (any combination; empty/omitted →
`always`): `always: true`; `contexts: [<id>, …]`; `paths: [<glob>, …]`; `risk:
{<key>: <value?>}`. Selection computes the **effective diff** once
(`gitops.name_only_diff(baseline, HEAD)`) and calls `contextmap.cmd_impact(paths=…)`
to get the affected contexts (each with `gates` + `risk`). A gate is selected when:
`always`; **or** any of its `contexts` is affected; **or** its `gates`-id appears in
an affected context's `gates` list (implicit context-id match, per clarify); **or** a
changed path matches a `paths` glob; **or** a `risk` key is present (optionally
`==` value) in an affected context's `risk` mapping. Every declared gate records a
machine-readable reason (`always | matched context <id> | matched gate-ref <id> |
matched path <glob> | matched risk key <k> | out-of-scope`). No map / no baseline →
only `always` + `paths` predicates can match; the reason states the degrade.

**Rationale**: One selection language (clarify decision), reusing the shipped
`cmd_impact` output verbatim; deterministic and fully explainable.

## R10 — Determinism over recorded state (not re-execution)

**Decision**: FR-017/FR-018 byte-for-byte guarantees apply to output rendered from
**recorded ledger + config + branch** inputs, exactly as Features 008–011 already
scope determinism. A client command's own stdout may vary run-to-run; that variance
lives inside the record's `summary`, and the *record identity* (R4) and *report
ordering* (FR-021) are deterministic regardless.

**Rationale**: Matches the established repo contract; avoids over-promising
reproducibility of nondeterministic third-party commands.

## R11 — Default-profile synthesis & precedence

**Decision**: If `.specify/specops/gate-profiles.yaml` is **absent**, synthesize the
implicit default profile: a `test` gate (`command = test_command`, `always`,
`required = true`) and, when `lint_command` is non-empty, a `lint` gate (`always`,
`required = true`) ordered `lint → test` (today's order). Empty `test_command` →
that gate is `SKIPPED`/`unavailable` exactly as `_command_gate` does now. When the
file is **present**, it is authoritative (it may still reference the client commands by
inlining them). Precedence: explicit file > synthesized default.

**Rationale**: Guarantees an upgraded repo behaves identically before adopting
profiles (roadmap Rule 5); zero behavior change until a profile file is authored.

## R12 — Unified vs split (roadmap replanning check)

**Decision**: Keep 012 **unified**. The split trigger (roadmap Dependency/Replanning
Policy) is *loss of independent testability*, not size. Each user story is
independently testable against fixtures (US1 selection; US2 evidence/migration; US3
taxonomy/caching/verdict; US4 JSON/SARIF), and all four share one v6 migration and one
`review.py` seam — splitting would fork the migration and seam across features and
create the exact ordering coupling the policy warns against. Feature 011 shipped a
comparable 4-US/26-FR scope as one feature.

**Rationale**: Cohesion around a single ledger bump + single integration point; no
independent-testability loss. Recorded here per the policy's "document the reason"
requirement should a future reviewer revisit the size.
</content>
