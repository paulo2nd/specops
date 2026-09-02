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


# Spec Kit's feature-artifact root. Hardcoded to match :func:`trace.is_managed`'s
# own ``specs/<feature>/`` hardcode; a repository that relocates the directory via
# ``SPECIFY_FEATURE_DIRECTORY`` keeps the narrower active-feature exclusion (a known
# limit — widening both is a separate change with the drift gate in its blast radius).
_SPEC_ROOT = "specs/"


def product_paths(paths: list[str], feature_name: str | None) -> list[str]:
    """Drop SpecOps/Speckit-managed artifacts from *paths*.

    Reuses the drift gate's exclusion (:func:`trace.is_managed`: ``.specify/``,
    ``specops.json``, the active feature's ``specs/<feature>/`` dir) so the reviewed
    scope and its coverage cover **product** code only — methodology bookkeeping
    (the ledger writes ``status.yaml`` every round) is neither reviewed nor able
    to block approval.

    Feature 027 widens it **for coverage only** to every ``specs/`` path, not just
    the active feature's. ``is_managed`` resolves the feature name at call time and
    the ledger keeps no rename history, so after ``specops feature rename`` the old
    directory's paths would read as product code and park themselves in the
    never-reached set — blocking approval on methodology prose. A Spec Kit feature
    directory is never product code, so the narrower rule was always more specific
    than review coverage needs. :func:`trace.is_managed` itself is unchanged, so the
    drift gate still sees another feature's artifacts.
    """
    return [
        p for p in paths
        if not trace.is_managed(p, feature_name) and not p.startswith(_SPEC_ROOT)
    ]


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
    # Feature 027: product paths changed since the baseline that NO recorded,
    # still-resolvable round reaches. Sorted, and ADDITIVE to the four fields above —
    # it does not subsume them. It sees what they cannot (a middle range a rewrite
    # orphaned, credited for a span nothing can verify); they see what it cannot (a
    # re-touch of an already-reached path after the last round is still a set member,
    # so a set difference is blind to it).
    never_reached: list[str]


def assess(
    repo: gitops.Repository,
    baseline: str,
    head: str,
    cycles: list[records.ReviewCycleRecord],
    feature_name: str | None = None,
) -> Assessment:
    """Assess whole-feature review coverage per PATH, derived from commit ranges.

    A product path changed since the baseline is **reached** when it appears in the
    diff of at least one recorded round whose range still resolves in this clone;
    ``never_reached`` is the rest. Only product paths count (managed methodology
    artifacts excluded via :func:`product_paths`).

    Soundness on an intact chain is a transitivity argument on tree comparison, not
    an assumption about how a reviewer spent its context: the rounds chain (an
    anchor's ``from`` = the baseline, a corrective's ``from`` = the prior round's
    ``to``), and if a file were identical across every segment it would be identical
    from baseline to HEAD — so a file that changed must show up in some segment, and
    ``never_reached`` is empty. No false block on a healthy history.

    This is **additive to** Feature 025's chain checks, not a replacement for them,
    and the two are genuinely complementary:

    - ``never_reached`` sees what the chain checks cannot: a middle range whose
      endpoints a squash or amend orphaned used to be credited for its whole span
      even though nothing could verify it (issue #76's silent-credit half). Such a
      range now contributes nothing and the paths it alone accounted for are named.
    - The chain checks see what ``never_reached`` cannot: a path already reached by
      an earlier round and then **re-touched** after the last one is still a member
      of the reached set, so a set difference is blind to it. ``unreviewed_tail``
      catches exactly that, and ``frontier_resolves`` fails closed when the tail
      cannot be computed at all.

    Dropping either half would reintroduce a false pass. The ``never_reached`` block
    is a deliberate narrowing of the Principle II carve-out; recovery is one
    ``handoff record-scope`` on the open round, which re-anchors over
    ``baseline..HEAD`` (orphaning always hits a chain *suffix*, so the fallback in
    :func:`specops.handoff.cmd_record_scope` always fires) — a rewrite costs a
    re-scope, never a re-review.
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
    reached: set[str] = set()
    for frm, to in recorded:
        # FR-004: credit a round only with what is still verifiable. An endpoint the
        # rewrite orphaned contributes nothing — checked explicitly rather than
        # leaning on `name_only_diff` returning [] on a non-zero git exit, because
        # "contributes no coverage" is a stated contract, not a happy accident.
        if gitops.commit_exists(repo, frm) and gitops.commit_exists(repo, to):
            reached.update(product_paths(gitops.name_only_diff(repo, frm, to), feature_name))
    return Assessment(
        has, not target, has_anchor, frontier, frontier_resolves, tail,
        sorted(set(target) - reached),
    )
