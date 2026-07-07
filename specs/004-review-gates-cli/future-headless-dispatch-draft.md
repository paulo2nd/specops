# Contract Draft — `specops review` (headless review pipeline)

**Status**: DRAFT for validation — pre-`/speckit.specify`
**Date**: 2026-07-06

## Purpose

Move the deterministic gates of `/specops-review` (template steps 2–4) into the
CLI, and add optional headless dispatch of the surgical AI review (step 5) to
the client's agent CLI. The verdict and the ledger transition become CLI-owned:
the agent reports findings; the tooling decides and records.

Route B (own minimal dispatch): no runtime dependency on the `specify` binary,
no mutation of Speckit-owned state. Speckit-workflow integration is delivered
as documentation (a `shell` step example), not code.

## Command surface

```
specops review [OPTIONS]

Options:
  --gates-only          Run deterministic gates only; skip dispatch and ledger
                        transition. Safe in any phase (CI-friendly).
  --no-transition       Full review (gates + AI dispatch + verdict) but do not
                        mutate the ledger. For dry runs and PR CI.
  --agent-cmd TEXT      Override the agent command template for this run.
  --timeout INTEGER     Agent dispatch timeout in seconds [default: from config].
```

## Preconditions

| Check | Applies to | Failure |
|---|---|---|
| `specops.json` present and parseable | always | `ConfigError`, exit 1 |
| Ledger present and parseable | full review | `LedgerParseError`, exit 2 |
| `current_phase == REVIEW` | full review (not `--gates-only`) | `SpecopsError`, exit 1 |

## Pipeline — reject cheapest first

Same order as today's template; each gate stops the run on failure.

| # | Gate | Implementation | On failure |
|---|---|---|---|
| 1 | Reconcile | `reconcile.run(root)` (in-process, not subprocess) | REJECTED, report violations, exit 1 |
| 2 | Lint | `lint_command` from config (skipped if empty) | REJECTED, report exit code + tail of output, exit 1 |
| 3 | Test | `test_command` from config | REJECTED, report exit code + tail of output, exit 1 |
| 4 | Working tree | `git status --porcelain` non-empty → dirty; no effective diff vs baseline (existing `gitops` semantics) → nothing to review | REJECTED, exit 1 |

`--gates-only` ends here: exit 0 with `GATES PASSED`. Gate failures never
touch the ledger (a gate rejection is not a review verdict; the review cycle
stays open).

## Agent dispatch (full review only)

**Command resolution order:**

1. `--agent-cmd` flag
2. `review_agent_command` in `specops.json`
3. Auto-detect: read `.specify/integration.json` → `integration` key →
   `<key> -p "{prompt}"` (the same default convention Speckit uses for its
   Markdown/TOML/Skills families)

**Template placeholders:** `{prompt}` (required). The command is parsed with
`shlex`, never `shell=True`.

**Env overrides** (mirror Speckit's naming convention):

- `SPECOPS_REVIEW_EXECUTABLE` — replace the binary
- `SPECOPS_REVIEW_EXTRA_ARGS` — extra flags appended (shlex-parsed), e.g.
  permissions-skipping flags for CI

**Execution:** `subprocess.run` with captured output and timeout
(`review_timeout_seconds`, default 600). Working dir = repo root.

**Failure semantics:** executable not found, timeout, or non-zero agent exit →
`DispatchError`, exit 3. Never mutates the ledger.

**Prompt content** (built by the CLI, self-contained — the dispatched agent
does NOT need the `/specops-review` command installed):

- The changed-file list from the effective diff (paths only; the agent reads
  the files itself — preserves the surgical-read property).
- Paths to spec, plan, constitution, and `skills_dir`.
- The exact revision file path to write (see below) and its format contract.
- Explicit instruction: do NOT run `specops status transition-phase` — the
  CLI owns the verdict.

## Verdict file contract

The CLI computes `revisions/revision-N.md` (N = max existing + 1) **before**
dispatch and reads exactly that path after the agent exits.

Format (tightened vs today's template):

- **First non-empty line MUST be exactly `APPROVED` or `REJECTED`.**
- If REJECTED: one finding per line, `[File]:[Line] - [rule violated and short action]`.
- Optional trailing `## Skill Suggestions` section (active learning, unchanged).

Missing file, or a first line that is neither verdict → `DispatchError`,
exit 3, no ledger mutation.

## Ledger transition (unless `--gates-only` / `--no-transition`)

- `APPROVED` → `transition_phase("DONE", result="APPROVED")`
- `REJECTED` → `transition_phase("IMPLEMENT", result="REJECTED")`
- The closing review cycle additionally records `revision:
  <relative path to revision-N.md>` (new optional field in `review_cycles`
  entries — auditability: verdict traceable to its report).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | APPROVED (full) / gates passed (`--gates-only`) |
| 1 | REJECTED (by gate or by verdict); also config/precondition errors (existing `SpecopsError` mapping) |
| 2 | Ledger parse error (existing) |
| 3 | **New** — `DispatchError`: review could not run (agent CLI missing, timeout, agent crashed, verdict file invalid). Distinct from rejection so CI can tell "code is bad" from "infra is broken". |

`DispatchError(SpecopsError, exit_code=3)` joins the hierarchy in
`errors.py`; raising rules and the single CLI-boundary mapper from
`contracts/errors.md` (002) apply unchanged.

## Config additions (`specops.json` `_DEFAULTS`)

```json
{
  "review_agent_command": "",
  "review_timeout_seconds": 600
}
```

`""` = auto-detect. Existing repos pick these up via `merge_preserve` on the
next `specops init` re-run; `load()` also falls back to defaults when keys are
absent (no forced re-init).

## Template changes (`templates/review.md`)

- Steps 2–4 collapse to: “Run `specops review --gates-only`. Non-zero exit →
  REJECTED, report its output, stop.”
- Step 6 adopts the verdict-first-line format (shared contract with the CLI).
- Interactive `/specops-review` keeps agent-driven transition (unchanged
  behavior for in-session use).

## Documentation deliverable

README section showing `specops review` as an automated gate inside a Speckit
workflow — user-owned YAML, zero specops code:

```yaml
- id: review
  type: shell
  run: specops review
  on_fail: abort
```

## Non-goals

- No integration with / dependency on the Speckit workflow engine or the
  `specify` binary.
- No per-agent flag matrix beyond the default `-p` convention + overrides
  (escape hatch covers exotic agents).
- No parsing of agent stdout — the revision file is the single source of truth.
- No change to interactive `/specops-review` semantics beyond gate collapsing
  and verdict format.

## Open questions

1. **Exit code 3** extends the {1,2} vocabulary frozen in 002 — acceptable?
2. **`--no-transition`** worth keeping in v1, or is `--gates-only` enough for CI?
3. Should a gate rejection also be recorded in the ledger (e.g. a
   `gate_failures` counter), or stay ephemeral as proposed?
4. Interactive `/specops-review`: keep agent-driven verdict (proposed), or
   also route it through `specops review` end-to-end?
