# Phase 1 Data Model: Native Spec Kit Extension

These are logical entities. Persistence is repository files (`.specify/extensions.yml`,
per-integration command files, `specops.json`, transient backups). No database, no ledger schema
change (Feature 006 owns ledger evolution).

## Entity: Extension Registration

The authoritative record that SpecOps is installed natively, held in `.specify/extensions.yml`.

| Field | Type | Notes |
|-------|------|-------|
| `owner` | string | Constant `specops`; distinguishes SpecOps entries from other extensions. |
| `cli_compat` | object | `{ min_cli_version: string }` — the CLI range this registration targets (R7, FR-016). |
| `hooks` | map<hook-point, list<HookEntry>> | Keyed by `before_<stage>` / `after_<stage>`. |
| `commands` | list<CommandRegistration> | Registered SpecOps command files (R2). |

**Validation**:
- `owner` MUST be `specops` for every SpecOps-authored entry (ownership check, R3).
- Writing MUST preserve non-SpecOps entries untouched (other extensions may share the file).
- Serialization is normalized (stable structure) but compared **semantically**, not byte-wise (R5).

## Entity: Hook Entry

One directive bound to one lifecycle seam.

| Field | Type | Notes |
|-------|------|-------|
| `extension` | string | `specops`. |
| `command` | string | Slash-command id the host will run (dots→hyphens per host rule), or inline directive marker. |
| `hook_point` | enum | `after_specify` \| `before_plan` \| `after_tasks` \| `after_implement` (R1 mapping). |
| `enabled` | bool | Default true. |
| `optional` | bool | `after_specify` = true; others = false. |
| `condition` | string? | SpecOps writes none by default (host-evaluated only). |
| `description` | string | Human summary. |
| `prompt` | string | Directive body, sourced from `src/specops/templates/directives/<stage>.md`. |

**Validation**: `hook_point` MUST be one of the mapped seams; `prompt` MUST be non-empty; duplicate
(`extension`,`command`,`hook_point`) tuples are collapsed (idempotency invariant).

## Entity: Command Registration

A SpecOps-owned command file installed per integration.

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | e.g. `specops-review`. |
| `integration` | string | From `installed_integrations` (e.g. `claude`). |
| `path` | repo-relative path | Derived via `speckit.derive_review_path()` per integration. |
| `separator` | string | Integration invoke separator (e.g. `-`). |

**Validation**: `path` MUST resolve under the integration's command directory; the file is
SpecOps-owned (never listed in the host integration manifest's hashed `files`). One entry per
installed integration (SC-006).

## Entity: Installation State

Derived (not stored authoritatively), computed on demand (R3).

| Value | Condition |
|-------|-----------|
| `absent` | No `extensions.yml` SpecOps entries and no legacy markers. |
| `native` | `extensions.yml` contains SpecOps entries. |
| `legacy` | A host prompt file contains `<!-- SPECOPS:BEGIN … -->` markers. |
| `native+legacy` | Both signals present (partial migration) — recommend completing migration. |

**Transitions**:
`absent → native` (install), `legacy → native` (migrate), `native → absent` (disable/remove),
`native → native` (update, idempotent), `disabled(absent+config) → native` (enable).

## Entity: Migration Backup Set

Transient safety record for a single migration run (R4, FR-008a).

| Field | Type | Notes |
|-------|------|-------|
| `run_id` | string | Unique per migration invocation (derived, not time-based to stay deterministic in tests). |
| `entries` | list<{ original_path, backup_path, sha256 }> | One per host file about to be edited. |
| `location` | repo-relative dir | SpecOps-namespaced under `.specify/` (e.g. `.specify/.specops-backup/<run_id>/`). |

**Lifecycle**: created before the first host-file edit; used to restore on failure/abort (restoring
exact pre-migration bytes, verified by `sha256`); discarded on success. On restore, all entries are
rolled back and the backup set removed.

## Entity: CLI Compatibility Descriptor

| Field | Type | Notes |
|-------|------|-------|
| `installed_cli_version` | string | From `importlib.metadata.version("speckit-specops")`, or absent. |
| `required_range` | string | `min_cli_version` the extension targets. |
| `satisfied` | bool | Result of the check; when false, install refuses and changes nothing (FR-016). |

## Configuration extension (`specops.json`)

Adds compatibility metadata to the existing defaults (`test_command`, `lint_command`, `skills_dir`):

| Key | Type | Notes |
|-----|------|-------|
| `min_cli_version` | string | Mirror of the extension's CLI compatibility floor (retained across disable/enable). |

Existing keys and unknown keys are preserved by `config.merge_preserve` (no breaking change).
