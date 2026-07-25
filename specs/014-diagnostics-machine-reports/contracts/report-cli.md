# Contract: `specops report`

Compact, read-only project/feature status report for the **active feature** (FR-014).
Distinct from the state-changing `specops status` verb group; complements the read-only
`status show` by adding a stable machine surface.

## Invocation

```text
specops report            # concise human status
specops report --json      # stable versioned JSON (StatusReport)
```

- No positional arguments. Operates on `Path(".")`. Read-only (SC-003).
- Reuses the `status.cmd_show` read path (feature/branch/phase, task tallies, review
  cycles, workflow lane) — no new state derivation.

## Exit codes

| Situation | outcome / class | Exit |
|---|---|---|
| Report produced (incl. "no active feature") | `ok` / `pass` | `0` |
| Ledger present but unreadable/corrupt | `error` / `infra-error` | `2` |

`report` has no `blocking` verdict of its own — it is a status view, not a gate. A missing
active feature is an `ok` state with `null` fields (not an error).

## Output (JSON, `--json`)

A `StatusReport` object (see `data-model.md`): `command`, `output_version`, `outcome`,
`class`, `active_feature`, `branch`, `phase`, `tasks{pending,in_progress,done,orphaned,total}`,
`active_task`, `review{cycles,blocking_open}`, `workflow_lane`. Byte-identical on unchanged
inputs.

## Determinism

Same discipline as `doctor`: no timestamps, no absolute paths, stable ordering.
