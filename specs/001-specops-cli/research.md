# Research & Decisions: SpecOps CLI

**Date**: 2026-07-05 | **Plan**: [plan.md](plan.md)

All decisions below were grounded empirically against this repository's real Speckit
installation (`.specify/`, `.claude/skills/speckit-*/SKILL.md`, task template) and the
vendored reference implementation in `.specs/reference/`. Checklist references point
to `checklists/pre-plan.md`.

## R1. Speckit detection criteria (CHK001)

- **Decision**: A repository "has Speckit" when `.specify/` exists at the repo root
  and contains `templates/`. Feature resolution reads `.specify/feature.json >
  feature_directory` (fallback: newest `specs/NNN-*` directory). Missing `.specify/`
  aborts init with guidance to run Speckit's initialization first.
- **Rationale**: Verified in this repo: `.specify/{templates,memory,scripts}` and
  `feature.json` are what Speckit's init produces; `feature.json` is Speckit's own
  pointer used by downstream commands.
- **Alternatives considered**: Detecting via `.claude/skills/speckit-*` only —
  rejected: that is integration-specific (see R2), while `.specify/` is
  integration-neutral.

## R2. Target prompt files for injection (CHK002, CHK004) — REVISED after Speckit source validation

- **Decision**: Prompt-target resolution is **manifest-driven, never hardcoded**.
  Speckit generates prompts in agent-specific folders (40+ integrations in
  `specify_cli/integrations/`: Claude skills mode `.claude/skills/speckit-plan/
  SKILL.md` with separator `-`; classic default `<folder>/commands/speckit.plan.md`
  with separator `.`; Copilot `.github/prompts/*.prompt.md`; etc.), and records
  every installed file per integration in
  `.specify/integrations/<agent>.manifest.json > files` (verified in Speckit 0.12.4
  source: `integrations/manifest.py`, `integrations/base.py`). Resolution algorithm:
  1. Read `.specify/integration.json > installed_integrations` (a LIST — multiple
     agents may coexist) and `integration_settings.<agent>.invoke_separator`.
  2. For each installed integration, read its manifest and select the entries whose
     path contains the `speckit{sep}plan` / `speckit{sep}implement` stem (matching
     both separator conventions and wrapper conventions like `speckit-plan/SKILL.md`
     or `speckit.plan.prompt.md`).
  3. Inject the two blocks into the located files of EVERY installed integration.
  4. Fail closed (exit 1, zero writes) when: an integration lacks a manifest, a
     manifest lacks a plan/implement entry, or a listed file is missing on disk.
- **Review-command install**: derived per integration by pattern substitution on the
  located plan-prompt path (`speckit{sep}plan` → `specops{sep}review`, preserving the
  wrapper convention — e.g. `.claude/skills/specops-review/SKILL.md` here, with the
  YAML frontmatter skills mode requires). Command name = `specops` +
  `invoke_separator` + `review` → `/specops-review` in this repository. This
  supersedes the earlier `.claude/commands/specops.review.md` assumption and closes
  analysis finding A1 without a fallback.
- **Upgrade interaction**: injected blocks make Speckit's manifest hashes stale —
  Speckit's uninstall preserves modified files (verified in `manifest.py`), and a
  Speckit upgrade may rewrite prompts, removing blocks; re-running `specops init`
  re-injects (spec edge case already covers this).
- **Rationale**: the manifest is Speckit's own record of where it put its prompts;
  resolving from it supports every agent Speckit supports, present and future,
  without SpecOps maintaining a layout table.
- **Alternatives considered**: hardcoded per-agent table (original decision) —
  rejected: breaks for any of the 40+ layouts not encoded and drifts on Speckit
  releases; injecting into `.specify/templates/*` — rejected: artifact templates,
  not agent prompts.

## R3. Directive block marker grammar (CHK003, CHK005, SC-010)

- **Decision**: HTML comment markers, one block per concern, appended at the end of
  the target file:
  `<!-- SPECOPS:BEGIN <block-id> v<version> -->` … `<!-- SPECOPS:END <block-id> -->`.
  Re-init replaces content strictly between matching markers. Corrupted markers
  (BEGIN without END, duplicated BEGIN, nested) → exit 1 with the file and line, no
  write performed. Deleting the appended block lines restores the file byte-identical
  because injection never touches any pre-existing byte.
- **Rationale**: HTML comments are invisible in rendered Markdown, survive Markdown
  tooling, and end-of-file appending is the only position that guarantees the
  byte-identical restore required by SC-010 even after Speckit upgrades rewrite the
  file body.
- **Alternatives considered**: In-place insertion near relevant sections — rejected:
  anchor drift across Speckit versions breaks idempotency and the restore guarantee.

## R4. Ledger location and schema (CHK011)

- **Decision**: `<feature_directory>/status.yaml` (e.g., `specs/001-x/status.yaml`),
  feature directory resolved per R1. Schema adapted from the reference
  `status-template.yaml`: uppercase lifecycle phases `SPECIFY | PLAN | TASKS |
  IMPLEMENT | REVIEW | DONE`, `tasks[]` items `{id, status
  (PENDING|IN_PROGRESS|DONE), started_commit, commits[], evidence, completed_at}`,
  `recovery {active_task, last_commit, blockers[]}`, `review_cycles[] {round,
  started_at, completed_at, result (APPROVED|REJECTED|null)}`, plus `feature`,
  `branch`, `baseline`, `created_at`, `updated_at`. Full schema:
  [contracts/ledger-schema.md](contracts/ledger-schema.md).
- **Rationale**: Keeps the reference engine's proven shape while mapping phases to
  the Speckit lifecycle (spec clarification) and adding `started_commit`/`commits[]`
  for R7.
- **Alternatives considered**: Parallel `.specify/specs/<name>/` tree — rejected in
  spec clarification session (ledger lives with the feature's Speckit artifacts).

## R5. Task ID extraction and sync (CHK012 resolution, CHK013, CHK014)

- **Decision**: Parse `tasks.md` checklist lines with
  `^\s*-\s*\[[ xX]\]\s*(T\d+)\b` (format `- [ ] T001 …`, verified in the Speckit
  tasks template). Sync on every ledger command: new IDs enter as PENDING; a ledger
  task whose ID vanished from `tasks.md` is kept but flagged `orphaned: true`
  (reconcile reports it; nothing is silently deleted — DONE history is preserved).
  `start-task` while another task is IN_PROGRESS → exit 1 (finish or handle the
  active one first; single active task is what makes `recovery.active_task`
  meaningful).
- **Rationale**: Speckit's checkbox is presentation; the ledger is the status
  authority (spec clarification). Refusing concurrent IN_PROGRESS preserves the
  recovery-point semantics the methodology depends on.
- **Alternatives considered**: Deleting orphaned ledger tasks on sync — rejected:
  destroys evidence history; flag-and-report is auditable.

## R6. Success-criterion coverage tags (FR-012)

- **Decision**: Criterion IDs are parsed from the spec's Success Criteria section
  (`- **SC-\d+**:` bullets, Speckit's own format). Tasks declare coverage with a
  bracketed label on the task line — `- [ ] T012 [SC-001,SC-004] Description…` —
  same label style Speckit already uses for `[P]`/`[US1]`. `consistency` fails
  naming any SC with zero covering tasks and any `SC-xxx` reference that does not
  exist in the spec. No token matching, no stopwords (FR-014a).
- **Rationale**: Deterministic, language-independent, and syntactically native to
  Speckit task lines; the injected plan directive instructs agents to emit the tags.
- **Alternatives considered**: Statistical token overlap — rejected by stakeholder
  decision (fuzzy, unexplainable failures); separate coverage map file — rejected:
  second source of truth to drift.

## R7. Evidence for multi-commit tasks (CHK017, CHK018, CHK019)

- **Decision**: `start-task` records `started_commit = HEAD`. `complete-task --auto`
  runs `test_command`, then harvests `git log started_commit..HEAD` — all commit
  hashes into `commits[]` (first also mirrored to `recovery.last_commit`) and the
  combined name-only diff for the `CODE_DIFF` summary. Evidence classes are fixed:
  `CLI_LOG`, `TEST_REPORT`, `SCREENSHOT_PATH`, `CODE_DIFF` (methodology §7). Auto
  evidence: `TEST_REPORT:<one-line test outcome>; CODE_DIFF:<N files across M
  commits: f1, f2…>`. Unusable test output → `TEST_REPORT:exit 0 (output not
  parseable)` — the exit code, not the text, is the gate. Empty commit range → exit
  1 ("no commits since task start").
- **Rationale**: `started_commit..HEAD` is exact for the single-active-task model
  from R5; the reference script's HEAD-only harvest loses commits.
- **Alternatives considered**: One-commit-per-task enforcement — rejected: the
  methodology prefers it but reality (fixups) shouldn't corrupt evidence.

## R8. Phase machine and corrective rounds (CHK015 resolution, CHK016)

- **Decision**: Ordered transitions SPECIFY→PLAN→TASKS→IMPLEMENT→REVIEW→DONE with
  the single exception REVIEW→IMPLEMENT requiring `-r REJECTED`; it appends a new
  `review_cycles[]` entry with an incremented round. `-r/--result` accepts
  `APPROVED | REJECTED | <free-form note>`; DONE requires the latest review cycle
  result APPROVED. Unknown phase or invalid jump → exit 1, ledger untouched.
- **Rationale**: Direct encoding of spec FR-008b and the reference `transitions.json`
  round model.
- **Alternatives considered**: Free-order transitions — rejected in clarification
  session (anti-hallucination mission).

## R9. Exit-code semantics (CHK027)

- **Decision**: `0` success; `1` blocking validation failure (the gate contract);
  `2` unexpected execution error (crash, unreadable/corrupt file — includes corrupt
  ledger YAML per CHK020). Typer's usage errors remain exit 2.
- **Rationale**: Gates must distinguish "checked and failed" from "could not check";
  CI treats both as failure but humans debug them differently.
- **Alternatives considered**: Uniform 1 — rejected: masks tooling bugs as
  legitimate rejections.

## R10. Init re-run with existing user config (CHK007, CHK009)

- **Decision**: `specops.json` merge-preserving: existing keys keep user values,
  missing keys are added with template defaults, unknown user keys are kept. Packaged
  assets install verbatim (byte-for-byte from package data); the only permitted
  install-time substitution is placeholder fill in the ledger scaffold when
  `status init-spec` instantiates it (`{{feature-name}}`, dates, baseline) — asset
  files themselves are never generated from external sources (FR-017).
- **Rationale**: Re-init must be safe on customized repos (SC-005); verbatim assets
  keep FR-017 verifiable.
- **Alternatives considered**: Overwriting config with a `.bak` — rejected: silent
  churn on every re-init.

## R11. Scope boundaries confirmed (CHK010, CHK026, CHK028, CHK029, CHK030)

- **Decision**: (a) Uninstall command: out of scope v1 — blocks are hand-removable
  by design (R3); documented in README. (b) Review with empty diff: the review
  prompt directs immediate rejection "no effective diff". (c) Commits recorded as
  `(human)` are exempt from reconciliation history checks (reference behavior kept).
  (d) Supported Speckit layout: the Claude skills layout of Speckit ≥0.12 as
  installed here; unknown layouts fail closed per R2. (e) Offline applies to ALL
  commands, not only init — nothing in the package performs network I/O.
- **Rationale**: Keeps v1 shippable; every deferral fails closed rather than
  guessing.
- **Alternatives considered**: Auto-uninstall — deferred until marker blocks prove
  stable in the field.

## R12. Existing `cli.py` skeleton

- **Decision**: Keep the Typer app/subcommand structure; translate all strings to
  English (FR-014), remove `rich` (constitution — plain `typer.echo`), add missing
  commands (`status init-spec`, `status transition-phase`) and `--evidence` /
  `--non-interactive` options per the CLI contract.
- **Rationale**: Verified the skeleton already matches the intended command tree;
  rewriting it wholesale would discard working scaffolding.
- **Alternatives considered**: argparse port of the reference scripts — rejected:
  `objective.md` mandates Typer and the skeleton exists.
