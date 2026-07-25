# Contract: CLI Output Freeze (byte-identical, one sanctioned delta)

**Scope**: every `specops` subcommand, human and `--json` modes, stdout/stderr and exit codes.

## Invariant

For every command, every scenario exercised by the existing test fixtures, and both output modes:

```
capture_after(cmd, scenario) == capture_before(cmd, scenario)
```

where a capture is the triple `(stdout_bytes, stderr_bytes, exit_code)` — with exactly one permitted difference, specified below. Valid-input behavior is frozen at the byte level; deliberate micro-deltas on *invalid* inputs are enumerated here and nowhere else.

## The sanctioned delta: lane JSON envelope

`specops lane <start|status|check|attest|close|promote> --json` gains two top-level fields, matching the envelope every other family already emits:

```json
{
  "output_version": "<lane OUTPUT_VERSION>",
  "command": "lane <sub>",     // unchanged
  "status": "<status token>",  // NEW at top level
  ...existing payload fields   // unchanged, none removed or renamed
}
```

- Additive only. Field order of existing keys is preserved as serialized today.
- Human mode for lane commands: unchanged.
- Exit codes for lane commands: unchanged (`soft` semantics preserved).
- CHANGELOG records this as the feature's single behavior change.

## Enumerated invalid-input convergences (D4)

Bounded to corrupted or hand-edited ledgers; these adopt the canonical behavior rather than preserving accidental divergence:

1. **Unparsable ledger**: `status show`, `status report`, and `reconcile` all emit `ledger.load_raw`'s diagnostic with exit code 2 (`LedgerParseError`). Legacy per-command wordings (e.g. reconcile's "Cannot parse ledger") are retired.
2. **Non-mapping task entries**: `status show` filters them exactly as `status report`/`compact_status` does (previously: crash vs filter divergence).

## Verification

- Golden capture harness per research.md D8: recorded on the pre-change baseline commit, re-diffed after each user story, asserted empty (modulo the lane delta and the two enumerated convergences) before merge.
- Runs exclusively against test fixture repositories — never against this repository (No Self-Application).
- Final gate: SC-001 / SC-006.
