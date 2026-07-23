# Contract: SARIF output adapter (opt-in, FR-013)

Projects Feature 011 structured findings into **SARIF 2.1.0** for external tooling
(GitHub code-scanning, CodeQL/semgrep viewers). Emitted **only** with `--sarif`
(absent by default; absence is never a defect). Plain `json` — no dependency. This is
the **output** adapter only; the SARIF **input** adapter is Feature 015 (out of scope).

## Document shape (SARIF 2.1.0)

```json
{
  "version": "2.1.0",
  "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "specops",
          "version": "0.4.0",
          "informationUri": "https://github.com/…/specops",
          "rules": [
            { "id": "no-secrets", "name": "no-secrets" }
          ]
        }
      },
      "results": [
        {
          "ruleId": "no-secrets",
          "level": "error",
          "message": { "text": "R1-F01: remove hardcoded credential" },
          "locations": [
            {
              "physicalLocation": {
                "artifactLocation": { "uri": "src/config.py" },
                "region": { "startLine": 42 }
              }
            }
          ]
        }
      ]
    }
  ]
}
```

## Mapping (finding → SARIF result)

| SpecOps finding (Feature 011) | SARIF |
|---|---|
| `rule` | `result.ruleId` + a `tool.driver.rules[]` entry (deduped) |
| `severity` `blocking` | `level: "error"` |
| `severity` `advisory` | `level: "warning"` |
| `location` `file[:line]` | `physicalLocation.artifactLocation.uri` (+ `region.startLine`) |
| `id` + `action` | `message.text` = `"<id>: <action>"` |
| CLI version | `tool.driver.version` |

## Guarantees

- Schema-valid SARIF 2.1.0; findings ordered by the Feature 011 canonical sort key
  (round → severity → location → finding id) ⇒ deterministic (FR-018).
- `rules[]` deduplicated and sorted by `id`.
- No SARIF is produced without `--sarif`; producing it never mutates state (FR-015).
- A finding with no line ⇒ `region` omitted (not a defect).
</content>
