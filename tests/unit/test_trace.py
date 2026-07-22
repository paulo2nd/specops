"""Unit tests for specops.trace (Feature 010)."""
from __future__ import annotations

from pathlib import Path

from specops import trace
from tests.conftest import make_task

# ---------------------------------------------------------------------------
# US1 — Classification (T006)
# ---------------------------------------------------------------------------


def _classify(root: Path, paths: list[str]) -> dict[str, str]:
    result = trace.classify(root, explicit_paths=paths)
    assert not isinstance(result, trace.TraceResult), result
    return {r["path"]: r["class"] for r in result.paths}


def test_planned_path_is_planned(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/planned.py"])
    assert _classify(root, ["src/planned.py"])["src/planned.py"] == trace.PLANNED


def test_undeclared_path_is_unexplained(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/planned.py"])
    assert _classify(root, ["src/other.py"])["src/other.py"] == trace.UNEXPLAINED


def test_acknowledged_path_is_discovered(trace_repo) -> None:
    root = trace_repo(
        plan_paths=["src/planned.py"], tasks=[make_task("T001")],
        acks=[{"path": "src/disc.py", "task": "T001", "reason": "r",
               "map_digest": None, "at": "t"}],
    )
    assert _classify(root, ["src/disc.py"])["src/disc.py"] == trace.DISCOVERED


def test_discovery_precedence_over_planned(trace_repo) -> None:
    # A path both planned and acknowledged is classified discovered (FR-003).
    root = trace_repo(
        plan_paths=["src/foo.py"], tasks=[make_task("T001")],
        acks=[{"path": "src/foo.py", "task": "T001", "reason": "r", "map_digest": None, "at": "t"}],
    )
    assert _classify(root, ["src/foo.py"])["src/foo.py"] == trace.DISCOVERED


def test_managed_paths_excluded(trace_repo) -> None:
    root = trace_repo(plan_paths=[])
    result = trace.classify(root, explicit_paths=[
        "specs/001-demo/status.yaml", ".specify/feature.json", "specops.json", "src/real.py",
    ])
    paths = {r["path"] for r in result.paths}
    assert paths == {"src/real.py"}  # methodology-managed paths excluded (SC-003)


def test_exactly_one_class_per_path_and_counts(trace_repo) -> None:
    root = trace_repo(
        plan_paths=["src/a.py"], tasks=[make_task("T001")],
        acks=[{"path": "src/b.py", "task": "T001", "reason": "r", "map_digest": None, "at": "t"}],
    )
    result = trace.classify(root, explicit_paths=["src/a.py", "src/b.py", "src/c.py"])
    assert result.counts == {trace.PLANNED: 1, trace.DISCOVERED: 1, trace.UNEXPLAINED: 1}
    assert len(result.paths) == 3


def test_classification_is_byte_stable(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/a.py"])
    a = trace.cmd_classify(root, explicit_paths=["src/z.py", "src/a.py"]).human
    b = trace.cmd_classify(root, explicit_paths=["src/z.py", "src/a.py"]).human
    assert a == b


def test_no_map_fallback_uses_plan_paths_only(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/planned.py"])  # no context map present
    got = _classify(root, ["src/planned.py", "src/other.py"])
    assert got == {"src/planned.py": trace.PLANNED, "src/other.py": trace.UNEXPLAINED}


def test_git_derived_classify_from_diff(trace_repo) -> None:
    # Effective diff is derived from Git (ledger baseline → HEAD); a post-baseline
    # source file that is neither planned nor acknowledged is unexplained.
    root = trace_repo(plan_paths=["src/planned.py"],
                      changed={"src/planned.py": "x\n", "src/surprise.py": "y\n"})
    result = trace.classify(root)
    assert not isinstance(result, trace.TraceResult)
    classes = {r["path"]: r["class"] for r in result.paths}
    assert classes == {"src/planned.py": trace.PLANNED, "src/surprise.py": trace.UNEXPLAINED}


def test_git_derived_symlink_matched_by_own_path(trace_repo) -> None:
    import os
    import subprocess
    root = trace_repo(plan_paths=[])
    os.symlink("target.py", root / "link.py")  # a symlink, not a regular file
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "link"], cwd=root, check=True, capture_output=True)
    result = trace.classify(root)
    assert not isinstance(result, trace.TraceResult)
    classes = {r["path"]: r["class"] for r in result.paths}
    # the symlink is classified by its own path entry (git does not follow it)
    assert classes.get("link.py") == trace.UNEXPLAINED


def test_resolve_baseline_merge_base_fallback(tmp_git_repo: Path) -> None:
    # No ledger baseline recorded → fall back to the merge-base with the default
    # branch (Finding 4), so classification still works.
    import subprocess

    import yaml

    from specops import gitops
    from tests.conftest import make_trace_ledger
    root = tmp_git_repo
    default = gitops.current_branch(gitops.find_repo(root))
    (root / ".specify").mkdir(exist_ok=True)
    (root / ".specify" / "feature.json").write_text('{"feature_directory": "specs/001-demo"}')
    fd = root / "specs" / "001-demo"
    fd.mkdir(parents=True)
    (fd / "plan.md").write_text("# Plan\n")
    led = make_trace_ledger(feature="001-demo", branch="feat", baseline="")  # empty baseline
    (fd / "status.yaml").write_text(yaml.dump(led))
    subprocess.run(["git", "checkout", "-b", "feat"], cwd=root, check=True, capture_output=True)
    (root / "app.py").write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "work"], cwd=root, check=True, capture_output=True)
    repo = gitops.find_repo(root)
    assert default in ("main", "master")  # fixture's default branch is resolvable
    base = trace.resolve_baseline(root, repo)
    assert base is not None  # derived from merge-base, not None


def test_classify_usage_error_not_a_repo(tmp_path: Path) -> None:
    (tmp_path / ".specify").mkdir()
    (tmp_path / ".specify" / "feature.json").write_text('{"feature_directory": "specs/x"}')
    (tmp_path / "specs" / "x").mkdir(parents=True)
    result = trace.classify(tmp_path)  # git-derived, no repo
    assert isinstance(result, trace.TraceResult)
    assert result.status == trace.USAGE_ERROR
    assert result.exit_code == 2


# ---------------------------------------------------------------------------
# US2 — Acknowledgement (T012)
# ---------------------------------------------------------------------------


def _acks(root: Path) -> list:
    from specops import ledger
    return ledger.load_raw(root / "specs" / "001-demo").get("acknowledgements") or []


def test_acknowledge_records(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/p.py"], tasks=[make_task("T001", status="IN_PROGRESS")])
    r = trace.cmd_acknowledge(root, "src/disc.py", task="T001", reason="moved during T001")
    assert r.status == trace.ACK_RECORDED and r.exit_code == 0
    recs = _acks(root)
    assert len(recs) == 1 and recs[0]["path"] == "src/disc.py"


def test_acknowledge_idempotent(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    trace.cmd_acknowledge(root, "src/d.py", task="T001", reason="r")
    r = trace.cmd_acknowledge(root, "src/d.py", task="T001", reason="r")
    assert r.status == trace.ACK_IDEMPOTENT and r.exit_code == 0
    assert len(_acks(root)) == 1


def test_acknowledge_conflict(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS"),
                                            make_task("T002", status="PENDING")])
    trace.cmd_acknowledge(root, "src/d.py", task="T001", reason="r")
    r = trace.cmd_acknowledge(root, "src/d.py", task="T002", reason="different")
    assert r.status == trace.ACK_CONFLICT and r.exit_code == 2
    recs = _acks(root)
    assert len(recs) == 1 and recs[0]["task"] == "T001"  # prior untouched


def test_acknowledge_unknown_task(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    r = trace.cmd_acknowledge(root, "src/d.py", task="T999", reason="r")
    assert r.status == trace.ACK_UNKNOWN_TASK and r.exit_code == 2
    assert _acks(root) == []  # nothing written


def test_acknowledge_normalizes_path(trace_repo) -> None:
    # `./src/foo.py` is stored normalized so it matches Git-reported `src/foo.py`.
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    r = trace.cmd_acknowledge(root, "./src/foo.py", task="T001", reason="r")
    assert r.status == trace.ACK_RECORDED
    assert _acks(root)[0]["path"] == "src/foo.py"
    assert _classify(root, ["src/foo.py"])["src/foo.py"] == trace.DISCOVERED


def test_non_active_feature_specs_path_is_classified(trace_repo) -> None:
    # Only the ACTIVE feature dir under specs/ is excluded; other specs/ paths
    # (e.g. product schemas) are still classified (Finding 7).
    root = trace_repo(plan_paths=[])
    got = _classify(root, ["specs/api/openapi.yaml", "specs/001-demo/status.yaml"])
    assert got == {"specs/api/openapi.yaml": trace.UNEXPLAINED}  # active feature excluded


def test_classify_and_validate_agree_on_unaccounted_owner(trace_repo) -> None:
    from specops import contextmap
    from tests.conftest import load_map_fixture
    root = trace_repo(
        spec_scs=["SC-001"], plan_paths=[],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", commits=["a" * 40])],
        changed={"src/api/foo.py": "x\n"},
    )
    mp = contextmap.map_path(root)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(load_map_fixture("contradictory_ownership.yaml"))
    # classify calls it unexplained AND validate emits contradictory-ownership —
    # the two commands agree (Finding 2).
    result = trace.classify(root)
    classes = {r["path"]: r["class"] for r in result.paths}
    assert classes["src/api/foo.py"] == trace.UNEXPLAINED
    kinds = {d["kind"] for d in trace.validate_trace(root)}
    assert "contradictory-ownership" in kinds


def test_acknowledge_already_planned_is_noop(trace_repo) -> None:
    root = trace_repo(plan_paths=["src/planned.py"],
                      tasks=[make_task("T001", status="IN_PROGRESS")])
    r = trace.cmd_acknowledge(root, "src/planned.py", task="T001", reason="r")
    assert r.status == trace.ACK_ALREADY_PLANNED and r.exit_code == 0
    assert _acks(root) == []


# ---------------------------------------------------------------------------
# US3 — Trace graph, report, validation (T016, T017)
# ---------------------------------------------------------------------------


def test_report_marks_completed_sc_and_lists_discoveries(trace_repo) -> None:
    root = trace_repo(
        spec_scs=["SC-001"], plan_paths=[],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", commits=["a" * 40])],
        acks=[{"path": "src/d.py", "task": "T001", "reason": "why", "map_digest": None, "at": "t"}],
    )
    r = trace.cmd_report(root)
    assert r.status == trace.TRACE_OK
    graph = r.extra["graph"]
    sc = next(s for s in graph["success_criteria"] if s["sc"] == "SC-001")
    assert sc["completed"] is True
    assert "Discoveries:" in r.human and "src/d.py" in r.human


def test_validate_complete_trace_has_no_defects(trace_repo) -> None:
    root = trace_repo(
        spec_scs=["SC-001"], plan_paths=[],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", evidence="CLI_LOG:ok", commits=["a" * 40])],
    )
    # commit sha 'aaaa...' will not exist → allow only that dangling ref; assert the
    # deterministic defects instead: no uncovered-sc / missing-link.
    defects = trace.validate_trace(root)
    kinds = {d["kind"] for d in defects}
    assert "uncovered-sc" not in kinds
    assert "missing-link" not in kinds


def test_validate_uncovered_sc(trace_repo) -> None:
    root = trace_repo(
        spec_scs=["SC-001", "SC-002"], plan_paths=[],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", commits=["a" * 40])],
    )
    defects = trace.validate_trace(root)
    assert any(d["kind"] == "uncovered-sc" and d["ref"] == "SC-002" for d in defects)


def test_validate_missing_link_no_evidence(trace_repo) -> None:
    root = trace_repo(
        spec_scs=["SC-001"], plan_paths=[],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", evidence=None, commits=["a" * 40])],
    )
    defects = trace.validate_trace(root)
    assert any(d["kind"] == "missing-link" and d["ref"] == "T001" for d in defects)


def test_validate_missing_link_no_commit_for_story(trace_repo) -> None:
    root = trace_repo(
        spec_scs=["SC-001"], plan_paths=[],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", evidence="CLI_LOG:ok", commits=[])],
    )
    defects = trace.validate_trace(root)
    assert any(d["kind"] == "missing-link" and d["ref"] == "US1" for d in defects)


def test_validate_contradictory_ownership(trace_repo) -> None:
    from specops import contextmap
    from tests.conftest import load_map_fixture
    root = trace_repo(
        spec_scs=["SC-001"], plan_paths=[],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", commits=["a" * 40])],
        changed={"src/api/foo.py": "x\n"},
    )
    # map owns src/api/** under context 'api', which no plan/task declares/associates
    mp = contextmap.map_path(root)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(load_map_fixture("contradictory_ownership.yaml"))
    defects = trace.validate_trace(root)
    assert any(
        d["kind"] == "contradictory-ownership" and d["ref"] == "src/api/foo.py"
        for d in defects
    )


def test_validate_dangling_acknowledgement_reference(trace_repo) -> None:
    root = trace_repo(
        spec_scs=["SC-001"], plan_paths=[],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", commits=["a" * 40])],
        acks=[{"path": "src/x.py", "task": "T404", "reason": "r", "map_digest": None, "at": "t"}],
    )
    defects = trace.validate_trace(root)
    assert any(d["kind"] == "dangling-reference" and "T404" in d["detail"] for d in defects)
