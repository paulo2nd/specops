# Contract: `.specify/extensions.yml` manifest & registration

`.specify/extensions.yml` is the host's native extension registry. It is **read** by every Spec Kit
skill (`speckit-*`) and **authored/owned** by SpecOps. Writing it does not modify a host-owned file.

## Shape (SpecOps-authored region)

```yaml
# .specify/extensions.yml  (SpecOps-owned entries; other extensions' entries preserved untouched)
hooks:
  after_specify:
    - extension: specops
      command: specops-specify-directive      # or inline prompt-only entry
      enabled: true
      optional: true
      description: "SpecOps specification directives"
      prompt: |
        <contents of src/specops/templates/directives/specify.md>
  before_plan:
    - extension: specops
      enabled: true
      optional: false
      description: "SpecOps planning directives (consistency gate)"
      prompt: |
        <contents of directives/plan.md>
  after_tasks:
    - extension: specops
      enabled: true
      optional: false
      description: "SpecOps task-generation directives (ledger creation seam)"
      prompt: |
        <contents of directives/tasks.md>
  after_implement:
    - extension: specops
      enabled: true
      optional: false
      description: "SpecOps implementation directives (review-cycle seam)"
      prompt: |
        <contents of directives/implement.md>

commands:
  - id: specops-review
    extension: specops
    integration: claude
    path: .claude/skills/specops-review/SKILL.md

specops:
  cli_compat:
    min_cli_version: "0.3.0"   # decided floor: first CLI release understanding this schema (research R7)
```

## Invariants

1. **Ownership isolation**: SpecOps reads/writes only entries where `extension: specops` (and the
   top-level `specops:` block). Entries owned by other extensions MUST be preserved verbatim
   across every lifecycle operation.
2. **Hook-point domain**: SpecOps hook points are exactly `after_specify`, `before_plan`,
   `after_tasks`, `after_implement` (research R1). No other seams are written.
3. **Prompt provenance**: each `prompt` body is sourced from the corresponding
   `src/specops/templates/directives/<stage>.md`; updates flow only from the templates
   (Principle IV — templates are the delivery vehicle).
4. **Semantic-equivalence idempotency**: two manifests are equal when their parsed SpecOps entries
   (hook points → set of `{extension, command|prompt-digest, enabled, optional}`), command
   registrations, and `cli_compat` match — regardless of key order, whitespace, or host-added
   timestamps (research R5, FR-005, SC-002).
5. **Command ownership**: every `commands[].path` is a SpecOps-owned file, absent from the host
   integration manifest's hashed `files` map. One command entry per installed integration (SC-006).
6. **Graceful absence**: when `.specify/extensions.yml` is missing, the host skills skip SpecOps
   hooks silently (already their documented behavior); SpecOps behavior degrades to no-op.

## Registration procedure (per installed integration)

1. Resolve integrations from `.specify/integration.json` → `installed_integrations` (reuse
   `speckit.resolve_prompt_targets`).
2. For each, derive the command path via `speckit.derive_review_path(plan_path, root, sep)`.
3. Install the review command file (SpecOps-owned) and record it under `commands:`.
4. Write the four hook entries once (integration-neutral) into `extensions.yml`.

## Legacy detection & migration boundary

- **Legacy signal**: `<!-- SPECOPS:BEGIN <id> v<n> -->` markers in host prompt files, parsed by
  `initializer._scan_markers` (existing, tested grammar).
- Migration removes only these marker blocks (via `initializer.remove_block`) after backing up the
  file, then writes the native manifest (research R3, R4).
