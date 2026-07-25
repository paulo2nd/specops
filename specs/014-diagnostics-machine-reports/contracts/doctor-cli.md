# Contract: `specops doctor`

Read-only diagnostic across all SpecOps-specific surfaces for the **active feature only**
(`.specify/feature.json`).

## Invocation

```text
specops doctor            # human-readable report to stdout
specops doctor --json      # stable versioned JSON document (see doctor-output.schema.json)
```

- No positional arguments. No flags beyond `--json`. Operates on the current working
  directory (`Path(".")`), like the other read-only commands.
- MUST NOT mutate any file (repository, ledger, context map, config) — verified by
  `snapshot_tree` before/after (SC-003).
- MUST NOT execute `specify`, any gate command, or any subprocess that runs user code.
  The only environment interaction beyond file reads is: git reads (GitPython) and
  `shutil.which` PATH lookups for gate availability (locate only, never execute).

## Exit codes (Principle VI / Feature 007 outcome contract)

| Overall verdict | outcome / class | Exit |
|---|---|---|
| `ok` or `warning` | `ok` / `pass` | `0` |
| `blocking` present | `blocked` / `gate-rejection` | `1` |
| `execution-error` present | `error` / `infra-error` | `2` |

The three classes MUST be mutually distinguishable by exit code alone (SC-004).

## Output (human)

Concise per-domain lines with a severity marker and, for non-`ok` findings, the next
action text. A final line states the overall verdict. Non-`pass` outcomes render to
stderr (the `_emit_*` idiom).

## Output (JSON, `--json`)

A single object conforming to [`doctor-output.schema.json`](./doctor-output.schema.json):
`command`, `output_version`, `outcome`, `class`, `verdict`, `domains[]`. Byte-identical on
unchanged inputs (FR-007/SC-005). Consumers MUST tolerate unknown `domain` ids and unknown
`next_action_code` values without error (forward-compat, D4).

## Determinism guarantees

- No wall-clock timestamps, absolute host paths, or native-command output in the payload.
- Domains emitted in the fixed order defined in `data-model.md`; findings sorted by
  `(id, message)`.

## Behavioral requirements (traceability)

- Reports a result for **every** domain each run (SC-002); never stops at the first
  problem (FR-013).
- "No active feature" and "no context map" are `ok` states, verdict unaffected
  (FR-009/FR-010).
- A domain whose input is unreadable/corrupt is reported `execution-error`, never omitted
  or silently `ok` (FR-015).
- Ambiguous active-feature identity ⇒ `blocking` (fail-closed, FR-012).
- Migratable (prior, supported) ledger ⇒ `warning`; too-new/unsupported ⇒ `blocking` (D6).
