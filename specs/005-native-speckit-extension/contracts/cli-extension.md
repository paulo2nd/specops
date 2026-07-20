# Contract: `specops extension` command group

A new Typer subgroup (mirrors the existing `status` subgroup). Every command returns exit code `0`
on success and `1` on blocking failure (Principle VI), is non-interactive by default, and performs
no network access (FR-011). All state-changing writes are atomic (R8).

## `specops extension install`

Register SpecOps natively into the current Spec Kit repository.

- **Pre-checks (fail-closed, leave repo unchanged on failure)**:
  1. Current directory is a Git repository (else exit 1).
  2. Spec Kit present (`.specify/templates/`) — else exit 1 (FR-013).
  3. Compatible `specops` CLI present and in range (FR-016, R7) — else exit 1, message names the
     missing/incompatible CLI; **nothing written**.
  4. At least one compatible installed integration resolvable (else exit 1).
- **Effect**: writes/updates `.specify/extensions.yml` SpecOps entries; installs the review command
  file per installed integration; creates/merges `specops.json` (incl. `min_cli_version`).
- **Idempotent**: re-running from the resulting state reports `unchanged` and produces a
  semantically equivalent manifest (FR-005, SC-002).
- **Never** modifies a host-owned prompt file (FR-001, SC-001).
- **Options**: `--non-interactive` (default behavior; present for symmetry with `init`).

## `specops extension update`

Refresh registered hooks/command to the current CLI's template versions.

- Requires an existing native installation (else suggests `install`).
- Re-applies templates; idempotent (semantic equivalence). No host-owned file modified.

## `specops extension disable`

Unregister hooks and command from the host's active surface; retain config and ledgers (FR-010, R6).

- Removes SpecOps entries from `extensions.yml` and removes registered command file(s).
- `specops.json` and any feature ledgers are preserved.
- Idempotent: disabling an already-disabled/absent install reports `unchanged`, exit 0.

## `specops extension enable`

Re-register from retained configuration, restoring the prior native state (FR-010).

- Requires retained `specops.json`; reproduces the same registration as a fresh install.
- Idempotent.

## `specops extension remove [--purge]`

Remove the native installation.

- **Default**: unregister hooks + command; leave **no** integration-managed file modified (SC-004);
  **retain** `specops.json` and feature ledgers (FR-009).
- **`--purge`**: additionally delete `specops.json` and feature ledgers (FR-009a). Never the
  default; requires the explicit flag.
- Idempotent: removing an absent install reports `unchanged`, exit 0.

## `specops extension migrate`

Convert a legacy marker-injected installation to native (FR-007, R3, R4).

- **Pre-checks**: same CLI/Spec Kit/integration fail-closed checks as `install`.
- **Effect (ordered, interruption-safe)**:
  1. Detect legacy markers across resolved host prompt files.
  2. Back up every host file about to be edited (R4, FR-008a).
  3. Strip only SpecOps marker blocks (`initializer.remove_block`, preserving surrounding content).
  4. Write native `extensions.yml` + register command.
  5. On any failure/abort → restore all backups to exact pre-migration bytes (SC-008), exit 1.
- Preserves existing `specops.json` and every feature ledger unchanged (FR-007, SC-003).
- Idempotent: migrating an already-native repo reports `already native`, exit 0.

## `specops extension status`

Read-only. Report detected installation state: `absent` | `native` | `legacy` | `native+legacy`
(FR-006), the installed integrations, and CLI compatibility. **Never mutates** repository state.
Exit 0 always (reporting command), unless the repository is unreadable.

## Retained legacy command

`specops init` is **unchanged** and remains the documented legacy marker-injection path (FR-015).
