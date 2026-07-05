# Directive Block Contract

**Plan**: [../plan.md](../plan.md) | **Research**: [research.md R2/R3](../research.md)

## Marker grammar

```text
<!-- SPECOPS:BEGIN <block-id> v<version> -->
…block content (owned by SpecOps, replaced on re-init)…
<!-- SPECOPS:END <block-id> -->
```

- `block-id` ∈ `plan` | `implement`; `version` is an integer bumped when the packaged
  directive content changes.
- Blocks are **appended at the end** of the target file, separated by one blank line.
  Injection never modifies any pre-existing byte — deleting the appended lines
  restores the file byte-identical (SC-010).
- Re-init: content strictly between matching BEGIN/END is replaced; version updated.
- Corruption (BEGIN without END, duplicate BEGIN, nested markers): exit 1 naming
  file and line; **no file is written** (fail-closed, R3).

## Injection targets (manifest-driven, R2)

Targets are resolved at runtime from Speckit's own records — never hardcoded:

1. `.specify/integration.json > installed_integrations` (list; multiple agents may
   coexist) + `integration_settings.<agent>.invoke_separator`.
2. Per integration, `.specify/integrations/<agent>.manifest.json > files` entries
   matching the `speckit{sep}plan` / `speckit{sep}implement` stem (any wrapper
   convention: `speckit-plan/SKILL.md`, `speckit.plan.md`, `speckit.plan.prompt.md`).
3. Both blocks are injected into the located files of EVERY installed integration.
4. Fail closed (exit 1, zero writes): missing manifest, missing plan/implement entry,
   or listed file absent on disk.

Example (this repository — Claude skills mode, separator `-`):

| block-id | Resolved target |
|---|---|
| `plan` | `.claude/skills/speckit-plan/SKILL.md` |
| `implement` | `.claude/skills/speckit-implement/SKILL.md` |

## Block content requirements

Content ships as packaged assets (`templates/directives/*.md`, FR-017). Contractual
minimum per block:

### `plan` block (`directives/plan.md`)

1. **Empirical Verification (§17.4)**: no path/convention declared from memory;
   every declared path carries `(create)` / `(modify)` / `(remove)` (mixed forms
   allowed) and is verified against the worktree before being written.
2. **Coverage tags**: every generated task line carries `[SC-xxx[,SC-yyy]]` labels
   declaring the success criteria it covers (R6).
3. **Consistency gate**: run `specops consistency` before finishing; exit ≠0 blocks
   the handoff until plan/spec are corrected.
4. **Stop-and-ask** on ambiguous structure (two coexisting patterns, missing paths).

### `implement` block (`directives/implement.md`)

1. **Operational Silence (§6)**: no intra-task narration; between tasks exactly one
   line — `<task-id> done (<commit-sha7>), starting <next-task-id>` — then continue
   immediately.
2. **Ledger loop**: `specops status start-task <id>` before editing; commit work;
   `specops status complete-task <id> --auto` to close; never edit `status.yaml` or
   `tasks.md` checkboxes by hand.
3. **Preflight**: `specops reconcile` before the first task; divergence = stop and
   signal the human.
4. **Stop-and-Ask gates (§8.2)**: persisted schema changes, secrets/auth/crypto,
   public contract breaks, dependency add/remove/major-bump, root-cause ambiguity —
   halt and ask.

## Installed agent command (not a block)

The `review.md` asset installs as a whole file per integration, its path derived by
pattern substitution on the located plan-prompt path (`speckit{sep}plan` →
`specops{sep}review`, preserving the wrapper convention — here:
`.claude/skills/specops-review/SKILL.md`, wrapped with the YAML frontmatter skills
mode requires). Command name = `specops` + invoke separator + `review` (here:
`/specops-review`). SpecOps-owned: overwritten on re-init. Content contract in
[cli-contract.md](cli-contract.md).
