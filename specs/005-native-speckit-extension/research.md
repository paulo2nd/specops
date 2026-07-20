# Phase 0 Research: Native Spec Kit Extension

All unknowns are design decisions resolvable from evidence in this repository (the Spec Kit skill
contracts under `.claude/skills/`, the integration manifests under `.specify/`, and the existing
`src/specops/` modules). No `NEEDS CLARIFICATION` remained after `/speckit-clarify`.

## R1 — The native extension mechanism (`.specify/extensions.yml`)

**Decision**: Register SpecOps behavior in a repository-owned `.specify/extensions.yml`, keyed by
lifecycle hook points. Each stage-bearing Spec Kit command reads
`hooks.before_<stage>` / `hooks.after_<stage>` and executes registered entries. A hook entry
carries: `extension` (owner id, e.g. `specops`), `command`, `enabled` (default true), optional
`condition` (left to the host to evaluate — SpecOps writes none by default), `optional`
(true/false), `description`, and `prompt` (the directive body).

**Rationale**: Every installed Spec Kit skill (`speckit-specify`, `speckit-plan`, `speckit-tasks`,
`speckit-implement`, …) already contains a "Check for extension hooks" pre/post block that reads
exactly these keys from `.specify/extensions.yml`. This is the host's *own* mechanism — using it
means SpecOps stops editing host-owned `SKILL.md` files entirely (FR-001, FR-002). `extensions.yml`
is authored/owned by SpecOps (the host only reads it), so writing it does not modify a host-owned
file. PyYAML is already a dependency, so no new package is required.

**Stage → hook mapping** (directive content preserved from `src/specops/templates/directives/`):

| Existing directive | Native hook point | `optional` |
|--------------------|-------------------|------------|
| `specify.md` | `after_specify` | true (best-effort, matches current partial-layout tolerance) |
| `plan.md` | `before_plan` (consistency gate guidance) | false |
| `tasks.md` | `after_tasks` (ledger creation seam) | false |
| `implement.md` | `after_implement` (review-cycle open seam) | false |

**Alternatives considered**: (a) Continue marker injection — rejected: it modifies host-owned files,
the exact fragility this feature removes. (b) A SpecOps-proprietary config the host cannot read —
rejected: the host would never execute the directives. (c) One combined hook on a single stage —
rejected: loses the per-stage seams the directives depend on.

## R2 — Command registration for `/specops-review`

**Decision**: Keep installing the review command as a **SpecOps-owned command file** (never a host
file) at the integration's command path, and record it in `extensions.yml` under a
`commands:` section (id, integration, path) so lifecycle operations can find and remove it. Reuse
`speckit.resolve_prompt_targets()` + `speckit.derive_review_path()` to locate the per-integration
command directory for every installed integration (FR-003, SC-006).

**Rationale**: The review command was already a standalone file, not a marker block, so it is not
host-owned and remains compatible with the native path. Listing it in `extensions.yml` gives the
lifecycle commands a single authoritative registry to enable/disable/remove without scanning the
tree. Iterating `installed_integrations` from `.specify/integration.json` (already implemented)
satisfies "every compatible installed integration."

**Alternatives considered**: Registering the command by editing a host command index — rejected
(host-owned). Relying on filesystem scanning to find the command on removal — rejected (fragile,
non-deterministic).

## R3 — Installation-state detection (absent | native | legacy)

**Decision**: Detect state deterministically:
- **native** if `.specify/extensions.yml` exists and contains SpecOps-owned entries (matching
  `extension: specops`).
- **legacy** if any resolved host prompt file contains a `<!-- SPECOPS:BEGIN … -->` marker
  (detected via the existing `initializer._scan_markers`).
- **absent** otherwise.
Report the detected state via `specops extension status` (FR-006). A repository may be both native
and legacy during a partial migration; report the combined state and recommend completing migration.

**Rationale**: Reuses the existing, tested marker grammar for legacy detection and a simple
ownership check for native. Both signals are file-derived and stable (deterministic).

**Alternatives considered**: A written state flag in `specops.json` — rejected as sole source: it
can drift from reality; file-derived detection is authoritative and self-healing.

## R4 — Migration safety (backup + auto-restore)

**Decision** (from clarification Q2 → A): Before editing any host-owned file, copy it to a
SpecOps-namespaced backup location under `.specify/` (e.g. `.specify/.specops-backup/<run-id>/…`).
Strip only SpecOps marker blocks via `initializer.remove_block` (which already preserves all content
outside the markers and the preceding blank separator). If any step fails or is aborted, restore
every backed-up file to its exact pre-migration bytes, then remove the backup set (FR-008, FR-008a,
SC-008). On success, discard backups. Migration also writes the native `extensions.yml` and
registers the command.

**Rationale**: A pre-edit backup is the cheapest guarantee of the "non-destructive" promise and
directly supports interruption-safety (FR-014). `remove_block` already raises `InjectionError`
without writing on corrupted markers, so a mis-parsed hand-edited file triggers restore rather than
damage.

**Alternatives considered**: Rely on git working-tree recovery — rejected (Q2 chose explicit
backups; not all repos have a clean tree, and SpecOps must not assume git state). Per-file
temp-then-swap without a separate backup — rejected (does not allow restoring an already-committed
partial batch across multiple files).

## R5 — Idempotency by semantic equivalence

**Decision** (from clarification Q5 → B): Judge idempotency by comparing the **parsed** manifest
structure — the set of hook entries (by `extension`+`command`+hook-point), enabled/version state,
and command registrations — ignoring key ordering, formatting, and any host-produced timestamps.
Install/update/migrate are no-ops (report "unchanged") when the resulting parsed state equals the
current parsed state (FR-005, SC-002).

**Rationale**: Byte-identity is brittle against benign YAML serialization differences; semantic
comparison tests what idempotency actually means. PyYAML round-trips give a normalized structure to
compare.

**Alternatives considered**: Byte-identical comparison (Q5 option A) — rejected as brittle.
No-duplicate-only check (option C) — rejected: drops the state-equivalence guarantee.

## R6 — Disable / enable mechanism

**Decision** (from clarification Q4 → A): **Disable unregisters** — remove SpecOps hook entries from
`extensions.yml` and remove the registered command file(s) from the host's active surface, while
retaining `specops.json` and any ledgers. **Enable re-registers** from the retained configuration,
reproducing the same registration state (FR-010). A disabled repository is detected as `absent`
native registration but with retained config.

**Rationale**: Unregistering guarantees zero lifecycle effect while disabled and reuses the exact
install/remove registration paths, so enable is provably identical to a fresh register.

**Alternatives considered**: An inert `enabled: false` flag (option B) — rejected: the command would
still appear on the host surface and relies on the host honoring the flag everywhere.

## R7 — CLI ↔ extension compatibility (FR-016)

**Decision** (from clarification Q1 → A): The install/migrate action records the compatible CLI
version range it targets (a `min_cli_version` written into `extensions.yml`/`specops.json`) and
verifies the invoking `specops` CLI version (via `importlib.metadata.version("speckit-specops")`)
satisfies it. If the CLI is missing or its version is outside the supported range, refuse to
register, report the mismatch, and leave the repository unchanged. The action never installs or
upgrades the CLI itself.

**Concrete floor**: `min_cli_version = "0.3.0"` — the first CLI release that understands the native
`extensions.yml` schema (the package is `0.2.1` today; this feature ships as the `0.3.0` minor). The
compat gate requires the invoking CLI to satisfy `>= 0.3.0`; anything older or absent is refused
(fail-closed). This value drives `pyproject.toml` (T002), the compat gate (T004), and install
orchestration (T016).

**Rationale**: Fail-closed at install time matches the existing FR-013 posture and Principle VI. The
version is already discoverable through `importlib.metadata` (used by `--version`). Recording the
target range lets a future checkout detect a stale extension driven by an older CLI.

**Alternatives considered**: Fail-open with a warning (option B) — rejected (defers a knowable
failure to mid-workflow). Auto-install the CLI (option C) — rejected (couples extension registration
to package management; out of scope per assumptions).

## R8 — Atomicity & interruption-safety

**Decision**: All file writes (extensions.yml, command files, specops.json, backups) use
temp-file-then-atomic-rename within the same directory. Multi-file operations (migration) are
ordered so that a crash at any point leaves either the prior valid state or a state a re-run can
complete/reverse using the backup set (FR-014, SC-007).

**Rationale**: Atomic rename is the standard POSIX/Windows-safe primitive; combined with the backup
set it yields the required interruption-safety without a transaction manager.

**Alternatives considered**: In-place edits — rejected (a crash mid-write corrupts the file). A
lockfile-based transaction — rejected as over-engineered for single-process CLI operations.

## R9 — Offline operation

**Decision**: No network access is performed by any lifecycle command; all inputs are local files
and template assets shipped in the package (FR-011). Verified by an integration test that runs the
full lifecycle with network disabled.

**Rationale**: The templates are packaged (`src/specops/templates/**`), and detection/registration
read only repository files. Nothing requires the network post-install.
