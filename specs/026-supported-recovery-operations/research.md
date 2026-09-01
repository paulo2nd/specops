# Research: Supported Recovery Operations

**Feature**: 026 | **Date**: 2026-08-31 | **Phase**: 0

All decisions below are grounded in the existing code, cited by file and line. No
NEEDS CLARIFICATION markers remain from the spec; the five clarifications plus the
one post-clarification scope decision are already integrated there. What follows
resolves the *technical* unknowns those answers created.

---

## D1 — How the amendment record is represented

**Decision**: reuse the existing Feature 012 structured-evidence record with two
additive optional fields (`amendment: true`, `reason: <str>`) and a new producer
value `"amend"`. No parallel correction store.

**Rationale**: the ledger already owns an append-only, id-addressable evidence
history with a supersede pointer (`superseded_by`) built into every record
(`src/specops/evidence.py:130`). `EvidenceRecord` is a `TypedDict` with
`total=False` extras (`src/specops/records.py:114-116`), so both fields are pure
additions. A separate `amendments:` list would duplicate the supersede machinery,
the id derivation, and the `_evidence_violations` reference check
(`src/specops/ledger.py:585`) for no gain.

**Alternatives considered**:
- *A dedicated top-level `amendments` list.* Rejected: it would need its own
  reference-integrity validation and its own rendering path in every consumer,
  and `task.evidence_refs` would no longer be the single answer to "what evidence
  does this task have".
- *Mutating the existing record in place with a `corrected_to` note.* Rejected
  outright by FR-002 — content of a prior record is never altered.

## D2 — Making the amendment id unique

**Decision**: pass `subject=f"{task_id}#amend:{reason}"` into `evidence.cache_key`,
and on the (possible) collision of two amendments with an identical reason and
commit range, append the count of existing amendments on that task.

**Rationale**: `derive_id` is a deterministic hash of the cache key
(`src/specops/evidence.py:92`), and `append_record` treats an id match as
"already recorded, reuse it" (`src/specops/evidence.py:180-182`). Two amendments
on the same task at the same HEAD with the same reason would otherwise silently
collapse into one — which FR-002b's "amend twice → three records" scenario
forbids, and which the spec's own edge case (amending with identical evidence)
explicitly requires to be recorded anyway. The amendment index is the minimal
disambiguator that keeps the id a pure function of the key.

**Alternatives considered**:
- *Include the timestamp in the key.* Rejected: the cache key deliberately
  excludes volatile fields so re-production is stable
  (`src/specops/evidence.py:63-66`); adding a timestamp for one producer would
  break that property for the shared function.
- *Random/UUID ids for amendments.* Rejected: every other id in the ledger is
  derived; one non-derived id class would make the invariant "ids are a function
  of content" untrue.

## D3 — Task-scoped supersede (the existing helper is not reusable as-is)

**Decision**: do **not** call `append_record(supersede=True)`. Add a task-scoped
supersede step in the amendment path that marks exactly the ids currently listed
in `task["evidence_refs"]` (and not already superseded) as superseded by the new
record.

**Rationale**: this is the one place where the obvious reuse is wrong.
`append_record`'s supersede mode matches on **producer** across the *entire*
ledger evidence list (`src/specops/evidence.py:184-190`) — semantics built for
gate records, where a producer *is* the gate identity. Applied to amendments it
would supersede other tasks' records sharing the producer. The correct scope is
the task's own refs, which FR-002b names explicitly ("supersedes every evidence
record currently attached to the task").

**Alternatives considered**:
- *Generalize `append_record` with a `scope=` parameter.* Rejected as premature:
  two callers, two different scoping rules, and the gate caller must not change.
  A local helper in the amendment path is smaller and cannot regress gate caching.

## D4 — Keeping the legacy evidence string honest

**Decision**: the amendment overwrites `task["evidence"]` with the amended
string, but only after ensuring the previously current value exists as a
structured record. When `task["evidence_refs"]` is empty and the legacy string is
non-empty (a hand-built or hand-edited v8 ledger), materialize the original
through `evidence.parse_legacy_string` first, then supersede it.

**Rationale**: two hard constraints meet here. `reconcile`
(`src/specops/reconcile.py:72`) and `ledger.validate_invariants`
(`src/specops/ledger.py:388`) both fail a DONE task with an empty `evidence`
string, so the field must stay populated. FR-002a makes the amendment the current
value, and `trace report` reads exactly this field (`src/specops/trace.py:454`),
so leaving it stale would contradict the clarification. `migrate_to_current`
already backfills refs for anything that migrates
(`src/specops/ledger.py:269,300`), so the materialize step is a narrow safety net
for current-schema ledgers that never migrated — not the common path.

**Alternatives considered**:
- *Leave the legacy string untouched.* Rejected: it is the value `trace report`
  and every legacy consumer reads; leaving it stale makes the amendment invisible
  exactly where the audit happens.
- *Clear the legacy string and rely on refs.* Rejected: violates the DONE-needs-
  evidence invariant in two independent validators.

## D5 — Schema version

**Decision**: bump `CURRENT_SCHEMA` 8 → 9 as a **pure version bump** with no
backfill, matching the v6→v7 and v7→v8 precedent.

**Rationale**: strictly, `docs/stability.md` classifies an optional added field as
"CHANGELOG note only". But v7 (ingestion extras) and v8 (review-round fields) were
both additive-optional and both took a version bump anyway
(`src/specops/ledger.py:37-45,68-72`), because the version is how an adopter
detects which optional fields *may* be present. Following the house precedent
costs one constant, one migration-test file, and keeps the rule uniform. The
roadmap's "bump with forward migration if the amendment record requires one" is
satisfied either way; uniformity decides it.

**Alternatives considered**:
- *No bump.* Defensible under the letter of the stability policy, rejected for
  consistency with the two immediately preceding features.

## D6 — Aligning feature resolution with Spec Kit

**Decision**: `speckit.resolve_feature_dir` gains `SPECIFY_FEATURE_DIRECTORY` as
the top-precedence source, normalized against the repo root exactly as Spec Kit
normalizes it. SpecOps **reads** the override and never persists it.

**Rationale**: Spec Kit's precedence is `SPECIFY_FEATURE_DIRECTORY` → pointer file
→ error (`.specify/scripts/powershell/common.ps1:155-192`), including
`Join-Path $repoRoot` normalization for a relative value. SpecOps reads only the
pointer file today (`src/specops/speckit.py:25-45`, no `os.environ` anywhere in
`src/`), so with the override set the two tools answer about different features.

The *non*-persistence is the subtler half: Spec Kit persists the override into
`feature.json` unless the caller passes `-NoPersist`, which read-only path
resolution does pass (`common.ps1:146-149`, issue #3025). Every SpecOps read is a
read-only resolution, so persisting would be the behavior Spec Kit explicitly
carved out — and it would dirty the working tree on a plain `specops report`.

**Alternatives considered**:
- *Persist the override on read, like Spec Kit's write path.* Rejected per above.
- *Ignore the override and document the divergence.* Rejected by the spec's own
  scope decision — it is the #75 failure through another door.

## D7 — The inference fallback stays, and announces itself

**Decision**: keep the "newest `specs/NNN-*`" fallback
(`src/specops/speckit.py:47-59`) and return *how* the feature was resolved
alongside *what* was resolved, so `_resolved_feature` can label an inferred
answer.

**Rationale**: Spec Kit errors where SpecOps guesses. Removing the guess would
align the two but break every repository that currently runs without a
`feature.json` — a silent behavior change for existing adopters, which is worse
than the divergence it fixes. Labelling the inference removes the silence, which
is the actual defect (FR-014a says so explicitly).

**Alternatives considered**:
- *Remove the fallback to match Spec Kit exactly.* Rejected as breaking. Noted for
  a future major, not for 026.

## D8 — Where the new code lives

**Decision**: `amend-task` goes in `status.py` beside `complete-task`; `feature
use` / `feature rename` go in a new `src/specops/feature.py`; resolution changes
go in `speckit.py`.

**Rationale**: dictated by the existing one-way import graph. `status` imports
`speckit` and `ledger`; `ledger` imports `speckit`; `speckit` imports neither
(`src/specops/speckit.py:1-8`). `feature rename` needs ledger read/write *and*
directory manipulation, so it cannot live in `speckit` without inverting that
graph. `amend-task` is a ledger state change with the same load/finalize cycle as
its neighbours (`status.load_for_write` / `status.finalize`), so it belongs where
that cycle is already implemented.

**Alternatives considered**:
- *All three in one new `recovery.py`.* Rejected: it would split the task-lifecycle
  commands across two modules for no reason, and `amend-task` is a `status`
  subcommand in the CLI surface regardless of where its code sits.

## D9 — Atomicity of `feature rename` (FR-020)

**Decision**: order the operations so the only irreversible step is last, and
verify every precondition before any of them: (1) validate source/target/ledger,
(2) write the updated ledger *into the source directory* through the normal
revision-CAS save, (3) rewrite the specification's identity header in place,
(4) `os.rename` the directory, (5) write the pointer. A failure before step 4
leaves a source directory that is internally consistent under its new identity;
a failure at 4 or 5 is reported with the exact recovery step.

**Rationale**: `os.rename` of a directory on the same filesystem is atomic; the
ledger save is already atomic and durable (`fsutil.atomic_write`,
`src/specops/fsutil.py:18`); the pointer write can reuse the same primitive. There
is no way to make a multi-file, multi-directory operation transactional on a POSIX
filesystem without a journal, and a journal for a once-per-renumber command is
exactly the over-engineering to avoid. Ordering plus complete up-front validation
gets the guarantee that matters: no half-moved directory, and no pointer aimed at
nothing.

**Alternatives considered**:
- *Copy-then-delete with rollback.* Rejected: strictly worse (non-atomic, doubles
  the failure surface, and a partial copy is the exact state FR-020 forbids).
- *A rename journal in `.specify/`.* Rejected as over-engineering for a command
  run a handful of times in a repository's life.

## D10 — Reporting stale references after a rename (FR-016b)

**Decision**: a plain literal scan of the moved artifacts' text for the old
feature-directory name and the old branch name, reporting file and line number,
changing nothing.

**Rationale**: FR-016a scopes *rewriting* to the one structured header SpecOps
owns; everything else is reported. A literal substring scan has no false-negative
risk that matters and its false positives (a deliberate reference to the old
feature) are exactly the cases a human must judge — which is why the output is
informational and never fails the rename.

**Alternatives considered**:
- *Regex-aware rewriting of prose references.* Rejected by the Q2 answer.
- *No scan at all.* Rejected by the same answer.
