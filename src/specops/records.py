"""Typed schemas for ledger records (Feature 019 US3, FR-005).

A **static** contract over the ledger's existing dict shapes: every type here is a
:class:`typing.TypedDict`, i.e. a plain ``dict`` at runtime, so adopting them changes
zero serialized bytes and adds zero runtime validation. Tolerance for hand-edited or
legacy ledgers stays exactly where it is today — in the existing validation paths and
``isinstance`` filters — these types exist so mypy catches a mistyped record key or a
wrongly-typed field before the tests run.

Stdlib-only with no intra-package imports (the same posture as
:mod:`specops.evidence`), so ``ledger``, ``status``, ``handoff``, ``findings``, and
``evidence`` can all import it without cycles.

Casting discipline (research D4): values arriving from ``yaml.safe_load`` enter as
untyped dicts and are cast **once** at the canonical points where the shape is
structurally known (after classify/migrate in ``status.load_for_write``); boundary
functions that deliberately accept untrusted input (validators, doctor's read paths)
take :data:`LedgerLike` so both typed and raw documents flow in.
"""
from __future__ import annotations

from typing import Any, TypedDict


class ContextProvenance(TypedDict, total=False):
    """Feature 009 provenance snapshot: ``{map: none|invalid}`` or a present-map record."""

    map: str
    digest: str
    context_ids: list[str]
    output_version: int


class _TaskRequired(TypedDict):
    id: str
    status: str
    started_commit: str | None
    commits: list[str]
    evidence: str | None
    completed_at: str | None


class TaskRecord(_TaskRequired, total=False):
    """One ``tasks[]`` entry (base keys from the tasks.md sync scaffold; extras additive)."""

    orphaned: bool
    context_provenance: ContextProvenance
    evidence_refs: list[str]


class _FindingRequired(TypedDict):
    """The 14 base keys every finding carries (single factory: ``findings.new_finding``)."""

    id: str
    severity: str
    rule: str
    file: str
    line: int | None
    action: str
    expected_evidence: str | None
    closure_criteria: str | None
    state: str
    task: str | None
    commits: list[str]
    evidence: str | None
    fixed_at: str | None
    verified_at: str | None


class FindingRecord(_FindingRequired, total=False):
    """A structured review finding (Feature 011; ingestion extras from Feature 015)."""

    imported: dict[str, Any]
    producer: dict[str, Any]
    reviewed_digest: dict[str, Any]
    promotion: dict[str, Any]
    dismiss_reason: str
    evidence_id: str


class HandoffRecord(TypedDict, total=False):
    """A review cycle's corrective handoff (Feature 011)."""

    authorized_paths: list[str]
    closed_at: str | None
    findings: list[FindingRecord]


class ReviewCycleRecord(TypedDict, total=False):
    """One ``review_cycles[]`` entry (corrective placeholders carry only the core keys)."""

    round: int
    started_at: str | None
    completed_at: str | None
    result: str | None
    context_provenance: ContextProvenance
    handoff: HandoffRecord
    # Feature 025 (v8) — the git-derived scope this round's Step-3 review covered.
    # Absent on rounds that never reached Step-3 (gate-rejected) and on pre-v8
    # cycles; ``review_role`` is "anchor" | "corrective". See specops.reviewscope.
    reviewed_range: str
    review_role: str


class _EvidenceRequired(TypedDict):
    """Mirrors ``evidence.build_record`` output exactly (Feature 012, v6)."""

    id: str
    producer: str
    command: str
    exit_code: int
    timestamp: str
    commit_range: str
    affected_paths: list[str]
    summary: str
    superseded_by: str | None


class EvidenceRecord(_EvidenceRequired, total=False):
    artifact_digest: str


class AcknowledgementRecord(TypedDict, total=False):
    """A discovered-path acknowledgement (Feature 010; shape from ``trace acknowledge``)."""

    path: str
    task: str
    reason: str
    map_digest: str | None
    at: str


class RecoveryBlock(TypedDict, total=False):
    active_task: str | None
    last_commit: str | None
    blockers: list[Any]
    last_consistent_revision: int
    last_consistent_at: str
    migrated_from_backup: str | None


class WorkflowBlock(TypedDict, total=False):
    skipped_steps: list[dict[str, Any]]


class ReviewHalt(TypedDict, total=False):
    """Feature 025 (v8) — the round-cap halt marker: the review loop reached its
    configured bound and handed control to a human. Audit-only, distinct from any
    review verdict; written only when the cap is hit."""

    at_round: int
    cap: int
    recorded_at: str


class LedgerDocument(TypedDict, total=False):
    """The top-level ``status.yaml`` mapping (schema v8; all keys additive-optional
    because supported legacy schemas may lack any of the later ones)."""

    schema_version: int
    revision: int
    feature: str
    branch: str
    baseline: str
    workflow_lane: str
    created_at: str
    updated_at: str
    current_phase: str
    active_artifact: str
    recovery: RecoveryBlock
    tasks: list[TaskRecord]
    review_cycles: list[ReviewCycleRecord]
    acknowledgements: list[AcknowledgementRecord]
    evidence: list[EvidenceRecord]
    workflow: WorkflowBlock
    promoted_from_lane: bool
    lane_provenance: dict[str, Any]
    # Feature 025 (v8) — round-cap halt marker (see ReviewHalt).
    review_halt: ReviewHalt


# Boundary alias: functions that deliberately accept untrusted/raw documents
# (validators, read-only diagnostics) take either form.
LedgerLike = LedgerDocument | dict

__all__ = [
    "AcknowledgementRecord",
    "ContextProvenance",
    "EvidenceRecord",
    "FindingRecord",
    "HandoffRecord",
    "LedgerDocument",
    "LedgerLike",
    "RecoveryBlock",
    "ReviewCycleRecord",
    "ReviewHalt",
    "TaskRecord",
    "WorkflowBlock",
]
