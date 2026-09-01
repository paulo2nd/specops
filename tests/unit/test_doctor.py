"""Unit tests for the doctor module (Feature 014): contract + per-domain checks.

Covers the foundational verdict/exit contract (T005) and each diagnostic domain's
severity + next_action_code (T012). Every doctor call is read-only and root-parameterized.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specops import doctor, ledger
from tests.conftest import write_map, write_profiles, write_second_feature

# ---------------------------------------------------------------------------
# Foundational contract (T005) — severity rollup, exit mapping, determinism
# ---------------------------------------------------------------------------


def test_domain_severity_rollup_is_the_worst_finding() -> None:
    d = doctor.DomainResult("x", [
        doctor.Finding(doctor.OK, "a"),
        doctor.Finding(doctor.WARNING, "b", doctor.NA_FIX_CONFIG, "do", "b"),
        doctor.Finding(doctor.OK, "c"),
    ])
    assert d.severity == doctor.WARNING


def test_verdict_to_exit_code_mapping() -> None:
    assert doctor.DoctorResult("doctor", doctor.OK, "", {}).exit_code == 0
    assert doctor.DoctorResult("doctor", doctor.WARNING, "", {}).exit_code == 0
    assert doctor.DoctorResult("doctor", doctor.BLOCKING, "", {}).exit_code == 1
    assert doctor.DoctorResult("doctor", doctor.EXECUTION_ERROR, "", {}).exit_code == 2


def test_findings_serialize_in_stable_sorted_order() -> None:
    d = doctor.DomainResult("x", [
        doctor.Finding(doctor.WARNING, "zzz", doctor.NA_FIX_CONFIG, "do", "b2"),
        doctor.Finding(doctor.WARNING, "aaa", doctor.NA_FIX_CONFIG, "do", "b1"),
    ])
    ids = [f["id"] for f in d.as_json()["findings"]]
    assert ids == ["b1", "b2"]  # sorted by (id, message)


def test_doctor_json_is_byte_identical_across_runs(doctor_healthy_repo: Path) -> None:
    a = doctor.doctor_json(doctor.cmd_doctor(doctor_healthy_repo))
    b = doctor.doctor_json(doctor.cmd_doctor(doctor_healthy_repo))
    assert a == b


# ---------------------------------------------------------------------------
# Per-domain checks (T012)
# ---------------------------------------------------------------------------


def _domains(root: Path) -> dict[str, dict]:
    result = doctor.cmd_doctor(root)
    return {d["domain"]: d for d in result.extra["domains"]}


def _ledger_path(root: Path) -> Path:
    return root / "specs" / "001-demo" / "status.yaml"


def test_healthy_repo_all_domains_ok(doctor_healthy_repo: Path) -> None:
    result = doctor.cmd_doctor(doctor_healthy_repo)
    assert result.status == doctor.OK
    assert result.exit_code == 0
    domains = {d["domain"]: d for d in result.extra["domains"]}
    assert len(domains) == 10  # SC-002: every domain reported
    assert all(d["severity"] == doctor.OK for d in domains.values())


def test_too_new_ledger_is_blocking(doctor_healthy_repo: Path) -> None:
    data = yaml.safe_load(_ledger_path(doctor_healthy_repo).read_text())
    data["schema_version"] = ledger.CURRENT_SCHEMA + 92
    _ledger_path(doctor_healthy_repo).write_text(yaml.dump(data))
    dom = _domains(doctor_healthy_repo)["ledger"]
    assert dom["severity"] == doctor.BLOCKING
    assert dom["findings"][0]["next_action_code"] == doctor.NA_LEDGER_UNSUPPORTED


def test_migratable_ledger_is_warning(doctor_healthy_repo: Path) -> None:
    data = yaml.safe_load(_ledger_path(doctor_healthy_repo).read_text())
    data["schema_version"] = 5
    _ledger_path(doctor_healthy_repo).write_text(yaml.dump(data))
    dom = _domains(doctor_healthy_repo)["ledger"]
    assert dom["severity"] == doctor.WARNING
    assert dom["findings"][0]["next_action_code"] == doctor.NA_RUN_STATUS_MIGRATE


def test_corrupt_ledger_is_execution_error(doctor_healthy_repo: Path) -> None:
    _ledger_path(doctor_healthy_repo).write_text(":\n  - [broken yaml")
    dom = _domains(doctor_healthy_repo)["ledger"]
    assert dom["severity"] == doctor.EXECUTION_ERROR
    assert dom["findings"][0]["next_action_code"] == doctor.NA_REPAIR_UNREADABLE_INPUT


def test_no_active_feature_is_ok(context_map_repo: Path) -> None:
    # context_map_repo has a Spec Kit layout but no feature.json and no specs/ dir,
    # so no active feature resolves — a supported `ok` resting state (FR-010).
    dom = _domains(context_map_repo)["feature_identity"]
    assert dom["severity"] == doctor.OK
    assert dom["findings"][0]["next_action_code"] == doctor.NA_START_OR_SELECT_FEATURE
    # And the overall verdict is unaffected by having no active feature.
    assert doctor.cmd_doctor(context_map_repo).extra["verdict"] in (doctor.OK, doctor.WARNING)


def test_ambiguous_identity_is_blocking(doctor_healthy_repo: Path) -> None:
    data = yaml.safe_load(_ledger_path(doctor_healthy_repo).read_text())
    data["baseline"] = "0" * 40  # a sha that is not an ancestor of HEAD
    _ledger_path(doctor_healthy_repo).write_text(yaml.dump(data))
    dom = _domains(doctor_healthy_repo)["feature_identity"]
    assert dom["severity"] == doctor.BLOCKING
    assert dom["findings"][0]["next_action_code"] == doctor.NA_RESOLVE_IDENTITY


def test_invalid_context_map_is_blocking(doctor_healthy_repo: Path) -> None:
    write_map(doctor_healthy_repo, {
        "schema_version": 1,
        "contexts": [
            {"id": "a", "match": ["src/a/**"], "reads": {"base": ["src/a"]}, "dependencies": ["b"]},
            {"id": "b", "match": ["src/b/**"], "reads": {"base": ["src/b"]}, "dependencies": ["a"]},
        ],
    })
    dom = _domains(doctor_healthy_repo)["context_map"]
    assert dom["severity"] == doctor.BLOCKING
    assert dom["findings"][0]["next_action_code"] == doctor.NA_FIX_CONTEXT_MAP


def test_unavailable_gate_command_is_warning(doctor_healthy_repo: Path) -> None:
    write_profiles(doctor_healthy_repo, {
        "output_version": 1,
        "profiles": [
            {"name": "unit", "command": "this-executable-does-not-exist-xyz --run",
             "applies": {"always": True}, "timeout": 60},
        ],
    })
    dom = _domains(doctor_healthy_repo)["gate_availability"]
    assert dom["severity"] == doctor.WARNING
    assert dom["findings"][0]["next_action_code"] == doctor.NA_INSTALL_GATE_COMMAND


def test_ledger_commit_absent_from_tree_is_workflow_divergence(doctor_healthy_repo: Path) -> None:
    data = yaml.safe_load(_ledger_path(doctor_healthy_repo).read_text())
    data["tasks"] = [{"id": "T001", "status": "DONE", "evidence": "CLI_LOG:ok",
                      "commits": ["f" * 40]}]
    _ledger_path(doctor_healthy_repo).write_text(yaml.dump(data))
    dom = _domains(doctor_healthy_repo)["workflow_divergence"]
    assert dom["severity"] == doctor.BLOCKING
    assert dom["findings"][0]["next_action_code"] == doctor.NA_RECONCILE


def test_blocking_handoff_finding_makes_ledger_blocking(handoff_repo) -> None:
    from tests.conftest import make_cycle, make_finding
    root = handoff_repo(review_cycles=[make_cycle(findings=[make_finding("F1", state="OPEN")])])
    dom = _domains(root)["ledger"]
    assert dom["severity"] == doctor.BLOCKING
    codes = {f["next_action_code"] for f in dom["findings"]}
    assert doctor.NA_VERIFY_BLOCKING in codes


def test_non_utf8_ledger_does_not_crash(doctor_healthy_repo: Path) -> None:
    # Regression (review finding 1): a non-UTF8 status.yaml raises UnicodeDecodeError
    # from load_raw — outside the per-domain _run guard — which must not crash doctor.
    _ledger_path(doctor_healthy_repo).write_bytes(b"\xff\xfe not utf8")
    result = doctor.cmd_doctor(doctor_healthy_repo)  # must not raise
    dom = {d["domain"]: d for d in result.extra["domains"]}["ledger"]
    assert dom["severity"] == doctor.EXECUTION_ERROR
    assert result.exit_code == 2


def test_active_feature_scope_ignores_other_features(doctor_healthy_repo: Path) -> None:
    # FR-012a: a second, broken (too-new) feature ledger must never be inspected.
    write_second_feature(doctor_healthy_repo, schema_version=99)
    result = doctor.cmd_doctor(doctor_healthy_repo)
    assert result.status == doctor.OK  # still healthy — 002-other is not scanned
    blob = doctor.doctor_json(result)
    assert "002-other" not in blob


# ---------------------------------------------------------------------------
# Feature 026 — doctor names the active-feature resolution, and fails on a broken one
# ---------------------------------------------------------------------------


def _resolution_repo(tmp_path: Path, *, pointer: str | None,
                     features: tuple[str, ...] = ("001-old", "002-newer")) -> Path:
    """A Spec Kit layout with `features` present and `pointer` as the stored value."""
    import json as _json
    import subprocess as _sp

    root = tmp_path / "repo"
    root.mkdir()
    _sp.run(["git", "init", str(root)], check=True, capture_output=True)
    _sp.run(["git", "config", "user.email", "t@t.com"], cwd=root, check=True)
    _sp.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    (root / "README.md").write_text("# t\n")
    _sp.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
    _sp.run(["git", "commit", "-m", "i"], cwd=root, check=True, capture_output=True)

    (root / ".specify" / "templates").mkdir(parents=True)
    for name in features:
        d = root / "specs" / name
        d.mkdir(parents=True)
        (d / "spec.md").write_text("# x\n")
    if pointer is not None:
        (root / ".specify" / "feature.json").write_text(
            _json.dumps({"feature_directory": pointer})
        )
    return root


def test_unresolvable_override_is_blocking(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression guard for the state Feature 026 itself created.

    Before SpecOps honoured `SPECIFY_FEATURE_DIRECTORY`, a broken one was inert:
    doctor resolved through the pointer and answered correctly. Once the override
    takes precedence, an unresolvable one made doctor report `ok — no active
    SpecOps feature` and advise `status init-spec`, while a perfectly good pointer
    sat unused. Advice derived from the wrong diagnosis is worse than no advice.
    """
    root = _resolution_repo(tmp_path, pointer="specs/001-old")
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/999-gone")

    dom = _domains(root)["feature_identity"]
    assert dom["severity"] == doctor.BLOCKING
    finding = dom["findings"][0]
    assert "SPECIFY_FEATURE_DIRECTORY" in finding["message"]
    assert "999-gone" in finding["message"]
    assert finding["next_action_code"] == doctor.NA_RESOLVE_FEATURE_SELECTION
    assert doctor.cmd_doctor(root).exit_code != 0


def test_dangling_pointer_is_blocking_not_silently_replaced(tmp_path: Path) -> None:
    """A pointer naming a missing directory is a *stated* selection that cannot be
    honoured. Falling through to the newest `specs/NNN-*` answers about a different
    feature and calls it healthy — #75's failure mode inside the command whose job
    is to catch it."""
    root = _resolution_repo(tmp_path, pointer="specs/999-gone")

    dom = _domains(root)["feature_identity"]
    assert dom["severity"] == doctor.BLOCKING
    finding = dom["findings"][0]
    assert "999-gone" in finding["message"]
    assert "002-newer" not in finding["message"]   # never answers about another feature
    assert finding["next_action_code"] == doctor.NA_RESOLVE_FEATURE_SELECTION


def test_inferred_resolution_is_a_warning(tmp_path: Path) -> None:
    """FR-014a: the inference is reported *wherever* the resolved feature is echoed,
    and doctor echoes it. A guess presented as a fact is the silence #75 is about."""
    root = _resolution_repo(tmp_path, pointer=None)

    dom = _domains(root)["feature_identity"]
    assert dom["severity"] == doctor.WARNING
    finding = dom["findings"][0]
    assert "002-newer" in finding["message"]
    assert "inferred" in finding["message"]
    assert finding["next_action_code"] == doctor.NA_RESOLVE_FEATURE_SELECTION


def test_pointer_resolution_stays_ok_and_unlabelled(tmp_path: Path) -> None:
    """The healthy path is byte-identical to before: no new noise on a good repo."""
    root = _resolution_repo(tmp_path, pointer="specs/002-newer")

    dom = _domains(root)["feature_identity"]
    assert dom["severity"] == doctor.OK
    assert dom["findings"][0]["message"] == "active feature: 002-newer"


def test_override_resolution_is_reported_as_the_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A *working* override is healthy — but naming it explains why doctor answers
    about a feature the pointer file does not name."""
    root = _resolution_repo(tmp_path, pointer="specs/001-old")
    monkeypatch.setenv("SPECIFY_FEATURE_DIRECTORY", "specs/002-newer")

    dom = _domains(root)["feature_identity"]
    assert dom["severity"] == doctor.OK
    assert "002-newer" in dom["findings"][0]["message"]
    assert "SPECIFY_FEATURE_DIRECTORY" in dom["findings"][0]["message"]


def test_genuinely_absent_feature_is_still_ok(tmp_path: Path) -> None:
    """No pointer and no `specs/` at all remains a supported resting state — this
    change must not turn "nothing started yet" into a failure."""
    root = _resolution_repo(tmp_path, pointer=None, features=())
    dom = _domains(root)["feature_identity"]
    assert dom["severity"] == doctor.OK
    assert dom["findings"][0]["next_action_code"] == doctor.NA_START_OR_SELECT_FEATURE
