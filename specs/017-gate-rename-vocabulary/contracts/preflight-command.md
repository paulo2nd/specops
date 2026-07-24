# CLI Contract — `specops preflight` (and the `specops review` deprecated alias)

**Feature**: 017 | **Date**: 2026-07-24 | Supersedes the *name* of the Feature 004
`specops review` contract; **behavior is unchanged**.

## Canonical command

```
specops preflight [--json] [--soft] [--sarif]
```

Runs the deterministic gate suite (reconcile → gate-profile suite → working-tree → drift),
cheapest-first, and reports a verdict. Identical in every respect to the pre-rename
`specops review` except the command name and the `command` value in JSON output.

### Options (identical set to the former `specops review`)

| Option | Effect |
|---|---|
| `--json` | Emit the stable outcome JSON (`outcome.render`). |
| `--soft` | With `--json`, always exit `0` (verdict is in the JSON) — for a `do-while` loop body. |
| `--sarif` | Emit a SARIF 2.1.0 projection of findings and exit `0` (read-only, opt-in). |

### Exit codes (Principle VI, unchanged)

| Code | Meaning |
|---|---|
| `0` | Gates passed (`APPROVED`), or `--soft`/`--sarif` read-only exit. |
| `1` | Blocking gate result / `REJECTED` (hard mode, no `--soft`). |
| `2` | Infrastructure / data / usage error. |

### stdout (JSON mode)

```json
{ "command": "preflight", "outcome": "ok", "class": "pass", "verdict": "APPROVED", "gates": [ … ] }
```

- `command` = `"preflight"` when invoked as `preflight` (mirrors the invoked name, FR-004).
- All other keys, `OUTPUT_VERSION`, and value semantics are **unchanged** from Feature
  004/007/012 (SC-005: no key added/removed/renamed).

### stderr

Empty on success. Gate-rejection evidence and infra errors go to stderr exactly as before.

## Deprecated alias

```
specops review [--json] [--soft] [--sarif]
```

Behaves identically to `specops preflight` for the same repository state, **plus** a
single deprecation line on stderr. Retained for the deprecation window; not removed in
this feature (removed no earlier than the next MINOR release, never in a PATCH).

### Alias-specific contract

| Aspect | Guarantee |
|---|---|
| stdout | **Byte-identical** to `preflight` for the same state (including `--json`). |
| exit code | Identical to `preflight`. |
| `command` value in JSON | `"review"` (mirrors the invoked name — byte-stable for existing consumers). |
| stderr | **Exactly one** deprecation line, every invocation, emitted before the gate runs. |
| suppression | None — no flag, no environment variable (Clarification Q2). |
| `--help` | Marked deprecated; `preflight` is the canonical command (FR-014). |

Example stderr line (wording may be refined; behavior fixed):

```
specops review is deprecated; use 'specops preflight' (this alias will be removed no earlier than the next minor release).
```

## Workflow composition (updated shipped `workflow.yml`)

| Step | Before | After |
|---|---|---|
| `review-soft` (in-loop, soft precondition) | `shell: specops review --json --soft` | `shell: specops preflight --json --soft` |
| `terminal-gate` (hard, fail-closed) | `shell: specops review` | `shell: specops preflight` |
| `semantic-review` (agent directive) | `command: specops.review` | **unchanged** — reserved "review" |

The updated definition MUST still validate against the Spec Kit workflow engine and run
unchanged (FR-007, SC-003).

## Contract tests (must pass)

1. `specops preflight` over a passing fixture → `class:"pass"`, `verdict:"APPROVED"`,
   exit `0`, `command:"preflight"`, empty stderr. *(SC-001)*
2. `specops preflight` over a failing fixture (hard) → `class:"gate-rejection"`,
   exit `1`, evidence on stderr. *(SC-001)*
3. `specops review` over the same fixtures → stdout and exit code byte-identical to
   `preflight`; exactly one stderr line; `--json` stdout parses as clean JSON with
   `command:"review"`. *(SC-002)*
4. Workflow definition: `review-soft.run` contains `specops preflight --json --soft`;
   `terminal-gate.run == "specops preflight"`; `semantic-review.command == "specops.review"`
   (unchanged); definition validates. *(SC-003, FR-013)*
5. Outcome render: `render("preflight", …)` → `command:"preflight"`; existing
   `render("review", …)` cases still hold; no key change. *(SC-005)*
