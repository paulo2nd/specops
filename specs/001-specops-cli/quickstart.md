# Quickstart Validation: SpecOps CLI

**Plan**: [plan.md](plan.md) | **Contracts**: [contracts/](contracts/)

End-to-end scenarios proving the feature works. Run from a clean shell; every step
lists its expected outcome. Details of flags and exit codes:
[contracts/cli-contract.md](contracts/cli-contract.md).

## Prerequisites

- Python ≥ 3.10, Git ≥ 2.30, no network required after install
- `pip install -e .` from the repo root → `specops --help` lists
  `init`, `status`, `reconcile`, `consistency` (all output in English)

## Scenario A — Initialization (US1)

```bash
# Sandbox with a fake Speckit (Claude skills) layout, including Speckit's
# integration records that drive prompt-target resolution (R2)
mkdir -p /tmp/sandbox/.specify/templates /tmp/sandbox/.specify/integrations \
         /tmp/sandbox/.claude/skills/speckit-plan \
         /tmp/sandbox/.claude/skills/speckit-implement
printf '# plan prompt\n' > /tmp/sandbox/.claude/skills/speckit-plan/SKILL.md
printf '# implement prompt\n' > /tmp/sandbox/.claude/skills/speckit-implement/SKILL.md
cat > /tmp/sandbox/.specify/integration.json <<'EOF'
{"installed_integrations": ["claude"],
 "integration_settings": {"claude": {"invoke_separator": "-"}}}
EOF
cat > /tmp/sandbox/.specify/integrations/claude.manifest.json <<'EOF'
{"integration": "claude", "files": {
  ".claude/skills/speckit-plan/SKILL.md": "-",
  ".claude/skills/speckit-implement/SKILL.md": "-"}}
EOF
cd /tmp/sandbox
cp .claude/skills/speckit-plan/SKILL.md .claude/skills/speckit-plan/SKILL.md.orig
cp .claude/skills/speckit-implement/SKILL.md .claude/skills/speckit-implement/SKILL.md.orig
```

1. `specops init --non-interactive` (no git yet) → **exit 1**, English error, < 1 s.
2. `git init && specops init` → **exit 0**; creates `specops.json`; installs
   `.claude/skills/specops-review/SKILL.md` (path derived from the manifest's plan
   prompt; command `/specops-review` per the `-` separator); both SKILL.md files end
   with `<!-- SPECOPS:BEGIN … -->` blocks; bytes before the blocks unchanged.
3. Re-run `specops init` → **exit 0**, no duplicated blocks (SC-005).
4. Remove exactly the appended region (block + its single blank separator line):

   ```bash
   python3 -c "import re,sys,pathlib; p=pathlib.Path(sys.argv[1]); \
     p.write_text(re.sub(r'\n<!-- SPECOPS:BEGIN .*?SPECOPS:END [a-z]+ -->\n', '', p.read_text(), flags=re.S))" \
     .claude/skills/speckit-plan/SKILL.md
   diff .claude/skills/speckit-plan/SKILL.md .claude/skills/speckit-plan/SKILL.md.orig  # → identical
   ```

   (repeat for the implement prompt) → **byte-identical** (SC-010).
5. Disable network (e.g., `sudo ifconfig en0 down` or offline container) and repeat
   step 2 in a fresh sandbox → same results (SC-009).
6. Remove `.specify/integrations/claude.manifest.json` and re-run `specops init` →
   **exit 1** naming the missing manifest, zero files written (fail-closed, R2).

## Scenario B — Ledger loop (US2)

Prereq: sandbox from A with a feature dir `specs/001-demo/`, `tasks.md` containing
`- [ ] T001 …` / `- [ ] T002 …` lines, `.specify/feature.json` pointing to it, and
`specops.json > test_command` set to a passing command (e.g., `true`).

1. `specops status init-spec 001-demo` → creates `specs/001-demo/status.yaml`;
   T001/T002 PENDING.
2. `specops status start-task T001` → IN_PROGRESS, `recovery.active_task: T001`.
3. `specops status start-task T002` → **exit 1** (another task active).
4. Commit any change, then `specops status complete-task T001 --auto` → DONE with
   `TEST_REPORT:…; CODE_DIFF:…` evidence and harvested commit hashes.
5. Set `test_command` to `false`, start T002, commit, `complete-task T002 --auto` →
   **exit 1**, T002 stays IN_PROGRESS (FR-009).
6. `specops status complete-task T002 --evidence "CLI_LOG:manual check ok"` →
   **exit 0** (FR-009a); without `--evidence` → **exit 1**.

## Scenario C — Reconcile gate (US3)

1. After B: `specops reconcile` → **exit 0**, `reconcile: ok`.
2. Edit `status.yaml` by hand, replacing a `commits[]` hash with `deadbeef0000…` →
   `specops reconcile` → **exit 1**, names T001 and the missing hash (SC-003).

## Scenario D — Consistency gate (US4)

Prereq: `spec.md` with `- **SC-001**: …` / `- **SC-002**: …` and a `plan.md`
declaring paths with suffixes.

1. Tasks tagged `[SC-001]` and `[SC-002]` → `specops consistency` → **exit 0**.
2. Remove the `[SC-002]` tag → **exit 1**, names SC-002 as uncovered.
3. Declare `src/ghost.py (modify)` in plan.md with no such file → **exit 1**, names
   the path (FR-012).

## Scenario E — Phase machine

1. `specops status transition-phase PLAN` from SPECIFY → **exit 0**.
2. `specops status transition-phase REVIEW` from PLAN → **exit 1** (skip).
3. Walk to REVIEW, then `transition-phase IMPLEMENT -r REJECTED` → **exit 0**,
   `review_cycles` gains round 2 (corrective loop).
4. `transition-phase DONE` with latest cycle not APPROVED → **exit 1**.

## Scenario F — Review command (US5, agent-side)

In a prepared repo, invoke `/specops.review` in the agent: with a seeded ledger
divergence it aborts before reading any code; with an out-of-plan changed file it
rejects from `git status --porcelain` alone; with a compliant diff it writes
`revisions/revision-1.md` using the `[File]:[Line] - …` format (SC-004).

## Automated equivalent

`pytest tests/integration/` covers A–E with temporary Git repos and the fake Speckit
layout fixture; Scenario F is validated manually (agent-in-the-loop).
