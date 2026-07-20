# Implementation Plan: Native Spec Kit Extension

**Branch**: `005-native-speckit-extension` | **Date**: 2026-07-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/005-native-speckit-extension/spec.md`

## Summary

Deliver SpecOps through Spec Kit's **own native extension mechanism** — a repository-owned
`.specify/extensions.yml` hook manifest plus per-integration command registration — instead of
injecting `<!-- SPECOPS:BEGIN … -->` marker blocks into host-owned prompt files. The Python
`specops` CLI remains the deterministic engine; the extension layer only registers hooks/commands
that call it. A new `specops extension` command group provides idempotent install, update,
disable, enable, remove (with opt-in purge), a legacy→native migration with per-file backup and
auto-restore, and a state-detection surface. The current marker-injection path (`specops init`) is
retained unchanged as the documented legacy path.

Technical approach (from research): the four stage directives (`specify`, `plan`, `tasks`,
`implement`) currently marker-injected into host `SKILL.md` files become `before_*`/`after_*`
entries in `.specify/extensions.yml`, whose `prompt` bodies are the existing directive templates.
The `/specops-review` command continues to be installed as a SpecOps-owned command file (never a
host file) and is now registered through the integration manifest rather than by editing host
prompts. Idempotency is judged by semantic equivalence of the parsed manifest; all writes are
atomic (temp-then-rename); migration backs up every host file before stripping markers.

## Technical Context

**Language/Version**: Python 3.10+ (`requires-python = ">=3.10"`, ruff/mypy target py310)

**Primary Dependencies**: Typer (CLI), PyYAML (extensions.yml read/write — already a dependency),
GitPython (unchanged). **No new runtime dependency** is introduced.

**Storage**: Repository files only — `.specify/extensions.yml` (new, SpecOps-authored),
per-integration command files under the integration command directory, `specops.json`
(extended with compatibility metadata), and transient migration backups under
`.specify/` (SpecOps-namespaced).

**Testing**: pytest (unit + integration), fixtures under `tests/`; ruff + mypy at repo thresholds.
Per the constitution, SpecOps is **not** self-applied here — behavior is validated through
test-suite fixtures, never by running `specops` against this repository.

**Target Platform**: Cross-platform CLI (Linux/macOS/Windows); offline after install.

**Project Type**: Single Python CLI package (`src/specops/`).

**Performance Goals**: Interactive CLI latency (each lifecycle command completes in well under a
second on a normal repository); no throughput target.

**Constraints**: Offline after install (FR-011); atomic and interruption-safe state changes
(FR-014); zero modification of host-owned files on the native path (FR-001); fail-closed on missing
Spec Kit, incompatible integration, or missing/incompatible CLI (FR-013, FR-016).

**Scale/Scope**: One repository, one `.specify/extensions.yml`, N installed integrations (today: 1,
`claude`). Roughly three new modules, one CLI subcommand group, one template asset, plus tests and
bilingual docs.

## Constitution Check

*GATE: evaluated against constitution v1.3.0. Re-checked after Phase 1 design.*

| Principle | Assessment | Verdict |
|-----------|------------|---------|
| **I. Speckit Extension, Never Replacement (NON-NEGOTIABLE)** | This feature is the strongest possible expression of the principle: it moves from editing host prompt files to Spec Kit's own extension registry, touching **zero** host-owned files on the native path, and migration *removes* prior host-file edits. See "Constitution evolution note" below. | PASS |
| **II. Physical State Ledger** | No ledger schema change (explicit non-goal). Extension registration state lives in SpecOps-authored files, mutated exclusively by CLI commands — never hand-edited. | PASS |
| **III. Automated Evidence Collection** | No change to evidence collection. Dev tasks close only with passing tests. | PASS |
| **IV. Surgical Agent Behavior via Injected Prompts** | The directive *content* (Operational Silence, Empirical Verification, Token-Optimized Review, Stop-and-Ask, Ledger & Phase Wiring) is preserved verbatim; only the *delivery vehicle* changes from marker injection to native hook `prompt` bodies, still centrally owned by SpecOps templates and updated on re-run. See evolution note. | PASS (with amendment follow-up) |
| **V. Domain Agnosticism** | `extensions.yml` + hooks are stack-neutral; no framework/language coupling. Client config stays in `specops.json`. | PASS |
| **VI. Exit Codes as Gates** | Every new lifecycle command returns 0 on success, 1 on blocking failure, non-interactive by default. | PASS |
| **Technical Constraints** | No new dependency (PyYAML already present). New modules live under `src/specops/`; template asset under `src/specops/templates/`. | PASS |
| **Development Workflow** | Not self-applied; plan verified manually; behavior validated via `tests/` fixtures only. | PASS |

**Constitution evolution note (non-blocking)**: Principle I and Principle IV currently *describe*
marker-delimited injection as the integration method. This feature introduces the native extension
mechanism as an additional, preferred delivery path while retaining the legacy injector (FR-015).
The intent of both principles (additive, never destructive) is strengthened, not violated. A
documentation-only constitution amendment (MINOR bump) SHOULD accompany the merge to record that
SpecOps delivers directives through the host's native extension mechanism, with marker injection as
the retained legacy path. This is tracked as a follow-up, not a gate failure, and is recorded in
Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/005-native-speckit-extension/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── cli-extension.md         # `specops extension …` command contract
│   └── extensions-manifest.md   # `.specify/extensions.yml` schema + registration contract
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

All paths below are declared with SpecOps action suffixes and verified against the current
worktree (Principle IV, Empirical Verification).

```text
src/specops/
├── extension.py             (create)   # native extensions.yml engine + command registration + idempotency
├── migration.py             (create)   # state detection (absent|native|legacy), backup/restore, marker strip, migrate
├── compat.py                (create)   # CLI ↔ extension version compatibility check (FR-016)
├── cli.py                   (modify)   # add `extension` Typer subgroup (install/update/disable/enable/remove/migrate/status)
├── speckit.py               (modify)   # extensions.yml path + per-integration command-dir resolution; native/legacy detection helpers
├── config.py                (modify)   # persist compatibility metadata (min_cli_version) in specops.json defaults/merge
├── initializer.py           (reuse)    # reuse remove_block()/_scan_markers() for legacy marker stripping (no behavior change)
└── templates/
    └── extensions.yml       (create)   # hook-manifest template; prompt bodies reference existing directives/*.md

tests/
├── unit/
│   ├── test_extension.py    (create)   # manifest build/write/update/remove, semantic-equivalence idempotency, atomic write
│   ├── test_migration.py    (create)   # detection matrix, backup+restore on failure, marker strip preserves surrounding text
│   └── test_compat.py       (create)   # CLI present/absent/incompatible → refuse & leave unchanged
└── integration/
    └── test_extension_lifecycle.py (create)  # install→update→disable→enable→remove/purge→migrate; idempotency; interruption-safety; offline

pyproject.toml               (modify)   # version bump; confirm extensions.yml template is packaged
CHANGELOG.md                 (modify)   # user-visible behavior + migration notes
README.md                    (modify)   # native install/migration docs (English)
README.pt-br.md              (modify)   # behaviorally equivalent Portuguese docs
```

**Structure Decision**: Single-package layout, matching the existing `src/specops/` module
convention. The native path is delivered by three new cohesive modules (`extension`, `migration`,
`compat`) rather than overloading `initializer.py`, keeping the legacy injector isolated and
independently testable (FR-015). The CLI grows a `specops extension` subgroup that mirrors the
existing `status` subgroup pattern. `specops init` is left untouched as the legacy path.

## Complexity Tracking

| Item | Why needed | Simpler alternative rejected because |
|------|------------|--------------------------------------|
| New `extension.py`/`migration.py`/`compat.py` modules (vs. extending `initializer.py`) | The legacy injector must remain available and independently testable (FR-015); mixing native + legacy in one module would couple two lifecycles and risk regressions in the retained path. | Extending `initializer.py` would entangle the marker path with the native path and make the "legacy unchanged" guarantee hard to prove. |
| Constitution amendment follow-up (Principle I/IV wording) | The delivery mechanism evolves from marker injection to native hooks; the constitution's descriptive text should reflect that once merged. | Silently diverging from the constitution text would violate the governance rule that principles and practice stay in sync. Deferred (not a gate failure) because the *intent* is unchanged and the amendment is documentation-only. |
