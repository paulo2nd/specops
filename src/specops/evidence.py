"""Structured evidence records (Feature 012, US2).

The versioned, id-addressable successor to the flat ``<CLASS>:<summary>`` evidence
string. A record carries a **cache-key-derived id** (FR-009), producer, command, exit
code, timezone-aware timestamp, commit range, affected paths, summary, and an optional
local-artifact digest. The id is a deterministic function of the cache key
(``producer``/``command``/``commit_range``/``affected_paths``/``context_map_digest``) —
so identical production yields an identical id and any cache-key change yields a new id
that **supersedes** (never mutates) the prior record (append-only history).

Records are stored as plain dicts in the ledger (YAML); their static shape is
:class:`specops.records.EvidenceRecord` (Feature 019 US3). This module imports only
the stdlib and the import-free :mod:`specops.records`, so :mod:`specops.ledger` can
import it without a cycle.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from specops.records import EvidenceRecord

__all__ = [
    "ID_PREFIX", "EVIDENCE_CLASSES", "validate_string", "cache_key", "derive_id",
    "build_record", "digest_artifact", "parse_legacy_string", "append_record",
    "canonical_sort",
]

ID_PREFIX = "EV-"

# Sole owner of the `<CLASS>:<summary>[; …]` evidence grammar (Feature 018 US3):
# the class set, the part regex, and validation live here; task-close (status) and
# finding-close (handoff) both consume `validate_string` so the grammar has one home.
EVIDENCE_CLASSES = ("CLI_LOG", "TEST_REPORT", "SCREENSHOT_PATH", "CODE_DIFF")
_PART_RE = re.compile(r"^(" + "|".join(EVIDENCE_CLASSES) + r"):(.+)$")


def validate_string(evidence: str) -> bool:
    """Return True when *evidence* matches the strict grammar: ``CLASS:summary[; CLASS:summary …]``.

    An empty string, an unknown class, a missing colon, an empty summary, a
    leading-space summary, or any non-conformant ``; ``-separated part is rejected.
    Promoted verbatim from the retired status helper ``validate_evidence`` (behavior
    identical).
    """
    if not evidence:
        return False
    for part in evidence.split("; "):
        m = _PART_RE.match(part)
        if not m:
            return False
        summary = m.group(2)
        if not summary or summary[0] == " ":
            return False
    return True


def cache_key(
    *, producer: str, command: str, commit_range: str,
    affected_paths: list[str], context_map_digest: str | None,
    subject: str | None = None, worktree_digest: str | None = None,
) -> dict[str, Any]:
    """The identity tuple (FR-009). Volatile fields (timestamp/exit code/summary/
    digest) are deliberately excluded so re-production yields a stable id.

    ``subject`` is an optional disambiguator (None for gate records — a gate's identity
    already lives in ``producer`` — so gate caching keys match the documented tuple).
    It is set for ``auto`` records (a task id, a finding id, or a migrated legacy part)
    so two records sharing identical provenance but distinct content do not collide.

    ``worktree_digest`` (Feature 024) is an optional gate-cache dimension: it is
    included in the key **only when provided**, so ``auto``/legacy callers (which pass
    None) keep byte-identical keys and ids — no migration. Gate-run cache records pass
    a digest of the uncommitted tree so any edit (committed or not) invalidates reuse.
    """
    key: dict[str, Any] = {
        "producer": producer,
        "command": command,
        "commit_range": commit_range,
        "affected_paths": sorted(affected_paths),
        "context_map_digest": context_map_digest,
        "subject": subject,
    }
    if worktree_digest is not None:
        key["worktree_digest"] = worktree_digest
    return key


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
    subject: str | None = None, worktree_digest: str | None = None,
    amendment: bool = False, reason: str | None = None,
) -> EvidenceRecord:
    """Build a structured evidence record dict with its cache-key-derived id (FR-006).

    ``worktree_digest`` (Feature 024) is threaded into the cache key for gate-run cache
    records so the derived id matches the gate's own lookup key; None for all other
    producers (id unchanged).

    ``amendment`` / ``reason`` (Feature 026, v9) mark a correction recorded after the
    task closed. Both are omitted from a close-time record, so their *absence* is what
    identifies an original — a consumer never has to know about amendments to read one.
    A reason is mandatory for an amendment (FR-005) and is deliberately **not** part of
    the cache key: it is content, not identity (callers disambiguate repeated
    amendments through ``subject``)."""
    if amendment and not reason:
        raise ValueError("An amendment requires a non-empty reason.")
    key = cache_key(
        producer=producer, command=command, commit_range=commit_range,
        affected_paths=affected_paths, context_map_digest=context_map_digest,
        subject=subject, worktree_digest=worktree_digest,
    )
    rec: EvidenceRecord = {
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
    if amendment:
        rec["amendment"] = True
        rec["reason"] = str(reason)
    return rec


def parse_legacy_string(
    evidence: str, *, timestamp: str, commit_range: str, subject: str | None = None,
) -> list[EvidenceRecord]:
    """Convert a legacy ``<CLASS>:<summary>[; …]`` string into structured record(s).

    Each grammar-conformant part becomes one record (``producer="auto"``,
    ``command="(migrated)"``, ``exit_code=0``, ``affected_paths=[]``). A string that
    does not match the grammar is preserved **verbatim** as a single opaque record
    (never dropped — FR-007), so migration is zero-loss.
    """
    parts = [p for p in evidence.split("; ") if p]
    recs: list[EvidenceRecord] = []
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


def canonical_sort(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Return *records* in the FR-021 canonical order (producer, timestamp, commit
    range) so any evidence listing is reproducible independent of insertion order."""
    return sorted(records, key=lambda r: (
        str(r.get("producer") or ""),
        str(r.get("timestamp") or ""),
        str(r.get("commit_range") or ""),
        str(r.get("id") or ""),
    ))


def append_record(
    evidence: list[EvidenceRecord], rec: EvidenceRecord, *, supersede: bool = False,
) -> EvidenceRecord:
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
