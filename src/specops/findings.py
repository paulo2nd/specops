"""Finding records + the co-located finding-line grammar (Feature 018 US3).

The single owner of two things Feature 011/015 had split across modules:

- :func:`new_finding` — the one base-shape factory for a structured review finding.
  The three former construction sites (authoring, legacy import, external import)
  built the same dict by hand and had begun to drift; they now share this factory,
  so the base shape is identical everywhere (FR-008). Import-only provenance
  (``imported``/``producer``/``reviewed_digest``) layers on via keyword.
- :func:`parse_finding_line` / :func:`format_finding_line` — the ``<file>[:<line>]
  - <action>`` textual projection used by revision rendering (handoff) and legacy
  import parsing (formerly a regex in trace plus a renderer in handoff). Kept side by
  side with a round-trip guarantee (FR-009): ``parse_finding_line(format_finding_line(f))``
  recovers ``file``/``line``/``action`` losslessly.

The serialized dict shape is unchanged (same keys, same defaults, same order) — no
ledger schema change.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from specops.records import FindingRecord

# The line number is optional so a line-less finding (`<file> - <action>`) round-trips
# through render → import faithfully; `<file>:<line> - <action>` still matches.
_FINDING_RE = re.compile(r"^(?P<file>[^:\s]+)(?::(?P<line>\d+))?\s*-\s*(?P<text>.+)$")


def new_finding(
    *, id: str, severity: str, rule: str, file: str, line: int | None, action: str,
    expected_evidence: str | None = None, closure_criteria: str | None = None,
    imported: dict[str, Any] | None = None, producer: dict[str, Any] | None = None,
    reviewed_digest: dict[str, Any] | None = None,
) -> FindingRecord:
    """Build the base finding record shared by every construction path (FR-008).

    The base dict is always the same 14 keys in the same order (matching the ledger's
    stored shape); ``imported``/``producer``/``reviewed_digest`` are appended only when
    supplied (the external-import path). All lifecycle bookkeeping starts at its OPEN
    default — callers never re-specify ``state``/``task``/``commits``/``evidence``/
    ``fixed_at``/``verified_at``.
    """
    rec: FindingRecord = {
        "id": id, "severity": severity, "rule": rule, "file": file,
        "line": line, "action": action,
        "expected_evidence": expected_evidence, "closure_criteria": closure_criteria,
        "state": "OPEN", "task": None, "commits": [], "evidence": None,
        "fixed_at": None, "verified_at": None,
    }
    if imported is not None:
        rec["imported"] = imported
    if producer is not None:
        rec["producer"] = producer
    if reviewed_digest is not None:
        rec["reviewed_digest"] = reviewed_digest
    return rec


def parse_finding_line(line: str) -> dict[str, Any] | None:
    """Parse a ``<file>[:<line>] - <action>`` line into ``{file, line, action}``.

    Returns None when the line does not match the grammar (blank lines, prose). The
    optional ``line`` is an ``int`` when present, else ``None``. Inverse of
    :func:`format_finding_line`.
    """
    m = _FINDING_RE.match(line.strip())
    if not m:
        return None
    return {
        "file": m.group("file"),
        "line": int(m.group("line")) if m.group("line") else None,
        "action": m.group("text").strip(),
    }


def format_finding_line(finding: Mapping[str, Any]) -> str:
    """Render a finding's ``<file>[:<line>] - <action>`` line (ids live in the ledger,
    not the human line). Inverse of :func:`parse_finding_line` (round-trip, FR-009)."""
    loc = f"{finding['file']}:{finding['line']}" if finding.get("line") is not None \
        else finding.get("file")
    return f"{loc} - {finding.get('action')}"
