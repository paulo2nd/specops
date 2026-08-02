"""Regression test pinning the reconcile exemption (Feature 025, research R7 / K1).

A cycle's ``reviewed_range`` endpoints are historical review HEADs, deliberately
exempt from Principle II's registered-commit invariant: ``specops reconcile`` MUST
stay green even when an endpoint is unresolvable (a rebased-away review HEAD), so
SpecOps never blocks on an ordinary history rewrite. A future change that starts
verifying these endpoints in reconcile fails here.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from tests.conftest import cli, make_cycle


def _feature_dir(root: Path) -> Path:
    return root / "specs" / "001-demo"


def test_reconcile_green_with_unresolvable_reviewed_range(handoff_repo) -> None:
    root = handoff_repo(review_cycles=[make_cycle(round=1, result="APPROVED")])
    fp = _feature_dir(root) / "status.yaml"
    data = yaml.safe_load(fp.read_text())
    # A well-formed range whose `to` endpoint does not exist in this clone.
    data["review_cycles"][0]["reviewed_range"] = f"{data['baseline']}..{'0' * 40}"
    data["review_cycles"][0]["review_role"] = "anchor"
    fp.write_text(yaml.dump(data))

    r = cli(root, "reconcile")
    assert r.returncode == 0, r.stderr
    # The bogus endpoint is never surfaced as a reconcile violation.
    assert "0000000" not in (r.stdout + r.stderr)
