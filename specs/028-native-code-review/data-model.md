# Data Model: Native Code Review in `/specops-review`

No persisted state is added. The ledger is unchanged, and `specops.json` is read and
never written. The two entities below exist only at install time.

## Entity 1 — Native review map entry (built-in, `nativereview.py`)

| Field | Type | Notes |
|---|---|---|
| `integration` | str | Spec Kit integration id, e.g. `claude` |
| `command` | str | Display name of the native reviewer, e.g. `/code-review` |
| `mechanism` | str | How the agent invokes it, e.g. `the Skill tool` |
| `invocation` | str | Template for the exact call, with `{effort}` |
| `efforts` | tuple[str, ...] | Accepted configured levels, e.g. `low, medium, high, xhigh, max` |
| `default_effort` | str | `high` |

Built-in set: `claude` only (research R1). An integration missing from the map means
**no native review**.

## Entity 2 — `native_review` configuration (`specops.json`, optional)

```json
{
  "native_review": {
    "<integration-id>": { "command": "<string> | null", "effort": "<level>" }
  }
}
```

Resolution for one integration:

| Config for the id | Built-in entry | Result |
|---|---|---|
| absent | present | built-in entry, `default_effort` |
| `{effort: X}` | present | built-in entry, effort X |
| `{command: null}` | any | **no native review** |
| `{command: "S"}` | any | override: command S, generic mechanism, no effort |
| absent | absent | **no native review** |

Validation raises `ConfigError` (exit 1, the existing code for `specops.json` errors), and nothing is written. That covers both install paths: `specops init` validates before its step 4. The error cases:

- `native_review` is not an object, or an entry is not an object.
- An entry has keys other than `command` and `effort`. This catches typos such as `efort`.
- `command` is neither a non-empty string nor `null`.
- `effort` is set while the entry resolves to an override or to no native review. Arguments for an override belong in its `command` string.
- `effort` is not one of the built-in entry's `efforts`. This includes `ultra` for `claude`.

Keys for integrations that are not installed are allowed and ignored, so a
configuration shared across machines never breaks an install.
