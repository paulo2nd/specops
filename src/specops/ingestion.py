"""External review ingestion (Feature 015) — pure parse / validate / identity / staleness.

Turns an external reviewer's output — a versioned JSON contract
(``contracts/findings-input.schema.json``) or a SARIF 2.1.0 document — into
:class:`NormFinding` objects that :mod:`specops.handoff` records as **advisory**
Feature 011 findings. This module performs **no I/O and no ledger writes**: it only
parses, validates (accumulating *every* defect for all-or-nothing import, FR-013),
computes the digest-independent content identity (FR-008), and compares per-path
content digests for staleness (FR-010).

Every imported finding is ``advisory`` regardless of any producer-declared severity
(FR-005/FR-012): no external input raises SpecOps severity. Promotion to ``blocking``
is a separate, human, audited step in :mod:`specops.handoff` (FR-006).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from specops import sarif, trace

# Versioned, stack-neutral JSON input contract (FR-001).
INPUT_CONTRACT_VERSION = 1
ADVISORY = "advisory"
UNSPECIFIED_VERSION = "unspecified"


@dataclass
class NormFinding:
    """A normalized finding from an adapter, before :mod:`specops.handoff` records it.

    ``declared_severity`` is retained for the audit trail only — it never sets the
    recorded severity (always ``advisory`` at import).
    """

    rule: str
    file: str
    line: int | None
    action: str
    producer_name: str
    producer_version: str
    reviewed_commit: str | None
    source_format: str            # "json" | "sarif"
    declared_severity: str | None  # informational only


def content_identity(f: NormFinding) -> tuple:
    """Digest-independent identity ``(producer, rule, file, line, action)`` (R1/FR-008).

    Two findings with equal identity are the *same* finding — the key for
    within-document dedup and idempotent re-import. The reviewed-diff digest and any
    promotion/staleness state are deliberately excluded.
    """
    return (f.producer_name, f.rule, f.file, f.line, f.action)


def is_stale(reviewed_blob: str | None, current_blob: str | None) -> bool:
    """True when a finding's own path changed since it was reviewed (FR-010).

    A path that is absent at HEAD (``current_blob is None``) is stale — its target
    was removed (this holds even when the reviewed baseline itself was ``None``).
    Otherwise stale when the current per-path content digest differs from the one
    recorded at import. Path granularity: unrelated paths never affect this.

    Callers MUST only invoke this when the repository is resolvable; when it is not
    (no current digest can be computed at all) staleness is *unknown*, not stale,
    and the caller reports it as such rather than passing ``None`` here.
    """
    if current_blob is None:
        return True
    return reviewed_blob != current_blob


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _req_str(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _resolve_producer(
    raw: Any, fallback: Any,
) -> tuple[str | None, str | None, str | None]:
    """Resolve ``(name, version, error)`` from a per-finding producer or the doc default."""
    if raw is not None and not isinstance(raw, dict):
        # A present-but-malformed producer is a defect, never a silent fall-through to
        # the document producer (which would misattribute and break dedup identity).
        return None, None, "producer must be an object"
    p = raw if isinstance(raw, dict) else fallback
    if not isinstance(p, dict):
        return None, None, "missing producer"
    name = _req_str(p.get("name"))
    if name is None:
        return None, None, "producer missing 'name'"
    version = _req_str(p.get("version")) or UNSPECIFIED_VERSION
    return name, version, None


def _dedup(findings: list[NormFinding]) -> list[NormFinding]:
    """Collapse equal-identity findings deterministically, keeping the first (FR-009)."""
    seen: set[tuple] = set()
    out: list[NormFinding] = []
    for f in findings:
        key = content_identity(f)
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


# ---------------------------------------------------------------------------
# JSON input contract (FR-001)
# ---------------------------------------------------------------------------


def parse_contract(doc: Any) -> tuple[list[NormFinding], list[str]]:
    """Parse a findings-input-contract document → ``(normalized, defects)``.

    All-or-nothing: when *defects* is non-empty the caller imports nothing, so this
    accumulates **every** defect. A valid document with zero findings returns
    ``([], [])`` — a supported no-op.
    """
    if not isinstance(doc, dict):
        return [], ["document is not a JSON object"]

    defects: list[str] = []
    cv = doc.get("contract_version")
    if cv != INPUT_CONTRACT_VERSION:
        defects.append(
            f"unsupported contract_version {cv!r} (expected {INPUT_CONTRACT_VERSION})")

    doc_producer = doc.get("producer")
    doc_commit = doc.get("reviewed_commit")
    raw = doc.get("findings")
    if raw is None:
        defects.append("missing 'findings' array")
        raw = []
    elif not isinstance(raw, list):
        defects.append("'findings' is not an array")
        raw = []

    normalized: list[NormFinding] = []
    for i, item in enumerate(raw):
        nf, fdefects = _norm_contract_finding(item, i, doc_producer, doc_commit)
        defects.extend(fdefects)
        if nf is not None:
            normalized.append(nf)

    if defects:
        return [], defects
    return _dedup(normalized), []


def _norm_contract_finding(
    item: Any, index: int, doc_producer: Any, doc_commit: Any,
) -> tuple[NormFinding | None, list[str]]:
    if not isinstance(item, dict):
        return None, [f"finding {index}: not an object"]
    d: list[str] = []
    rule = _req_str(item.get("rule"))
    file = _req_str(item.get("file"))
    action = _req_str(item.get("action"))
    if rule is None:
        d.append(f"finding {index}: missing 'rule'")
    if file is None:
        d.append(f"finding {index}: missing 'file'")
    if action is None:
        d.append(f"finding {index}: missing 'action'")
    name, version, perr = _resolve_producer(item.get("producer"), doc_producer)
    if perr:
        d.append(f"finding {index}: {perr}")
    line = item.get("line")
    if line is not None and (isinstance(line, bool) or not isinstance(line, int)):
        d.append(f"finding {index}: 'line' is not an integer")
        line = None
    if d:
        return None, d
    commit = item.get("reviewed_commit") or doc_commit
    return NormFinding(
        rule=rule, file=trace.norm_path(file), line=line, action=action,  # type: ignore[arg-type]
        producer_name=name, producer_version=version,  # type: ignore[arg-type]
        reviewed_commit=commit if isinstance(commit, str) else None,
        source_format="json", declared_severity=item.get("severity"),
    ), []


# ---------------------------------------------------------------------------
# SARIF 2.1.0 input adapter (FR-011/FR-012)
# ---------------------------------------------------------------------------


def parse_sarif(doc: Any) -> tuple[list[NormFinding], list[str]]:
    """Parse a SARIF 2.1.0 document → ``(normalized, defects)``.

    The inverse of the Feature 012 SARIF *output* adapter. Every result lands
    ``advisory`` (the SARIF ``level`` is informational). All-or-nothing.
    """
    if not isinstance(doc, dict):
        return [], ["document is not a JSON object"]

    defects: list[str] = []
    if doc.get("version") != sarif.SARIF_VERSION:
        defects.append(
            f"unsupported SARIF version {doc.get('version')!r} "
            f"(expected {sarif.SARIF_VERSION})")
    runs = doc.get("runs")
    if not isinstance(runs, list):
        defects.append("SARIF 'runs' is not an array")
        runs = []

    normalized: list[NormFinding] = []
    for ri, run in enumerate(runs):
        if not isinstance(run, dict):
            defects.append(f"run {ri}: not an object")
            continue
        name, version = _sarif_producer(run)
        if name is None:
            defects.append(f"run {ri}: missing tool.driver.name")
        results = run.get("results")
        if results is None:
            results = []
        elif not isinstance(results, list):
            defects.append(f"run {ri}: 'results' is not an array")
            continue
        for xi, res in enumerate(results):
            nf, rdefects = _norm_sarif_result(
                res, ri, xi, name or "", version or UNSPECIFIED_VERSION)
            defects.extend(rdefects)
            if nf is not None:
                normalized.append(nf)

    if defects:
        return [], defects
    return _dedup(normalized), []


def _sarif_producer(run: dict) -> tuple[str | None, str | None]:
    tool = run.get("tool")
    driver = tool.get("driver") if isinstance(tool, dict) else None
    if not isinstance(driver, dict):  # a truthy non-dict (list/str) must not crash .get()
        driver = {}
    name = _req_str(driver.get("name"))
    version = _req_str(driver.get("version")) or UNSPECIFIED_VERSION
    return name, version


def _sarif_location(res: dict) -> tuple[str | None, int | None]:
    """Primary-location rule: the first location bearing an artifact URI (FR-012)."""
    for loc in res.get("locations") or []:
        if not isinstance(loc, dict):
            continue
        phys = loc.get("physicalLocation")
        if not isinstance(phys, dict):
            continue
        art = phys.get("artifactLocation")
        uri = art.get("uri") if isinstance(art, dict) else None
        if isinstance(uri, str) and uri:
            region = phys.get("region")
            line = region.get("startLine") if isinstance(region, dict) else None
            return uri, line if isinstance(line, int) else None
    return None, None


def _norm_sarif_result(
    res: Any, ri: int, xi: int, name: str, version: str,
) -> tuple[NormFinding | None, list[str]]:
    if not isinstance(res, dict):
        return None, [f"run {ri} result {xi}: not an object"]
    rule = _req_str(res.get("ruleId")) or "unknown"
    message = res.get("message")
    text = _req_str(message.get("text")) if isinstance(message, dict) else None
    action = text or rule
    uri, line = _sarif_location(res)
    if uri is None:
        return None, [f"run {ri} result {xi}: no usable physical location"]
    return NormFinding(
        rule=rule, file=trace.norm_path(uri), line=line, action=action,
        producer_name=name, producer_version=version,
        reviewed_commit=None, source_format="sarif",
        declared_severity=res.get("level"),
    ), []
