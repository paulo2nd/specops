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
class Coverage:
    """Derived (never persisted) coverage of ``baseline..HEAD`` by recorded ranges."""

    target_paths: frozenset[str]
    covered_paths: frozenset[str]
    has_scope_records: bool

    @property
    def missing_paths(self) -> list[str]:
        return sorted(self.target_paths - self.covered_paths)

    @property
    def complete(self) -> bool:
        return not self.missing_paths


def coverage(
    repo: gitops.Repository,
    baseline: str,
    head: str,
    cycles: list[records.ReviewCycleRecord],
    feature_name: str | None = None,
) -> Coverage:
    """Union path-set coverage of ``baseline..head`` by the recorded reviewed ranges.

    Only **product** paths count on both sides (managed methodology artifacts are
    excluded — :func:`product_paths`), so a ``status.yaml`` change can never block
    approval. A range whose endpoints do not both resolve in this clone is
    **dropped** (not an error) — rebase tolerance (research R7). The caller (the
    approval guard) fail-closes separately when the baseline itself is unresolvable
    while scope records exist.
    """
    target = (
        frozenset(product_paths(gitops.name_only_diff(repo, baseline, head), feature_name))
        if baseline else frozenset()
    )
    covered: set[str] = set()
    has = False
    for cycle in cycles:
        if not isinstance(cycle, dict):
            continue
        ep = _endpoints(cycle.get("reviewed_range"))
        if ep is None:
            continue
        has = True
        frm, to = ep
        if gitops.commit_exists(repo, frm) and gitops.commit_exists(repo, to):
            covered.update(product_paths(gitops.name_only_diff(repo, frm, to), feature_name))
    return Coverage(target, frozenset(covered), has)
