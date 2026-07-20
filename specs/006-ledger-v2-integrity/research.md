# Phase 0 Research: Ledger v2 Integrity

All decisions below were resolved against the current codebase (`status.py`, `gitops.py`,
`reconcile.py`, `migration.py`, `compat.py`, `errors.py`, `templates/status.yaml`) and the
clarified spec. No `NEEDS CLARIFICATION` items remain.

## R1 — Schema version field and classification

- **Decision**: Add a top-level integer `schema_version`. `CURRENT_SCHEMA = 2`, `OLDEST_SUPPORTED = 1`.
  A ledger with **no** `schema_version` key is treated as **v1**. Classification:
  - `schema_version` absent or `== 1` → **migratable-older**
  - `schema_version == 2` → **current**
  - `schema_version >= 3` → **too-new** (refuse state changes; FR-005)
  - `schema_version` present but `< 1` / non-integer / unrecognized → **unsupported** (refuse; FR-006)
- **Rationale**: An integer compare is the simplest deterministic scheme and mirrors the existing
  int-tuple version handling in `compat.py`. Absence-means-v1 lets us classify existing ledgers
  with zero on-disk changes and no ambiguity.
- **Alternatives considered**: Semantic version string (rejected — needless parsing for a
  single-writer local file); a `format: specops/ledger` + version pair (rejected — no second
  producer exists, so a discriminator adds no value yet).

## R2 — Timezone-aware timestamps and stable serialization

- **Decision**: Store timestamps as RFC 3339 / ISO 8601 UTC strings with an explicit offset,
  e.g. `2026-07-19T14:30:22+00:00`, produced by `datetime.datetime.now(datetime.timezone.utc)`.
  Migration converts a pre-existing zone-naive / date-only value (current v1 stores
  `datetime.date.today().isoformat()` → `2026-07-19`) by interpreting it as **UTC midnight**
  and reserializing, preserving the recorded instant (FR-010, clarified default).
- **Stable serialization (FR-011, SC-005)**: `save()` computes a canonical serialization of the
  ledger's **logical** content (everything except the volatile `updated_at`) and compares it to
  what is already on disk. If the logical content is unchanged, the write is skipped entirely —
  no `updated_at` bump, no `revision` bump, byte-identical file. YAML key ordering is already
  deterministic because `yaml.dump` defaults to `sort_keys=True`; we keep that.
- **Rationale**: The current code unconditionally sets `updated_at` on every `_save_ledger`, which
  would defeat idempotency. Gating the write on a logical-content diff is the minimal change that
  makes re-running a no-op operation produce a byte-stable ledger.
- **Alternatives considered**: Always rewrite with a monotonic timestamp (rejected — spurious
  diffs, fails SC-005); strip timestamps from equality but still rewrite (rejected — still churns
  the file and the revision).

## R3 — Concurrency: optimistic revision compare-and-swap

- **Decision**: Add a top-level monotonic integer `revision` (starts at `1` on create, `+1` per
  committed state change). Every state-changing command: (1) loads the ledger and captures
  `base_revision`; (2) mutates in memory; (3) in `save()`, acquires a short-lived exclusive lock
  file `status.yaml.lock` (`os.open` with `O_CREAT|O_EXCL`, released in a `finally`), re-reads the
  on-disk `revision`, and if it differs from `base_revision` **aborts with a stale-state error**
  (no write); otherwise writes `revision = base_revision + 1` via the atomic tmp→fsync→`os.replace`
  path already present in `_save_ledger`. Stale detection is driven by `revision`, never by
  timestamps (FR-016).
- **Rationale**: The roadmap already mandates a ledger-revision field; using it as the CAS token
  gives lost-update protection (FR-012–FR-015) with no new dependency. The lock only narrows the
  in-process read-modify-write window; the durable guarantee is the revision compare, which holds
  even if a lock is stale or unsupported. At most one concurrent writer wins (FR-014); the loser
  gets a clear "ledger moved on — re-read and retry" message (FR-015).
- **Alternatives considered**: `fcntl`/`flock` advisory locks (rejected — not portable to Windows;
  we keep an O_EXCL lockfile that works cross-platform); a long-held lock as the primary mechanism
  (rejected — deadlock/staleness risk and violates "no interactive prompts"); mtime-based staleness
  (rejected — violates FR-016 and is unreliable under clock skew).
- **Lock hygiene**: a stale lockfile from a killed process is tolerated — acquisition treats an
  existing lock older than a short threshold as reclaimable, and in all cases the revision CAS is
  the authority, so a leaked lock can never cause a lost update, only a transient retry.

## R4 — Workspace identity validation (pre-write gate)

- **Decision**: Before any state change, validate three dimensions and fail closed on the first
  mismatch, naming it (FR-018/FR-019):
  - **feature** — `speckit.resolve_feature_dir(root).name` must equal ledger `feature`; if the
    feature cannot be resolved unambiguously, fail closed (FR-020, already the behavior of
    `_get_feature_dir`).
  - **branch** — `gitops.current_branch(repo)` must equal ledger `branch`.
  - **baseline** — ledger `baseline` (the branch-point commit, already captured at `init-spec` as
    `gitops.head_sha`) must be an ancestor of `HEAD` via `gitops.is_ancestor` (Q3 clarification,
    FR-017/FR-017a). An unreachable baseline (branch switch / reset / history rewrite) is a
    divergence.
- **Rationale**: `reconcile.py` already computes exactly these signals but as **warnings**. Feature
  006 promotes them to a hard gate **for state changes only**, reusing `gitops.is_ancestor` and
  `current_branch` verbatim. Read-only `reconcile`/`show` keep the warning behavior (FR-021).
- **Alternatives considered**: A single opaque "workspace fingerprint" hash (rejected — cannot name
  the diverged dimension, which the spec requires); recomputing merge-base against the default
  branch (rejected in Q3 in favor of the stored branch-point baseline).

## R5 — Atomicity, interruption safety, and recovery metadata

- **Decision**: Reuse the existing atomic write (`tmp.write_text` → `fsync` → `os.replace`), which
  already guarantees FR-022/FR-023 (an interrupted write leaves the prior complete ledger, never a
  truncated file — `os.replace` is atomic on POSIX and Windows). Extend `recovery` with
  `last_consistent_revision` and `last_consistent_at` (the revision/timestamp of the last committed
  state) and, after a migration, a `migrated_from_backup` reference (see R6). Formalize the
  guarantee with an injected-interruption test that kills between `tmp` write and `os.replace`.
- **Rationale**: The durability primitive already exists and is correct; this feature formalizes and
  tests it, and adds the recovery breadcrumbs required by FR-024. The lock and `.tmp`/`.lock`
  sidecars are cleaned up on the happy path and are harmless leftovers otherwise.
- **Alternatives considered**: Write-ahead log / journal (rejected — over-engineered for a single
  small file that `os.replace` already makes atomic).

## R6 — Migration engine and pre-migration backup

- **Decision**: `ledger.migrate_to_current(data) -> dict` applies an ordered list of pure step
  functions (`_v1_to_v2`) that back-fill new fields deterministically: `schema_version = 2`,
  `revision = 1`, `workflow_lane = "full"`, `active_artifact` derived from `current_phase`,
  zone-aware timestamps, and enriched `recovery`. Before the migrated ledger is written, the
  original bytes are copied to a retained backup under `.specify/.specops-backup/` mirroring the
  ledger's repo-relative path (reusing the `migration.BackupSet` convention from Feature 005), and
  the backup path is recorded in `recovery.migrated_from_backup` (Q1 clarification, FR-008a).
  - **Auto-trigger** (Q2, FR-008b): the state-change load path classifies the ledger; if
    migratable-older, it migrates in memory + backs up the original, then proceeds with the
    operation (single atomic write). Read-only paths never trigger this (FR-007).
  - **Explicit command** (Q2, FR-008b): `specops status migrate` performs the same migration
    deliberately and idempotently, reporting `migrated` / `already current` / a refusal for
    too-new/unsupported. Migrating a current ledger is a no-op that does not rewrite it (FR-008).
- **Rationale**: Ordered pure step functions keep migration deterministic and unit-testable per
  shape (SC-001), and reusing the proven `BackupSet`/`.specops-backup` pattern avoids inventing a
  second backup mechanism. Backing up before overwrite gives the deterministic rollback the
  clarification asked for.
- **Alternatives considered**: In-place field-add without backup (rejected in Q1 — no recovery from
  a defective migration); a separate `status.yaml.bak` sibling (rejected — pollutes the feature dir
  and diverges from the established namespaced backup location).

## R7 — Formalized invariants

- **Decision**: `ledger.validate_invariants(data) -> list[str]` returns human-readable violation
  strings; a non-empty result blocks a state change (fail closed, FR-025) and is surfaced via
  `SpecopsError`/`LedgerParseError`. Enforced invariants:
  - **Phases**: `current_phase ∈ PHASES`; the phase machine only advances per the existing
    transition rules (SPECIFY→PLAN→TASKS→IMPLEMENT→REVIEW→DONE, plus REVIEW→IMPLEMENT on REJECTED).
  - **Tasks**: `status ∈ {PENDING, IN_PROGRESS, DONE}`; at most one non-orphaned IN_PROGRESS task;
    a DONE task has non-empty `evidence`; referenced commits are well-formed.
  - **Recovery**: `recovery.active_task` is null or matches the single IN_PROGRESS task id.
  - **Review cycles**: rounds are strictly increasing from 1; at most one open cycle (`result: null`).
- **Rationale**: These invariants already exist implicitly across `status.py`'s scattered checks;
  centralizing them as one validator both documents them (FR-026) and lets every state change
  fail closed on a hand-corrupted ledger instead of writing on top of invalid state.
- **Alternatives considered**: A full JSON-Schema/`pydantic` model (rejected — adds a dependency and
  is heavier than the handful of structural rules; PyYAML + explicit checks stay within the
  constitution's dependency limits).

## R8 — New metadata: workflow lane and active artifact

- **Decision**: Add top-level `workflow_lane` (default `"full"`) and `active_artifact` (the artifact
  associated with the current phase, e.g. `spec.md` at SPECIFY, `plan.md` at PLAN, `tasks.md` at
  TASKS/IMPLEMENT), alongside `revision`. Both are populated on create and back-filled during
  migration. `workflow_lane` is forward-compatible with Feature 013's lightweight lane; this feature
  only ever sets `"full"`.
- **Rationale**: The roadmap's Feature 006 required outcomes list these fields explicitly; adding
  them now (defaulted, inert) lets later features consume them without another migration.
- **Alternatives considered**: Defer the fields to the feature that first uses them (rejected — that
  forces an extra schema bump and migration later; adding inert, documented fields now is cheaper).

## R9 — v1 read compatibility and read-only safety on abnormal ledgers

- **Decision**: All read-only surfaces (`cmd_show`, `reconcile.run`, `read_baseline`, and the future
  diagnostics) read the raw dict without migrating (FR-007/FR-029) and never write. For a too-new,
  unsupported-older, or malformed ledger, read-only paths report best-effort status plus a clear
  diagnostic and exit non-destructively — they do not raise a hard failure that suppresses all
  output (Q4, FR-029a). `LedgerParseError` (exit 2) remains reserved for genuinely unparseable YAML,
  where "best effort" is a one-line diagnostic rather than a stack trace.
- **Rationale**: Upholds the global DoD ("read-only commands do not mutate") and gives users a way to
  *see* why a ledger is stuck without being forced into a write. The existing `cmd_show`/`reconcile`
  already read generic dicts, so the change is additive (tolerate missing v2 keys, add diagnostics).
- **Alternatives considered**: Symmetric hard-fail on any unvalidatable ledger (rejected in Q4 — it
  blinds the user to the diagnostic exactly when they need it).

## Dependency / tooling notes

- **No new runtime dependency** (Typer/PyYAML/GitPython only). Locking and timestamps are stdlib.
- **Quality gates** (unchanged): ruff (line-length 100), mypy (`disallow_untyped_defs`), pytest with
  `--cov-fail-under=85`. New public functions in `ledger.py` carry full type annotations and tests.
- **No self-application** (constitution Development Workflow): all behavior is validated via `tests/`
  fixtures — synthetic v1 ledgers, injected interruptions, simulated concurrent writers — never by
  running `specops` against this repository.
