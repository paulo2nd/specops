# Research: Hardening II — API & State Robustness

**Feature**: 019-api-state-robustness | **Date**: 2026-07-27

Every decision below was made against the verified worktree (file:line references
checked on branch `019-api-state-robustness` at the time of planning). No NEEDS
CLARIFICATION markers remained in the spec; the one open design decision the roadmap
delegated to this plan is D1.

## D1 — Ledger-lock stale reclaim: harden in-tree with atomic-rename (reject `filelock`)

**The defect** (`src/specops/ledger.py:722-744`, `_LedgerLock.__enter__`): on
`FileExistsError`, a contender stats the lock's mtime and, when older than `stale`
(30 s), performs `os.unlink(self.lock_path)` then loops back to `os.open(O_CREAT|O_EXCL)`.
Reclaim is therefore **check → unlink → create** as three separate steps. Two waiting
contenders A and B can both observe "stale"; A unlinks and creates its fresh lock; B then
unlinks **A's fresh lock** and creates its own — both now believe they hold the lock and
both enter the read-modify-write section. The revision-CAS in `ledger.save` bounds the
damage (one writer fails late with `StaleLedgerError`), but the lock's own guarantee is
broken in exactly the scenario it exists for.

**Decision**: harden the in-tree lock by serializing stale reclaim through a
**reclaim-mutex sentinel**. To remove a stale lock, a contender must first win
`<lock>.reclaim` via `O_CREAT|O_EXCL` (single winner by construction); under that mutex
it **re-checks** the main lock's staleness and only then unlinks it; the sentinel is
released token-checked (like `__exit__`). Losers fall back to the ordinary wait loop
(deadline + 50 ms sleep). A sentinel leaked by a reclaimer that crashed mid-reclaim goes
stale by age and is removed so later passes retry. Everything else is preserved:
owner-token stamping, token-checked release in `__exit__`, timeout diagnostics, the 30 s
stale threshold, and the mtime-based staleness check.

> **Design revision during implementation (falsified by the FR-002 test)**: the plan's
> first design — atomic-rename reclaim to a unique per-contender name — closed the
> unlink race but not the class of bug: `os.rename` operates on the *name*, so a slow
> contender that had judged the old file stale could rename away the **fresh** lock the
> winner had just created (same TOCTOU, one step later; the race test caught it as
> 3 simultaneous holders with no token violation). POSIX offers no compare-and-unlink,
> so no name-based single-step reclaim can pin the checked inode; the reclaim-mutex +
> re-check-under-mutex design is the correct portable fix. With the single-crash
> assumption of G3 (a stale lock's owner is dead), reclaim is exactly single-winner and
> a fresh lock is never touched; multi-crash edge cases degrade no worse than today,
> with the revision-CAS (G7) as the durable backstop.

**Rationale**:
- Fixes the single-winner property with ~10 lines, no new failure modes on the
  uncontended fast path (unchanged `O_CREAT|O_EXCL`).
- Keeps the constitution's dependency posture: the 1.0-readiness cycle is *shrinking*
  the dependency tree (Feature 020 removes GitPython); adding a locking dependency cuts
  against that direction and would demand Complexity Tracking justification.
- The revision-CAS remains the durable authority (spec assumption); the lock stays an
  in-process contention reducer — now with a correct reclaim.

**Alternatives considered**:
- **`filelock` (PyPI)**: uses OS-level locks (`fcntl`/`msvcrt`) that auto-release on
  process death, eliminating the stale-file concept entirely — genuinely attractive.
  Rejected because: (a) it is a new runtime dependency in a cycle whose explicit goal is
  a minimal footprint; (b) it changes observable failure semantics (no stale-age
  diagnostics; a crashed holder's lock file lingers inertly), risking output/diagnostic
  drift against FR-013; (c) `fcntl` locks are unreliable on some network filesystems,
  where the current file-existence protocol at least degrades predictably.
- **`O_EXCL` + fstat identity check before unlink**: narrows but does not close the
  window (check and unlink remain two steps).
- **Directory-based lock (`mkdir`)**: same TOCTOU on stale reclaim; no gain over rename.

**Test obligation (FR-002/SC-002)**: `tests/unit/test_ledger_lock.py` pre-creates a lock
file with an artificially old mtime (`os.utime`), releases N barrier-synchronized threads
into `_LedgerLock.__enter__`, and inside the critical section each winner re-reads the
lock file and asserts it still contains **its own token** (double-grant makes the earlier
winner observe the later winner's token — the deterministic detection signal), plus a
max-concurrency counter asserting one holder at a time. Against the old implementation
the token assertion trips; against the new one the suite passes repeatedly (loop the race
to amplify confidence).

## D2 — The verbatim DONE-gate duplicate: one `_require_approved_cycle` helper

**Verified duplication** (`src/specops/status.py`): inside `cmd_transition_phase`, the
REVIEW→DONE branch (lines 702-710) and the plain `elif target == "DONE"` branch (lines
711-721) contain the **byte-identical** Feature 006 cycle-result gate — "no review cycles
recorded" refusal, `latest = cycles[-1]`, `latest_result != "APPROVED"` refusal with the
same message. This is the "duplicated verbatim" gate the roadmap names.

**Decision**: extract a single `_require_approved_cycle(cycles: list[ReviewCycleRecord])
-> None` (raises `SpecopsError` with today's exact messages). Both DONE branches call it;
the REVIEW→DONE branch keeps its preceding APPROVED-result application and REJECTED
refusal (order preserved — R1 comment: result applied to the open cycle *before* the gate
check). The Feature 011 blocking-findings gate (`handoff.blocking_approval_check`,
`status.py:680-688`) is *already* single-sourced and consumed by `doctor`,
`compact_status`, and `handoff` — it needs no change beyond keeping its position guarding
every DONE entry before the cycle gate.

**Alternatives considered**: moving the whole DONE gate into `handoff.py` — rejected;
the cycle-result gate predates handoffs (Feature 006) and concerns review cycles, not
findings; `status.py` (the state machine) is its natural owner.

## D3 — Decomposition map for the long state transitions

**Verified**: `cmd_transition_phase` is ~155 lines (`status.py:571-726`) mixing result
validation, phase-sequence validation, REVIEW-entry cycle management, corrective-round
bookkeeping, two DONE gates, and persistence. `cmd_complete_task` is ~100 lines
(`status.py:402-505`) mixing precondition checks, auto/manual evidence collection,
provenance snapshotting, and the v6 evidence record.

**Decision** — named sub-steps, all module-private, behavior byte-identical:

`cmd_transition_phase` becomes a thin orchestrator over:
1. `_normalize_result(result) -> str | None` — the R2 pre-read vocabulary check.
2. `_validate_transition(current, target, normalized_result) -> None` — sequence +
   REVIEW→IMPLEMENT(REJECTED) exception (messages unchanged).
3. `_enter_review(data, root, repo) -> None` — placeholder activation vs new-cycle append
   (including Feature 009 provenance).
4. `_close_rejected_review(data) -> None` — corrective-round close + next placeholder.
5. `_gate_done(data, current, normalized_result) -> None` — the ordered DONE gates:
   blocking-findings check (Feature 011), then result application + `_require_approved_cycle`
   (D2), preserving today's exact order and messages.
6. Persistence via the existing `finalize`.

`cmd_complete_task` becomes an orchestrator over:
1. `_validate_evidence_args(auto, evidence)` — the XOR argument check.
2. `_require_in_progress(task_map, task_id) -> TaskRecord` — status + `started_commit`
   preconditions.
3. `_auto_evidence(root, repo, task, started, changed_files)` /
   `_manual_evidence(evidence)` — each returning the evidence string + command + commits.
4. `_record_completion(data, task, ...)` — provenance snapshot, v6 evidence record,
   recovery bookkeeping.

**Rationale**: each sub-step is independently unit-testable and names the invariant it
enforces; the orchestrators read as the state-machine documentation. The existing tests
(which exercise every failure path through the CLI) are the byte-identical harness.

## D4 — Typed ledger records: new dependency-free `records.py` with `TypedDict`s

**Verified**: zero `TypedDict` in the codebase; ledger records flow as untyped `dict`
through `ledger.py`, `status.py`, `handoff.py`, `findings.py`, `evidence.py` (mypy runs
with `disallow_untyped_defs` but key access is unchecked).

**Decision**: create `src/specops/records.py` (stdlib-only, no intra-package imports —
same posture as `evidence.py`) defining, with `total=False` for optional/afterward-added
keys:

- `TaskRecord` (id, status, started_commit, commits, evidence, completed_at, orphaned,
  context_provenance, evidence_refs)
- `FindingRecord` (the 14 base keys of `findings.new_finding` + optional `imported`,
  `producer`, `reviewed_digest`, `promotion`, `dismiss_reason`, `evidence_id`)
- `ReviewCycleRecord` (round, started_at, completed_at, result, context_provenance,
  handoff)
- `HandoffRecord` (authorized_paths, closed_at, findings)
- `EvidenceRecord` (mirrors `evidence.build_record` output exactly)
- `ContextProvenance` (map, digest, context_ids)
- `LedgerDocument` (the top-level `status.yaml` mapping: schema_version, feature, branch,
  baseline, current_phase, active_artifact, revision, updated_at, tasks, review_cycles,
  evidence, acknowledgements, workflow, recovery, lane provenance keys)

Producing/consuming signatures adopt the types where the value is structurally known:
`findings.new_finding -> FindingRecord`, `evidence.build_record -> EvidenceRecord`,
`handoff._iter_findings -> Iterator[tuple[ReviewCycleRecord, FindingRecord]]`, the D3
sub-step signatures, `ledger.validate_invariants(data: LedgerDocument)`, etc. Boundary
rule: values arriving from `yaml.safe_load` enter as `dict` and are cast **once** at the
canonical load points (`ledger.load_raw` callers that have classified the ledger); the
tolerant runtime filtering (`isinstance(t, dict)`) stays exactly as-is — TypedDicts are a
static contract, never runtime validation (spec assumption).

**Rationale**: key-level mypy checking (a seeded typo like `task["staus"]` fails the
check — quickstart documents the probe) with zero serialization change, since a TypedDict
*is* a dict at runtime. No new mypy overrides (FR-006).

**Alternatives considered**: dataclasses with to/from-dict converters — rejected
(serialization-order and round-trip risk, large diff, runtime cost); pydantic — already
rejected in the 2026-07 review triage (dependency + runtime validation this feature
explicitly does not want).

## D5 — Handoff loader: `LoadedLedger` + typed refusal, converted in one place

**Verified**: `handoff._load_write` (`handoff.py:202-213`) returns
`HandoffResult | tuple[Path, dict, int, list[str], Any]`; **9** call sites repeat
`isinstance(loaded, HandoffResult)` + re-wrap (`cmd_finding_add`, `cmd_authorize`,
`cmd_finding_fix`, `cmd_finding_verify`, `cmd_finding_dismiss`, `cmd_close`,
`cmd_import`, `_apply_import`, `cmd_finding_promote`).

**Decision**:
- `@dataclass(frozen=True) LoadedLedger`: `feature_dir: Path`, `data: LedgerDocument`,
  `base_revision: int`, `base_violations: list[str]`, `repo: git.Repo` — replacing the
  positional 5-tuple.
- `_load_write` returns `LoadedLedger` and **raises** `HandoffLoadRefused(status, human)`
  (module-private exception) for the not-a-repo case.
- One conversion point: a small decorator `_handoff_command(cmd)` (or an equivalent
  try/except in each command — the decorator is preferred to keep the conversion single)
  that catches `HandoffLoadRefused` and returns `HandoffResult(cmd, e.status, e.human)`,
  reproducing today's exact re-wrap semantics (the generic `"handoff: not a Git
  repository"` human text with the specific command name — byte-identical).
- SC-004: zero `isinstance(loaded, HandoffResult)` remains.

**Alternatives considered**: returning `tuple[LoadedLedger | None, HandoffResult | None]`
— still a union probe; raising `SpecopsError` — wrong, it would change the
status→class→exit mapping (NOT_A_REPO renders through the HandoffResult envelope today).

## D6 — One `--name-status` parser in `gitops`, rename-awareness as a parameter

**Verified duplication**: the parse loop `split("\t")` → `(parts[0][:1], parts[-1])`
exists twice — `gitops.effective_diff_status` (`gitops.py:117-123`, invoked with
`--no-renames`) and `lane._parse_name_status` (`lane.py:159-170`, invoked with `-M`,
plus a `--cached` variant in `lane._diff_status`). `trace._name_status` already delegates
to `gitops.effective_diff_status` (no third copy).

**Decision**: `gitops` gains the single parser and a parameterized invocation:

```python
def parse_name_status(raw: str) -> list[tuple[str, str]]           # the one parse loop
def name_status_diff(repo, start_sha, end_sha="HEAD", *,
                     rename_aware: bool, cached: bool = False) -> list[tuple[str, str]]
```

- `rename_aware=False` → `--no-renames` (renames decomposed; today's
  `effective_diff_status` semantics — it becomes a thin wrapper, keeping its name and
  docstring for its existing consumers).
- `rename_aware=True` → `-M` (single `R` on the new path; today's lane semantics).
- `cached=True` → `--cached` staged diff (lane's second call).
- Error behavior preserved per caller: `effective_diff_status` keeps returning `[]` on
  `GitCommandError`; lane keeps its `contextlib.suppress` degrade — the shared function
  raises and each caller keeps its current handling (no behavior merge).

`lane._parse_name_status` is deleted; `lane._diff_status` composes the shared function.

**Alternatives considered**: parameterizing on raw flag lists — rejected (stringly-typed;
the two semantic modes are the entire domain).

## D7 — `(human)` sentinel out of `gitops`: `ledger.HUMAN_COMMIT`, callers filter

**Verified**: `gitops.is_ancestor` short-circuits `if sha == "(human)": return True`
(`gitops.py:45`). Call-site audit of `is_ancestor`:

| Call site | Value checked | Can be `(human)` today? | Post-change handling |
|---|---|---|---|
| `reconcile.py:58` (baseline warn) | ledger `baseline` | hand-edited only | filter via predicate (preserve pass) |
| `reconcile.py:70` (task commits) | task `commits[]` | yes (R11 exemption) | already filters explicitly — unchanged |
| `ledger.py:607` `validate_identity` (baseline) | ledger `baseline` | hand-edited only | filter via predicate (preserve pass) |
| `handoff.py:693` `cmd_validate` (finding commits) | finding `commits[]` | yes (legacy/hand-authored) | add explicit filter (preserve pass) |
| `lane.py:453` `cmd_promote` (baseline) | lane `baseline` | guarded by `commit_exists` first, which already fails `(human)` today | no filter needed — behavior identical either way |

**Decision**: remove the sentinel from `gitops.is_ancestor`. Add to `ledger.py` (the
domain that owns the convention, one-way importable from every consumer):

```python
HUMAN_COMMIT = "(human)"
def is_human_commit(sha: str) -> bool: ...
```

Callers that today inherit the exemption apply it explicitly per the table (reconcile
task-commit loop already does — it switches to the shared constant). Every command that
exempts `(human)` today continues to (spec FR-009), including the hand-edited-baseline
paths, so behavior is strictly preserved.

**Alternatives considered**: leaving the sentinel in `gitops` with a docstring — rejected
(the roadmap names this leak explicitly; a generic git layer must not know ledger
conventions, and Feature 020 will rebuild that layer).

## D8 — Template rendering completeness: `fsutil.render_template`

**Verified render sites** (chained `.replace("{{...}}", …)` with no residue check):
`status.cmd_init_spec` (`status.py:259-267`), `status.synthesize_ledger_at_plan`
(`status.py:298-306`), `lane.cmd_start` (`lane.py:264-273`). A placeholder added to
`src/specops/templates/status.yaml` or `templates/lane.yaml` without a matching
`.replace` silently ships `{{...}}` residue into a client's ledger/lane record today.
(The `initializer`/`extension` marker-block mechanism is a different system — verified
not a `{{...}}` renderer — and is out of scope.)

**Decision**: add to `fsutil.py` (the shared low-level utility home, no import cycles):

```python
def render_template(text: str, mapping: dict[str, str]) -> str
```

Applies every `{{key}}` → value, then asserts completeness: any remaining `{{...}}`
token raises `SpecopsError` naming the unfilled placeholder(s). Unknown mapping keys
(supplied but absent from the template) are ignored — additive templates must not break
old code. The three sites switch to it; per the spec assumption, no current template
legitimately emits literal `{{`, so any residue is drift. A unit test corrupts a template
copy with a novel placeholder and asserts the loud failure (SC-006).

**Alternatives considered**: `string.Template`/`str.format` — rejected (changes escaping
semantics of template files that live in client scaffolds; `$`/`{}` collide with YAML
content more than the current `{{...}}` convention).

## D9 — Gate-profile field knowledge: one declarative table

**Verified duplication** (`gateprofiles.py`): field names, types, and defaults are
spelled once leniently in `_parse_profile`/`_parse_predicate` (lines 138-197) and again
prescriptively in `validate`/`_validate_applies` (lines 356-455) — `name`, `command`,
`timeout` (+ positivity), `required`, and the `applies` keys (`always`, `contexts`,
`paths`, `risk`, `gate_ref`, the `_VALID_APPLIES_KEYS` set). A field added to one side
can silently be forgotten by the other.

**Decision**: introduce a module-level declarative table — one entry per field carrying
its name, expected type spec, default, and defect-message template — consumed by **both**
the lenient parser (coerce/fall back per the table) and the validator (report a defect
per the table). The table also derives `_VALID_APPLIES_KEYS`. Semantics-preserving:
lenient parse keeps every current fallback (e.g. non-int `timeout` → `DEFAULT_TIMEOUT`,
non-mapping `applies` → always), and validate keeps every current message and the checks
that are *not* per-field shape checks (duplicate names, unknown-context references,
pattern classification) as explicit code.

**Alternatives considered**: generating validation from the dataclass field types —
rejected (the lenient-parse fallbacks and the human defect messages are the actual
knowledge; type introspection cannot carry them).

## D10 — Doctor error flow: no exceptions as call arguments

**Verified** (`doctor.py`): `diagnose` captures `state_error: Exception | None` from
`migration.detect_state` and threads it into `_domain_cli_extension(install_state,
state_error)` and `_domain_legacy(install_state, state_error)`, each of which starts with
`if state_error is not None: raise state_error` so the generic `_run` wrapper converts it
— an exception smuggled through two argument lists just to be re-raised.

**Decision**: extract the conversion in `_run`'s except-arms into a shared
`_error_domain(domain: str, exc: Exception) -> DomainResult` helper (used by `_run`
unchanged). In `diagnose`, when the shared `detect_state` read fails, build the two
affected domains' results directly via `_error_domain(D_CLI_EXTENSION, exc)` /
`_error_domain(D_LEGACY, exc)` instead of threading the exception. The two domain checks
drop their `state_error` parameter entirely. Output is byte-identical because
`_error_domain` is the same conversion `_run` performs today (same severities, ids,
messages, `next_action_code`s).

**Alternatives considered**: a `Result`-style union return from `detect_state` — rejected
(re-introduces the class-probing pattern D5 removes elsewhere).

## Inventory summary (baselines for SC-003/SC-004)

| Concern | Today | After |
|---|---|---|
| Feature 006 DONE cycle gate | 2 verbatim copies (`status.py:702-710`, `711-721`) | 1 (`_require_approved_cycle`) |
| `--name-status` parse loop | 2 (`gitops.py:117-123`, `lane.py:159-170`) | 1 (`gitops.parse_name_status`) |
| `(human)` in generic git layer | 1 (`gitops.py:45`) | 0 (ledger-owned constant, callers filter) |
| `isinstance(loaded, HandoffResult)` probes | 9 | 0 |
| Unchecked `{{...}}` render sites | 3 | 0 (all via `fsutil.render_template`) |
| Gate-profile field spellings | 2 (parse + validate) | 1 (declarative table) |
| Exceptions threaded as arguments (doctor) | 2 parameters | 0 |
| `TypedDict` ledger schemas | 0 | 7 types in `records.py` |
