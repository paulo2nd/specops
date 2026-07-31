# SpecOps CLI

[![CI](https://github.com/paulo2nd/specops/actions/workflows/ci.yml/badge.svg)](https://github.com/paulo2nd/specops/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/speckit-specops.svg)](https://pypi.org/project/speckit-specops/)
[![Python](https://img.shields.io/pypi/pyversions/speckit-specops.svg)](https://pypi.org/project/speckit-specops/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Read this in: **English** | [Português (BR)](README.pt-br.md)

**SpecOps turns [GitHub Spec Kit](https://github.com/github/spec-kit)'s
spec-driven workflow into an enforced, auditable process.** It layers an
agent-guided *atomic development* methodology on top of any Speckit repository —
a physical state ledger, typed evidence with machine collection, and
token-optimized review —
**without replacing or forking a single Speckit file.**

> Speckit gives your agents great artifacts (spec → plan → tasks → implement).
> SpecOps makes sure they actually follow them: state is on disk and
> Git-verifiable, evidence is collected by tooling instead of claimed by the
> agent, and review rejects as cheaply as possible.

## Why SpecOps?

Spec-driven development with AI agents has three recurring failure modes.
SpecOps addresses each one:

| Problem | Without SpecOps | With SpecOps |
|---|---|---|
| **Agents hallucinate progress** | "Done ✅" with no proof | Every task closes with typed evidence; `--auto` attaches test output, commit hashes, and diffs at the commit boundary |
| **State lives in the chat** | Lost on context reset; not auditable | State is a physical `status.yaml` ledger, Git-verifiable and recovery-safe |
| **Reviews are slow and expensive** | Agent reads the whole repo | `/specops-review` rejects cheapest-first (reconcile → gate profiles (lint/test by default) → working tree/effective diff → drift) before reading any code |

## What it adds to Speckit

- **📒 Physical state ledger (Repo-as-State).** A versioned, structured
  `status.yaml` tracks phase, tasks, evidence, and review cycles. Mutated only
  through `specops` commands — never hand-edited, never held in agent memory.
  State changes are atomic and interruption-safe, guarded by optimistic
  concurrency (a monotonic `revision`) and a workspace-identity check
  (feature / branch / baseline); older ledgers migrate losslessly with a backup.
- **🔬 Automated evidence collection.** `complete-task --auto` runs your test
  command, harvests commits and diffs, and records them as typed evidence. A
  task cannot be `DONE` without proof.
- **🔁 A phase state machine wired into the prompts.** `specops init` injects
  directives into the specify, plan, tasks, and implement prompts so the ledger
  is created and phases advance automatically — the human never runs the
  bookkeeping by hand.
- **✂️ Token-optimized surgical review.** The installed `/specops-review`
  command reviews only effective-diff files and stops at the first cheap rejection.
- **📐 Empirical verification & gates.** `specops consistency` and
  `specops reconcile` are exit-code gates you can drop into CI or agent prompts.
- **➕ Additive and reversible.** Everything is delivered through
  marker-delimited blocks. Removing those blocks restores the affected Speckit
  files byte-for-byte.

## Install

```bash
pip install speckit-specops
```

Installs the `specops` command. Requires Python ≥ 3.10 and Git ≥ 2.30. No
network I/O after install.

## Quick Start

```bash
# In a Speckit-initialized repository:
specops init          # inject directives, install /specops-review, create specops.json
```

That's it. From here you drive Speckit as usual (`/speckit.specify`,
`/speckit.plan`, `/speckit.tasks`, `/speckit.implement`) and the injected
directives take care of the ledger and phase transitions. Check state anytime:

```bash
specops status show
```

## How it works

SpecOps rides the Speckit lifecycle. Once `specops init` has run, the injected
directives drive the ledger at each stage seam:

| Speckit stage | What SpecOps does |
|---|---|
| **specify** | Marks the repo as SpecOps-managed (informational; no ledger yet) |
| **plan** | Enforces empirical path verification and the `consistency` gate |
| **tasks** | Creates the ledger (`status init-spec`), advances the phase to `TASKS`, and requires `[SC-xxx]` coverage tags on every task |
| **implement** | Opens `IMPLEMENT`, resolves the context map's minimal read set and scopes reads to it (guidance, never a gate; no-op without a map), runs the evidence-backed ledger loop, then opens `REVIEW` |
| **review** | `/specops-review` validates the diff and records `APPROVED` / `REJECTED` |

The phase machine is `SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE`.
If SpecOps is not installed, the Speckit prompts still work standalone — the
directives degrade to no-ops.

## Commands at a glance

| Command | What it does |
|---|---|
| `specops init` | Prepare a Speckit repo: inject directives, install `/specops-review`, create `specops.json` |
| `specops extension …` | Native Spec Kit extension lifecycle, plus the `specops` and `specops-lite` workflows |
| `specops status …` | Drive the ledger: `show`, `init-spec`, `start-task`, `complete-task`, `transition-phase`, `record-step`, `migrate`, `rebaseline` |
| `specops preflight` | Deterministic review gate, cheapest-first — CI-safe (formerly `specops review`) |
| `specops reconcile` | Read-only gate: every recorded commit reachable, every `DONE` task evidenced |
| `specops consistency` | Read-only gate: SC coverage tags + plan path action suffixes |
| `specops doctor` | Read-only health diagnostic across every SpecOps surface |
| `specops report` | Compact, stable machine surface for the active feature's status |
| `specops context …` | Context map: ownership, phase read sets, impact, staleness |
| `specops trace …` | End-to-end traceability; classify and acknowledge effective-diff drift |
| `specops gate …` | Gate-profile suite and structured-evidence inspection |
| `specops handoff …` | Structured corrective handoffs; import external findings (JSON/SARIF) |
| `specops lane …` | Lightweight lane for small, reversible changes |

The full reference — flags, exit codes, JSON contracts, examples, and the
review workflow — lives in **[docs/commands.md](docs/commands.md)**.

### Stability & contract freeze

Building automation on SpecOps? **[docs/stability.md](docs/stability.md)** is the contract
freeze for 1.0: it classifies every adopter-facing surface — `specops.json`, `status.yaml`,
`lane.yaml`, gate-profile files, the `--json` output envelope, exit codes, the findings-input
contract, the context-map file, and SARIF output — as **frozen**, and states the
additive-vs-breaking rule and the post-1.0 versioning/migration obligations for each. Every
`--json` output carries an `output_version` so you can detect envelope changes.

## How SpecOps behaves: a paved road you can leave — on the record

SpecOps is neither a rigid gate that blocks you nor a suggestion you can ignore.
It presents a **correct path** and lets you **deviate — as long as the deviation is
recorded**. What it blocks is *silent* deviation, not deviation itself:

- A path you changed that the plan didn't predict isn't rejected — you
  **acknowledge** it with a reason (`specops trace acknowledge`).
- A review finding that turns out to be a false positive isn't a dead-end — you
  **dismiss** it with a reason (`specops handoff finding dismiss`).
- A gate that was skipped is **recorded** as a finding, never silently passed.

SpecOps **records** the deviation and its reason; it does **not** judge whether the
reason is good — that is the team's call, not the tool's. (A small core of
safety-critical gates — persisted-schema changes, secrets, public-contract breaks,
destructive actions — is *not* pierceable; there SpecOps halts and asks a human.)

## Configuration — `specops.json`

| Key | Purpose | Default |
|---|---|---|
| `test_command` | Command run by `complete-task --auto` | `pytest` |
| `lint_command` | Lint gate run by `specops preflight` (empty = skipped) | `""` |
| `skills_dir` | Directory the review prompt loads skills from | `.specify/skills` |

Unknown keys are preserved on re-init.

## Language policy

All SpecOps operational output (CLI messages, injected assets) is in English.
Your prose (`spec.md`, `plan.md`, task descriptions) may be in **any language** —
SpecOps parses only structural tokens (`SC-\d+`, `T\d+`, action suffixes), never
content.

## Supported Speckit layouts

SpecOps resolves prompt targets at runtime from
`.specify/integrations/<agent>.manifest.json`. Any Speckit integration with a
recorded manifest is supported; unknown layouts fail closed. Tested with
Speckit ≥ 0.12 (Claude skills mode, separator `-`).

## Uninstall

Remove the appended block from each prompt file, then delete `specops.json` and
the installed review command. No other files are written; the restore is
byte-identical.

## Contributing

Contributions are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md) for dev setup,
the quality gates, and project principles. SpecOps is at `0.x`; the CLI surface
and ledger format may still change before `1.0` (see [CHANGELOG.md](CHANGELOG.md)).

## License

[MIT](LICENSE) © Paulo Segundo
