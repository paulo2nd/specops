# Research: Native Code Review in `/specops-review`

**Feature**: 028 | **Date**: 2026-09-29

## R1 — Native review command per Spec Kit integration

**Question**: Which Spec Kit integrations ship a native code-review command that the
**agent itself** can invoke mid-review, against the round's range?

**Method**: Official vendor docs and vendor repositories, fetched 2026-09-29. Integration
ids come from the installed `specify-cli` 1.0.13 (`specify_cli/integrations/`, 44
integrations). Anything not confirmed from a primary source is treated as none.

**Inclusion rule for the built-in map**. All three must hold:

1. **Built-in**: shipped with the tool, not an optional extension.
2. **Agent-invocable in-session**: a tool or skill the model calls. Excluded are
   slash commands only a user can type, UI buttons, and shelling out to a second
   process of the same CLI, which needs shell permission and network access and costs
   a second model session.
3. **Targetable to the round's range**: it can review `<from>..<head>` as printed by
   `specops handoff record-scope`. A reviewer that only sees "uncommitted" or "since
   main" would review the wrong diff, which is a new silent failure.

| Integration | Native reviewer found | 1 | 2 | 3 | In map | Source |
|---|---|---|---|---|---|---|
| claude | `/code-review` (bundled skill; `/review` is an alias) | ✅ | ✅ Skill tool. Model invocation since Claude Code v2.1.246; can be blocked via `skillOverrides` | ✅ ref range `A...B`, PR, branch, path | **yes** | code.claude.com/docs/en/commands; code.claude.com/docs/en/code-review |
| qwen | `/review` bundled skill | ✅ | ✅ Skill tool | ❌ local diff / PR / file only | no | qwenlm.github.io/qwen-code-docs/en/users/features/code-review/ |
| amp | `code_review` tool, `amp review` | ✅ | ✅ in-thread tool | ❌ outstanding changes / since main | no | ampcode.com/news/liberating-code-review |
| copilot | Copilot CLI has `code-review` agent; Spec Kit's `copilot` targets **VS Code**, where review is a UI button | ✅ | ❌ in VS Code | – | no | docs.github.com/…/use-code-review; `specify_cli/integrations/copilot/__init__.py` ("GitHub Copilot in VS Code") |
| codex | TUI `/review`, CLI `codex review` | ✅ | ❌ shell-out only | `--base/--commit/--uncommitted` | no | learn.chatgpt.com/docs/developer-commands?surface=cli |
| gemini | none built-in. `/code-review` is the optional `gemini-cli-extensions/code-review` extension | ❌ | – | – | no | geminicli.com/docs/reference/commands/ |
| opencode | `/review` (source only) | ✅ | ❌ shell-out | ✅ | no | anomalyco/opencode `src/command/template/review.txt` |
| goose | `goose review` | ✅ | ❌ shell-out | ✅ | no | aaif-goose/goose release v1.38.0 |
| junie | `junie --review` | ✅ | ❌ shell-out | ✅ | no | junie.jetbrains.com/docs/junie-review-agent.html |
| droid | `/review` wizard | ✅ | ❌ user-only | – | no | docs.factory.ai/software-factory/code-review |
| kilocode | CLI `/review` | ✅ | unverified → ❌ | – | no | kilo.ai/docs/code-with-ai/platforms/cli |
| cursor_agent, devin, kiro_cli, auggie, cline, rovodev | none agent-invocable in the CLI | – | – | – | no | cursor.com/docs/cli/reference/slash-commands; docs.devin.ai/desktop/quick-review; kiro.dev/docs/reference/slash-commands/; docs.augmentcode.com/cli/reference; docs.cline.bot; support.atlassian.com/rovo/docs/rovo-dev-cli-commands/ |
| all others (tabnine, trae, zed, kimi, grok, forge, pi, …) | not verified | – | – | – | no | — |

**Decision**: The built-in map has one entry, **claude → `/code-review` via the Skill
tool**. Every other integration renders "no native review". A project can declare its
own reviewer for any integration in `specops.json`. Examples are a Codex shell-out
(`codex review --base …`) or Qwen's `/review`, where the project accepts that tool's
cost or target semantics.

**Rationale**: The feature exists to stop *silent* fallbacks. A map entry that
reviews the wrong diff, or that a sandboxed agent cannot launch, would create a new
one. The decision to take on a shell-out or a narrower target belongs to the project,
not to the default.

**Alternatives considered**:
- *Include every documented reviewer (codex, opencode, goose, junie via shell;
  qwen/amp with their own targets).* Rejected. Shell-out needs permissions and a
  second paid session, and qwen/amp cannot be pointed at the round's range. Both
  produce unreliable mandatory instructions.
- *Include Copilot CLI's `code-review` agent.* Rejected. Spec Kit's `copilot`
  integration is VS Code Copilot. The CLI agent belongs to a different host.

**Revisit**: This area moves fast. Claude's `/review` became an alias in v2.1.223 and
model invocation arrived in v2.1.246. The map is one dict in `nativereview.py`, and
adding an entry is a one-line change plus its test.

## R2 — Claude Code `/code-review` invocation details

- **Levels**: `low|medium|high|xhigh|max|ultra`. With no level, it reuses the last level
  the *user* typed, so the rendered text always passes the level explicitly.
  `ultra` is a billed cloud review that can stop to confirm the charge, so it is
  excluded from configuration (FR-010). Default: `high`.
- **Target**: A ref range such as `main...feat` is accepted. Step 3a passes the
  round's `reviewed_range` from `record-scope` written as `<from>...<head>`. Because
  `<from>` is an ancestor of `<head>`, the three-dot and two-dot diffs are identical.
- **Flags to avoid**: `--fix` (mutates the working tree), `--comment` and `--post`
  (publish outside the repo). Step 3a forbids them.
- **Execution**: In interactive sessions the skill runs as a background forked
  subagent, so Step 3a tells the reviewer to wait for its report before Step 4.
- **Failure modes that count as "not run"**: The Skill tool is absent (a delegated
  subagent without it, which is the field failure). The skill is blocked by
  `skillOverrides: user-invocable-only`. The Claude Code version is older than
  v2.1.246. The skill errors.
- **Risk to validate once in a real session** (quickstart §4): a raw commit-sha range
  is accepted as a target. The docs show branch names. If shas are refused, the
  fallback is to pass the paths from `scope_paths`.

## R3 — Where the render happens

**Decision**: Add a single `nativereview.render_review(root, integration) -> str` that
returns the full review-command text (`review.md` with `{{native_review}}` filled). Both
`initializer.run_init` (legacy path) and `extension.register_commands` (native path,
reached by `install`/`update`/`enable`) call it per target. `register_commands` renders
every target before writing any file, which keeps the "a rejected install writes
nothing" property. The init path renders, and so validates, every target before its
config step (step 4), so an invalid `native_review` fails before `specops.json` or any
prompt file is written.

**Rationale**: One function keeps the two paths identical (Principle IV). Rendering
uses the existing `fsutil.render_template`, which already fails closed on an unfilled
`{{…}}` (Feature 019).

**Alternatives considered**: Rendering inside `install_review`. Rejected: that
function is a thin writer called after decisions are made, and validation must happen
before the first write.

## R4 — Configuration shape and the Feature 021 freeze

**Decision**: An optional `native_review` object keyed by integration id, where each
value is `{ "command": str | null, "effort": str }` and both keys are optional. The
object is **not** added to `config._DEFAULTS`: it is never written by
`create_or_merge`, and its absence means built-in defaults. `specops.json` is read
with `config.load` only when the file exists. On first install it does not exist yet,
so defaults apply.

**Rationale**: `stability.md` allows a new optional key, and `test_frozen_config.py`
pins `_DEFAULTS`. Keeping the block out of `_DEFAULTS` leaves the frozen test and the
byte-for-byte idempotent `create_or_merge` untouched. Per-integration keying matches
per-integration rendering, as in the field project with Claude and Codex installed.

**Alternatives considered**: The flat `{command, effort, required}` from the original
request. Rejected: `required` has no effect now that there is no gate (spec revision
2026-09-29), and a flat `command` is ambiguous when several integrations are installed.

## R5 — The "not run" signal

**Decision**: Use a convention in the rendered text, not in code. The reviewer records
`specops handoff finding add --severity advisory --rule "native-review-not-run" --file .
--action "Native review not run: <command> (<reason>)"`. This is the same command and
shape as the existing `skipped-gate` instruction.

**Rationale**: The user decided that the review records do not change and that
SpecOps does not verify that the native reviewer ran. The finding already appears in
`handoff render` under advisory findings, so the "render shows it" criterion is met
with zero code.
