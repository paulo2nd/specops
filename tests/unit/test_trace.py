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


# --- out-of-feature acknowledgement (issue #63) ----------------------------


def test_acknowledge_out_of_feature_records_without_task(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    r = trace.cmd_acknowledge(root, "skills/foo.md", reason="supports dev", out_of_feature=True)
    assert r.status == trace.ACK_RECORDED and r.exit_code == 0
    recs = _acks(root)
    assert len(recs) == 1
    assert recs[0]["out_of_feature"] is True
    assert "task" not in recs[0]           # tooling ack carries no task
    # the path is now discovered-and-acknowledged, so the drift gate passes
    assert _classify(root, ["skills/foo.md"])["skills/foo.md"] == trace.DISCOVERED


def test_acknowledge_extra_shape_is_mode_specific(trace_repo) -> None:
    # task-bound ack keeps {path, task} (no out_of_feature key); out-of-feature omits task
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    tb = trace.cmd_acknowledge(root, "src/d.py", task="T001", reason="r")
    assert "out_of_feature" not in tb.extra and tb.extra["task"] == "T001"
    oof = trace.cmd_acknowledge(root, "skills/y.md", reason="r", out_of_feature=True)
    assert oof.extra["out_of_feature"] is True and "task" not in oof.extra


def test_report_labels_out_of_feature_discovery(trace_repo) -> None:
    root = trace_repo(spec_scs=["SC-001"], plan_paths=[],
                      tasks=[make_task("T001", status="IN_PROGRESS")])
    trace.cmd_acknowledge(root, "skills/tool.md", reason="supports dev", out_of_feature=True)
    r = trace.cmd_report(root)
    assert "out-of-feature: supports dev" in r.human
    assert "task None" not in r.human  # the field survives build_graph, so no dead label
    ack = next(a for a in r.extra["graph"]["acknowledgements"] if a["path"] == "skills/tool.md")
    assert ack["out_of_feature"] is True


def test_acknowledge_out_of_feature_rejects_task(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    r = trace.cmd_acknowledge(root, "skills/foo.md", task="T001", reason="r", out_of_feature=True)
    assert r.status == trace.USAGE_ERROR
    assert _acks(root) == []


def test_acknowledge_requires_task_or_out_of_feature(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    r = trace.cmd_acknowledge(root, "skills/foo.md", reason="r")
    assert r.status == trace.USAGE_ERROR
    assert _acks(root) == []


def test_acknowledge_out_of_feature_idempotent(trace_repo) -> None:
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    trace.cmd_acknowledge(root, "agents/x.md", reason="r", out_of_feature=True)
    r = trace.cmd_acknowledge(root, "agents/x.md", reason="r", out_of_feature=True)
    assert r.status == trace.ACK_IDEMPOTENT
    assert len(_acks(root)) == 1


def test_acknowledge_mode_conflict(trace_repo) -> None:
    # same path acknowledged out-of-feature then as task-bound → conflict, unchanged
    root = trace_repo(plan_paths=[], tasks=[make_task("T001", status="IN_PROGRESS")])
    trace.cmd_acknowledge(root, "skills/x.md", reason="r", out_of_feature=True)
    r = trace.cmd_acknowledge(root, "skills/x.md", task="T001", reason="r")
    assert r.status == trace.ACK_CONFLICT
    assert len(_acks(root)) == 1 and _acks(root)[0]["out_of_feature"] is True


def test_out_of_feature_ack_is_not_a_dangling_reference(trace_repo) -> None:
    root = trace_repo(
        spec_scs=["SC-001"], plan_paths=[],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", commits=["a" * 40])],
    )
    trace.cmd_acknowledge(root, "skills/foo.md", reason="tooling", out_of_feature=True)
    # the taskless ack must not read as a dangling task reference (the fake seed
    # commit "a"*40 is a separate, expected commit dangling-reference)
    assert not any(
        d["kind"] == "dangling-reference" and "acknowledgement" in d["detail"]
        for d in trace.validate_trace(root)
    )


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


# ---------------------------------------------------------------------------
# Commit linkage — `trace link` (issue #62)
# ---------------------------------------------------------------------------


def _work_head(root: Path) -> str:
    """Full sha of the fixture's `changed` "work" commit (current HEAD)."""
    from tests.conftest import git
    return git(root, "rev-parse", "HEAD")


def _seed_missing_link(trace_repo):
    """A DONE story with no bound commit (the #62 gap) plus a real commit to link."""
    return trace_repo(
        spec_scs=["SC-001"], plan_paths=["src/x.py"],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", evidence="CLI_LOG:ok", commits=[])],
        changed={"src/x.py": "print()\n"},
    )


def test_link_records_and_clears_missing_link(trace_repo) -> None:
    root = _seed_missing_link(trace_repo)
    sha = _work_head(root)
    # gap present before linking
    assert any(d["kind"] == "missing-link" and d["ref"] == "US1"
               for d in trace.validate_trace(root))

    r = trace.cmd_link(root, task="T001", commits=[sha])
    assert r.status == trace.LINK_RECORDED
    assert r.extra["commits"] == [sha]
    # gap cleared, and the linked sha does not introduce a dangling-reference
    kinds = {d["kind"] for d in trace.validate_trace(root)}
    assert "missing-link" not in kinds
    assert "dangling-reference" not in kinds


def test_link_runs_on_done_task_and_persists(trace_repo) -> None:
    import yaml
    root = _seed_missing_link(trace_repo)  # task is DONE — complete-task would refuse it
    sha = _work_head(root)
    assert trace.cmd_link(root, task="T001", commits=[sha]).status == trace.LINK_RECORDED
    # durable on disk in full-sha form
    ledger = yaml.safe_load((root / "specs" / "001-demo" / "status.yaml").read_text())
    task = next(t for t in ledger["tasks"] if t["id"] == "T001")
    assert task["commits"] == [sha]
    # a second call re-reads that state and is a no-op
    assert trace.cmd_link(root, task="T001", commits=[sha]).status == trace.LINK_IDEMPOTENT


def test_link_resolves_short_sha_to_full(trace_repo) -> None:
    root = _seed_missing_link(trace_repo)
    sha = _work_head(root)
    r = trace.cmd_link(root, task="T001", commits=[sha[:8]])
    assert r.status == trace.LINK_RECORDED
    assert r.extra["commits"] == [sha]  # stored full, not the abbreviation


def test_link_union_preserves_existing(trace_repo) -> None:
    # task already carries a prior (here unresolvable/legacy) sha; linking a new one
    # unions — the existing binding is preserved (tolerated, kept last), never dropped
    root = trace_repo(
        spec_scs=["SC-001"], plan_paths=["src/x.py"],
        tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
        tasks=[make_task("T001", status="DONE", commits=["a" * 40])],
        changed={"src/x.py": "print()\n"},
    )
    sha = _work_head(root)
    r = trace.cmd_link(root, task="T001", commits=[sha])
    assert r.status == trace.LINK_RECORDED
    assert r.extra["added"] == [sha]
    assert set(r.extra["commits"]) == {"a" * 40, sha}   # existing preserved
    assert r.extra["commits"][0] == sha                 # resolvable sorted ahead of dangling


def test_link_dedups_within_invocation(trace_repo) -> None:
    # the same commit supplied twice (as short + full spellings) is stored once
    root = _seed_missing_link(trace_repo)
    sha = _work_head(root)
    r = trace.cmd_link(root, task="T001", commits=[sha, sha[:8]])
    assert r.status == trace.LINK_RECORDED
    assert r.extra["commits"] == [sha]


def test_link_stores_union_newest_first(trace_repo) -> None:
    # supplied oldest-first, persisted newest-first (commits[0] is HEAD-most)
    from tests.conftest import git
    root = _seed_missing_link(trace_repo)
    head = _work_head(root)
    baseline = git(root, "rev-parse", "HEAD~1")
    r = trace.cmd_link(root, task="T001", commits=[baseline, head])
    assert r.status == trace.LINK_RECORDED
    assert r.extra["commits"] == [head, baseline]


def test_link_idempotent_message_reports_total_bindings(trace_repo) -> None:
    root = _seed_missing_link(trace_repo)
    sha = _work_head(root)
    trace.cmd_link(root, task="T001", commits=[sha])
    r = trace.cmd_link(root, task="T001", commits=[sha])
    assert r.status == trace.LINK_IDEMPOTENT
    assert "1 binding(s) total" in r.human


def test_link_unknown_task(trace_repo) -> None:
    root = _seed_missing_link(trace_repo)
    sha = _work_head(root)
    r = trace.cmd_link(root, task="T999", commits=[sha])
    assert r.status == trace.LINK_UNKNOWN_TASK


def test_link_bad_commit_rejected(trace_repo) -> None:
    root = _seed_missing_link(trace_repo)
    r = trace.cmd_link(root, task="T001", commits=["deadbeef" * 5])
    assert r.status == trace.LINK_BAD_COMMIT


def test_link_requires_task_and_commit(trace_repo) -> None:
    root = _seed_missing_link(trace_repo)
    assert trace.cmd_link(root, task="T001", commits=[]).status == trace.USAGE_ERROR
    assert trace.cmd_link(root, task="", commits=["a" * 40]).status == trace.USAGE_ERROR


# --- Feature 026 (T033): amendment provenance in the trace report -------------


def _amended_ledger_tasks() -> list[dict]:
    """One amended task (T001) and one ordinarily-closed task (T002)."""
    return [
        {"id": "T001", "status": "DONE", "started_commit": None, "commits": [],
         "evidence": "TEST_REPORT:verified later", "completed_at": "2026-09-01T00:00:00+00:00",
         "evidence_refs": ["EV-original0001", "EV-amendment01"]},
        {"id": "T002", "status": "DONE", "started_commit": None, "commits": [],
         "evidence": "CLI_LOG:ordinary close", "completed_at": "2026-09-01T00:00:00+00:00",
         "evidence_refs": ["EV-plainclose1"]},
    ]


def _amended_ledger_evidence() -> list[dict]:
    base = {
        "producer": "auto", "command": "c", "exit_code": 0,
        "timestamp": "2026-09-01T00:00:00+00:00", "commit_range": "a..b",
        "affected_paths": [], "superseded_by": None,
    }
    return [
        {**base, "id": "EV-original0001", "summary": "CLI_LOG:placeholder",
         "superseded_by": "EV-amendment01"},
        {**base, "id": "EV-amendment01", "summary": "TEST_REPORT:verified later",
         "producer": "amend", "amendment": True, "reason": "no gate run at close"},
        {**base, "id": "EV-plainclose1", "summary": "CLI_LOG:ordinary close"},
    ]


def _amended_repo(trace_repo) -> Path:
    import yaml as _yaml

    root = trace_repo(tasks=_amended_ledger_tasks(),
                      tasks_md_tasks=["- [ ] T001 [SC-001] a", "- [ ] T002 [SC-001] b"])
    fd = root / "specs" / "001-demo"
    data = _yaml.safe_load((fd / "status.yaml").read_text())
    data["evidence"] = _amended_ledger_evidence()
    (fd / "status.yaml").write_text(_yaml.dump(data))
    return root


def test_trace_report_marks_an_amended_task(trace_repo) -> None:
    """FR-006: an amended close is never rendered as an original one."""
    graph = trace.build_graph(_amended_repo(trace_repo))
    t1 = next(t for t in graph["tasks"] if t["id"] == "T001")
    assert t1["evidence_amended"] is True
    assert t1["evidence"] == "TEST_REPORT:verified later"


def test_trace_report_lists_the_superseded_history(trace_repo) -> None:
    graph = trace.build_graph(_amended_repo(trace_repo))
    t1 = next(t for t in graph["tasks"] if t["id"] == "T001")
    assert t1["evidence_history"] == ["EV-original0001"]


def test_trace_report_omits_the_keys_for_an_ordinary_close(trace_repo) -> None:
    """Absence is what identifies an original — a consumer reading a pre-026 report
    sees exactly what it saw before."""
    graph = trace.build_graph(_amended_repo(trace_repo))
    t2 = next(t for t in graph["tasks"] if t["id"] == "T002")
    assert "evidence_amended" not in t2
    assert "evidence_history" not in t2


# ---------------------------------------------------------------------------
# Feature 027 containment: the drift gate's exclusion is NOT widened
# ---------------------------------------------------------------------------


def test_is_managed_keeps_the_narrow_active_feature_exclusion() -> None:
    """Feature 027 widens the exclusion for review COVERAGE only
    (`reviewscope.product_paths`). `trace.is_managed` — which the drift gate reads —
    must keep dropping only the ACTIVE feature's spec dir, so a change to another
    feature's artifacts stays visible to drift."""
    assert trace.is_managed(".specify/memory/constitution.md")
    assert trace.is_managed("specops.json")
    assert trace.is_managed("specs/027-active/spec.md", "027-active")
    # The narrow behavior: another feature's spec dir is NOT managed here.
    assert not trace.is_managed("specs/003-other/spec.md", "027-active")
    assert not trace.is_managed("specs/003-other/spec.md", None)
    assert not trace.is_managed("src/product.py", "027-active")
