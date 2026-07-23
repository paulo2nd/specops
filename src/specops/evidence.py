"""Structured evidence records (Feature 012, US2).

The versioned, id-addressable successor to the flat ``<CLASS>:<summary>`` evidence
string. A record carries a **cache-key-derived id** (FR-009), producer, command, exit
code, timezone-aware timestamp, commit range, affected paths, summary, and an optional
local-artifact digest. The id is a deterministic function of the cache key
(``producer``/``command``/``commit_range``/``affected_paths``/``context_map_digest``) —
so identical production yields an identical id and any cache-key change yields a new id
that **supersedes** (never mutates) the prior record (append-only history).

Records are stored as plain dicts in the ledger (YAML). This module is dependency-free
(stdlib only) so :mod:`specops.ledger` can import it without a cycle.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

__all__ = [
    "ID_PREFIX", "EVIDENCE_CLASSES", "cache_key", "derive_id", "build_record",
    "digest_artifact", "parse_legacy_string", "append_record", "canonical_sort",
]

ID_PREFIX = "EV-"

# The legacy evidence-string grammar migrated by v5→v6 (mirrors status.EVIDENCE_CLASSES).
EVIDENCE_CLASSES = ("CLI_LOG", "TEST_REPORT", "SCREENSHOT_PATH", "CODE_DIFF")
_PART_RE = re.compile(r"^(" + "|".join(EVIDENCE_CLASSES) + r"):(.+)$")


def cache_key(
    *, producer: str, command: str, commit_range: str,
    affected_paths: list[str], context_map_digest: str | None,
    subject: str | None = None,
) -> dict[str, Any]:
    """The identity tuple (FR-009). Volatile fields (timestamp/exit code/summary/
    digest) are deliberately excluded so re-production yields a stable id.

    ``subject`` is an optional disambiguator (None for gate records — a gate's identity
    already lives in ``producer`` — so gate caching keys match the documented tuple).
    It is set for ``auto`` records (a task id, a finding id, or a migrated legacy part)
    so two records sharing identical provenance but distinct content do not collide.
    """
    return {
        "producer": producer,
        "command": command,
        "commit_range": commit_range,
        "affected_paths": sorted(affected_paths),
        "context_map_digest": context_map_digest,
        "subject": subject,
    }


def derive_id(key: dict[str, Any]) -> str:
    """Deterministic ``EV-<hex12>`` id derived from the cache key (SC-003/SC-005)."""
    blob = json.dumps(key, sort_keys=True, separators=(",", ":"))
    return ID_PREFIX + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]


def digest_artifact(path: Path) -> str | None:
    """Return ``sha256:<hex>`` of a local file's bytes, or None when absent (FR-019).

    No remote copy is stored — the digest is the current-at-production content hash,
    so a later change is detectable by re-digesting.
    """
    if not path.is_file():
        return None
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build_record(
    *, producer: str, command: str, exit_code: int, timestamp: str,
    commit_range: str, affected_paths: list[str], summary: str,
    context_map_digest: str | None = None, artifact_digest: str | None = None,
    subject: str | None = None,
) -> dict[str, Any]:
    """Build a structured evidence record dict with its cache-key-derived id (FR-006)."""
    key = cache_key(
        producer=producer, command=command, commit_range=commit_range,
        affected_paths=affected_paths, context_map_digest=context_map_digest,
        subject=subject,
    )
    rec: dict[str, Any] = {
        "id": derive_id(key),
        "producer": producer,
        "command": command,
        "exit_code": exit_code,
        "timestamp": timestamp,
        "commit_range": commit_range,
        "affected_paths": sorted(affected_paths),
        "summary": summary,
        "superseded_by": None,
    }
    if artifact_digest is not None:
        rec["artifact_digest"] = artifact_digest
    return rec


def parse_legacy_string(
    evidence: str, *, timestamp: str, commit_range: str, subject: str | None = None,
) -> list[dict[str, Any]]:
    """Convert a legacy ``<CLASS>:<summary>[; …]`` string into structured record(s).

    Each grammar-conformant part becomes one record (``producer="auto"``,
    ``command="(migrated)"``, ``exit_code=0``, ``affected_paths=[]``). A string that
    does not match the grammar is preserved **verbatim** as a single opaque record
    (never dropped — FR-007), so migration is zero-loss.
    """
    parts = [p for p in evidence.split("; ") if p]
    recs: list[dict[str, Any]] = []
    conformant = parts and all(_PART_RE.match(p) for p in parts)
    slices = parts if conformant else [evidence]
    for i, summary in enumerate(slices):
        # Disambiguate parts sharing identical provenance by their content + index.
        part_subject = f"{subject}#{i}:{summary}" if subject else f"#{i}:{summary}"
        recs.append(build_record(
            producer="auto", command="(migrated)", exit_code=0,
            timestamp=timestamp, commit_range=commit_range,
            affected_paths=[], summary=summary, subject=part_subject,
        ))
    return recs


def canonical_sort(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return *records* in the FR-021 canonical order (producer, timestamp, commit
    range) so any evidence listing is reproducible independent of insertion order."""
    return sorted(records, key=lambda r: (
        str(r.get("producer") or ""),
        str(r.get("timestamp") or ""),
        str(r.get("commit_range") or ""),
        str(r.get("id") or ""),
    ))


def append_record(
    evidence: list[dict[str, Any]], rec: dict[str, Any], *, supersede: bool = False,
) -> dict[str, Any]:
    """Append *rec* to *evidence*, or return the existing record on an id match.

    Idempotent: a record whose id already exists (identical cache key) is reused, not
    duplicated (FR-009 ``cached``). When *supersede* is True, any prior non-superseded
    record with the **same producer** (i.e. the same gate) is marked ``superseded_by``
    the new id — never mutated otherwise. Task evidence uses ``supersede=False`` (each
    task's evidence is independent); gate evidence (US3) uses ``supersede=True``.
    """
    for existing in evidence:
        if existing.get("id") == rec["id"]:
            return existing
    if supersede:
        for existing in evidence:
            if (
                existing.get("producer") == rec["producer"]
                and existing.get("superseded_by") is None
            ):
                existing["superseded_by"] = rec["id"]
    evidence.append(rec)
    return rec
