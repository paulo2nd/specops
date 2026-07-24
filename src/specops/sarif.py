"""Optional SARIF 2.1.0 output adapter (Feature 012, US4).

Projects Feature 011 structured findings into a schema-valid SARIF 2.1.0 document for
external tooling (GitHub code-scanning, CodeQL/semgrep viewers). Opt-in (``--sarif``);
plain ``json`` — no dependency. This is the **output** adapter only; the SARIF *input*
adapter is Feature 015 (out of scope). Deterministic: findings are projected in the
Feature 011 canonical order and ``rules`` are deduplicated + sorted (FR-013/FR-018).
"""
from __future__ import annotations

from typing import Any

__all__ = ["SARIF_VERSION", "project", "from_ledger"]

SARIF_VERSION = "2.1.0"
_SCHEMA_URI = "https://json.schemastore.org/sarif-2.1.0.json"
_INFO_URI = "https://github.com/paulosegundo/specops"
_LEVEL = {"blocking": "error", "advisory": "warning"}


def project(findings: list[dict[str, Any]], *, tool_version: str = "0.0.0") -> dict[str, Any]:
    """Build a SARIF 2.1.0 document from *findings* (already in canonical order)."""
    rules: dict[str, dict[str, str]] = {}
    results: list[dict[str, Any]] = []
    for f in findings:
        rule_id = str(f.get("rule") or "unknown")
        rules.setdefault(rule_id, {"id": rule_id, "name": rule_id})
        location: dict[str, Any] = {
            "physicalLocation": {"artifactLocation": {"uri": str(f.get("file") or "")}}
        }
        line = f.get("line")
        if isinstance(line, int):
            location["physicalLocation"]["region"] = {"startLine": line}
        results.append({
            "ruleId": rule_id,
            "level": _LEVEL.get(str(f.get("severity")), "warning"),
            "message": {"text": f"{f.get('id')}: {f.get('action') or ''}"},
            "locations": [location],
        })
    return {
        "version": SARIF_VERSION,
        "$schema": _SCHEMA_URI,
        "runs": [{
            "tool": {"driver": {
                "name": "specops",
                "version": tool_version,
                "informationUri": _INFO_URI,
                "rules": [rules[k] for k in sorted(rules)],
            }},
            "results": results,
        }],
    }


def from_ledger(data: dict[str, Any], *, tool_version: str = "0.0.0") -> dict[str, Any]:
    """Project every structured finding in *data* (canonical order) to SARIF 2.1.0."""
    from specops import handoff

    findings = [f for _cycle, f in handoff._canonical(data)]
    return project(findings, tool_version=tool_version)
