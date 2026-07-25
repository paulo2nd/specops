"""Unit tests for the doctor module (Feature 014): contract + per-domain checks.

Covers the foundational verdict/exit contract (T005) and each diagnostic domain's
severity + next_action_code (T012). Every doctor call is read-only and root-parameterized.
"""
from __future__ import annotations

from pathlib import Path

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


def test_active_feature_scope_ignores_other_features(doctor_healthy_repo: Path) -> None:
    # FR-012a: a second, broken (too-new) feature ledger must never be inspected.
    write_second_feature(doctor_healthy_repo, schema_version=99)
    result = doctor.cmd_doctor(doctor_healthy_repo)
    assert result.status == doctor.OK  # still healthy — 002-other is not scanned
    blob = doctor.doctor_json(result)
    assert "002-other" not in blob
