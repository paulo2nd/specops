# Contract: `specops handoff record-scope` output

**Feature 027** | additive change | `handoff.OUTPUT_VERSION` stays `1`

Additive under the stability policy: three new **optional** keys, no key removed,
no key's meaning changed (`specs/021-contract-freeze/contracts/stability-policy.md:27`).

## Before

```json
{
  "command": "handoff record-scope",
  "outcome": "ok",
  "class": "pass",
  "output_version": 1,
  "round": 2,
  "review_role": "corrective",
  "reviewed_range": "<t1>..<head>",
  "scope_paths": ["src/a.py", "src/b.py"]
}
```

## After

```json
{
  "command": "handoff record-scope",
  "outcome": "ok",
  "class": "pass",
  "output_version": 1,
  "round": 2,
  "review_role": "corrective",
  "reviewed_range": "<t1>..<head>",
  "scope_paths": ["src/a.py", "src/b.py"],
  "baseline_paths": ["src/a.py", "src/b.py", "src/c.py", "src/d.py"],
  "not_reverified_paths": ["src/c.py", "src/d.py"],
  "never_reached_paths": ["src/d.py"]
}
```

| Key | Status | Contents |
|---|---|---|
| `scope_paths` | **unchanged** | this round's priority set |
| `baseline_paths` | new (US1) | full `baseline..HEAD` product set |
| `not_reverified_paths` | new (US1) | `baseline_paths − scope_paths` |
| `never_reached_paths` | new (US2) | reached by no recorded round (data-model entity 4) |

US1 ships the first two keys; `never_reached_paths` arrives with US2's derivation.
Each addition is independently additive — a consumer reading only `scope_paths`
is unaffected by either.

All three are sorted, deduplicated, and repo-relative. All three are **derived
per call and never persisted** (FR-010).

## Anchor round

`scope_paths == baseline_paths` ⇒ `not_reverified_paths == []`. The human output
prints the priority block only — no second reading obligation is implied (spec
AS US1-2).

## Human output

```
review scope: corrective round 2 — 2 file(s) over <t1>..<head>
src/a.py
src/b.py

not yet re-verified this round (2 of 4 baseline file(s)):
src/c.py
src/d.py

never reviewed by any round (1):
src/d.py
```

A block whose set is empty is omitted entirely. The `never reviewed by any round`
block is not bounded here (unlike the approval message, R6) — it is a report, not
an error line.

## What does not change

- The persisted `reviewed_range` / `review_role` and how they are derived (FR-002).
- Exit codes, `output_version`, the base envelope, every other `handoff` command.
- The `SCOPE_RECORDED` / `SCOPE_UNRESOLVABLE` / `BAD_ARGS` outcome classes.
