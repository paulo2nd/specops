"""Reviewed-scope derivation and union coverage for the semantic review loop (Feature 025).

Pure logic, no ledger or CLI I/O: given the ledger's review cycles plus a git
repository, derive a round's **reviewed range** (an *anchor* round covers
``baseline..HEAD``; a *corrective* round covers ``prev_scoped_to..HEAD``) and
compute whether the union of the recorded reviewed ranges covers the current
``baseline..HEAD`` effective diff. This mirrors how :mod:`specops.evidence` and
:mod:`specops.trace` isolate git-derived logic from the ``status``/``handoff``
orchestration and the ``cli`` surface.

The reviewed-range endpoints are **git-derived, never reviewer-supplied**
(FR-001/SC-006), and are deliberately exempt from the ``reconcile``
registered-commit invariant (research R7): the coverage math drops any range
whose endpoints no longer resolve (a rebased-away review HEAD) and re-derives
against the current baseline/HEAD, so SpecOps never blocks on an ordinary
history rewrite.
"""
from __future__ import annotations

from dataclasses import dataclass

from specops import gitops, records, trace

# Review-role vocabulary (mirrored as string literals in the ledger validator).
ANCHOR = "anchor"
CORRECTIVE = "corrective"


def product_paths(paths: list[str], feature_name: str | None) -> list[str]:
    """Drop SpecOps/Speckit-managed artifacts (``.specify/``, ``specops.json``, the
    active feature's ``specs/<feature>/`` dir) from *paths*.

    Reuses the drift gate's exclusion (:func:`trace.is_managed`) so the reviewed
    scope and its coverage cover **product** code only — methodology bookkeeping
    (the ledger writes ``status.yaml`` every round) is neither reviewed nor able
    to block approval.
    """
    return [p for p in paths if not trace.is_managed(p, feature_name)]


@dataclass(frozen=True)
class DerivedRange:
    """A round's derived reviewed range: its role and ``<from>..<to>`` endpoints."""

    review_role: str  # ANCHOR | CORRECTIVE
    from_commit: str
    to_commit: str

    @property
    def range_str(self) -> str:
        return f"{self.from_commit}..{self.to_commit}"


def _endpoints(reviewed_range: object) -> tuple[str, str] | None:
    """The ``(from, to)`` of a well-formed ``"<from>..<to>"`` range, else None."""
    if isinstance(reviewed_range, str) and reviewed_range.count("..") == 1:
        a, b = reviewed_range.split("..", 1)
        if a and b:
            return a, b
    return None


def has_any_scope(cycles: list[records.ReviewCycleRecord]) -> bool:
    """True when any cycle carries a well-formed ``reviewed_range`` (the degradation
    switch: absence keeps the prior cycle-result approval behavior — FR-008)."""
    return any(
        isinstance(c, dict) and _endpoints(c.get("reviewed_range")) is not None
        for c in cycles
    )


def derive_range(
    baseline: str, head: str, cycles: list[records.ReviewCycleRecord]
) -> DerivedRange:
    """Derive the current round's reviewed range.

    The current round is the **last** cycle; a round is an *anchor* when no
    EARLIER cycle carries a ``reviewed_range`` (``from = baseline``), otherwise
    *corrective* (``from`` = the most recent earlier cycle's ``reviewed_range``
    ``to``). Idempotent by construction: the current round's own prior record is
    excluded, so re-running recomputes the same role against the current HEAD.
    """
    prior_to: str | None = None
    for cycle in cycles[:-1]:
        ep = _endpoints(cycle.get("reviewed_range")) if isinstance(cycle, dict) else None
        if ep is not None:
            prior_to = ep[1]
    if prior_to is None:
        return DerivedRange(ANCHOR, baseline, head)
    return DerivedRange(CORRECTIVE, prior_to, head)


@dataclass(frozen=True)
class Assessment:
    """Derived (never persisted) verdict on whether the recorded review rounds
    cover the whole feature at HEAD."""

    has_scope_records: bool     # any round recorded a well-formed reviewed_range
    target_empty: bool          # no product change in baseline..HEAD (nothing to review)
    has_anchor: bool            # some recorded range starts at the current baseline
    frontier: str | None        # the last recorded round's `to` endpoint
    frontier_resolves: bool     # that endpoint still exists in this clone
    unreviewed_tail: list[str]  # product paths changed after the frontier (frontier..HEAD)


def assess(
    repo: gitops.Repository,
    baseline: str,
    head: str,
    cycles: list[records.ReviewCycleRecord],
    feature_name: str | None = None,
) -> Assessment:
    """Assess whole-feature review coverage by COMMIT reach, not by path names.

    Each round reviews the full effective diff of its ``from..to`` range, and the
    rounds chain (an anchor's ``from`` = the baseline; a corrective's ``from`` =
    the prior round's ``to``), so the recorded rounds jointly cover
    ``baseline..frontier`` where ``frontier`` is the **last** recorded ``to``. The
    feature is fully reviewed iff an anchor exists (the chain starts at the current
    baseline) and no product change lands after the frontier (``frontier..HEAD`` is
    empty). Only product paths count (managed methodology artifacts excluded via
    :func:`product_paths`).

    This is robust both ways — the two defects a path-set union had: a pruned
    INTERMEDIATE review HEAD is never re-diffed (no false block on a benign rewrite),
    and a commit landing on an already-reviewed file *after* the last review is
    caught by the tail (no false pass on unreviewed code).
    """
    recorded = [
        ep for c in cycles
        if isinstance(c, dict) and (ep := _endpoints(c.get("reviewed_range"))) is not None
    ]
    has = bool(recorded)
    target = (
        product_paths(gitops.name_only_diff(repo, baseline, head), feature_name)
        if baseline else []
    )
    has_anchor = bool(baseline) and any(frm == baseline for frm, _to in recorded)
    frontier = recorded[-1][1] if recorded else None
    frontier_resolves = frontier is not None and gitops.commit_exists(repo, frontier)
    tail = (
        product_paths(gitops.name_only_diff(repo, frontier, head), feature_name)
        if frontier_resolves and frontier is not None else []
    )
    return Assessment(has, not target, has_anchor, frontier, frontier_resolves, tail)
