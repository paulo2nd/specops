# Contract: `specops.json` → `native_review`

**Feature 028** | additive, optional key | stability class: `specops.json` "new optional key" (`docs/stability.md`)

The block is optional and never written by SpecOps. It is absent from `config._DEFAULTS`,
so `create_or_merge` output and `test_frozen_config.py` are unchanged.

```json
{
  "native_review": {
    "claude": { "effort": "max" },
    "codex":  { "command": "codex review --base <from> (via the shell)" },
    "qwen":   { "command": "/review" },
    "gemini": { "command": null }
  }
}
```

| Key | Type | Default | Meaning |
|---|---|---|---|
| `native_review` | object | absent → built-in map | per-integration overrides, keyed by Spec Kit integration id |
| `.<id>.command` | string \| null | built-in entry, or none | string: this project's reviewer for `<id>`, rendered verbatim with a generic invocation sentence. `null`: `<id>` has no native review |
| `.<id>.effort` | string | `high` (claude) | only for a built-in entry. Claude accepts `low\|medium\|high\|xhigh\|max`, and `ultra` is rejected |

**Errors**: any rule in data-model.md Entity 2 raises `ConfigError`. `specops init` and
`specops extension install|update|enable` then exit **1**, write nothing, and name the
offending key. Exit 1 is the existing `ConfigError` code, the same one an unparseable
`specops.json` gets. `specops init` validates before its config step (step 4), so it
also writes nothing.

**Takes effect**: on the next `specops extension update` (or reinstall). The rendered
review command reflects the configuration at the time of its last install.
