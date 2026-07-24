"""Unit tests for gate-profile config validation (Feature 012, US1, T005).

Covers FR-014 / SC-006: each defect is a distinct diagnostic; a well-formed config
passes; a missing config reports the default-profile state (exit 0). Ordering-cycle is
NOT a v1 defect (reserved).
"""
from __future__ import annotations

from pathlib import Path

from specops import gateprofiles
from tests.conftest import write_map, write_profiles


def _valid_entry(**over):
    entry = {"name": "unit", "command": "pytest -q", "applies": {"always": True}, "timeout": 600}
    entry.update(over)
    return entry


def test_no_config_reports_default_profile(context_map_repo: Path) -> None:
    res = gateprofiles.validate(context_map_repo)
    assert res.status == gateprofiles.S_NO_CONFIG
    assert res.exit_code == 0
    assert "default profile" in res.human


def test_well_formed_config_passes(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"output_version": 1, "profiles": [_valid_entry()]})
    res = gateprofiles.validate(context_map_repo)
    assert res.status == gateprofiles.S_VALID
    assert res.exit_code == 0
    assert res.extra["profiles"] == 1


def test_duplicate_name_defect(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"profiles": [_valid_entry(), _valid_entry()]})
    res = gateprofiles.validate(context_map_repo)
    assert res.status == gateprofiles.S_INVALID
    assert res.exit_code == 1
    assert any("duplicate gate name" in d for d in res.extra["defects"])


def test_empty_command_defect(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"profiles": [_valid_entry(command="")]})
    res = gateprofiles.validate(context_map_repo)
    assert any("`command`" in d for d in res.extra["defects"])


def test_non_positive_timeout_defect(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"profiles": [_valid_entry(timeout=0)]})
    res = gateprofiles.validate(context_map_repo)
    assert any("timeout" in d for d in res.extra["defects"])


def test_non_int_timeout_defect(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"profiles": [_valid_entry(timeout="soon")]})
    res = gateprofiles.validate(context_map_repo)
    assert any("timeout" in d for d in res.extra["defects"])


def test_unknown_predicate_key_defect(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"profiles": [_valid_entry(applies={"wut": 1})]})
    res = gateprofiles.validate(context_map_repo)
    assert any("unknown `applies` key" in d for d in res.extra["defects"])


def test_unsafe_path_pattern_defect(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"profiles": [_valid_entry(applies={"paths": ["../etc/**"]})]})
    res = gateprofiles.validate(context_map_repo)
    assert any("path" in d.lower() for d in res.extra["defects"])


def test_dangling_context_reference_defect(context_map_repo: Path) -> None:
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "api", "match": ["src/api/**"]},
    ]})
    write_profiles(context_map_repo, {"profiles": [_valid_entry(applies={"contexts": ["nope"]})]})
    res = gateprofiles.validate(context_map_repo)
    assert any("unknown context" in d for d in res.extra["defects"])


def test_unsupported_output_version_defect(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"output_version": 999, "profiles": [_valid_entry()]})
    res = gateprofiles.validate(context_map_repo)
    assert any("output_version" in d for d in res.extra["defects"])


def test_scalar_contexts_flagged_not_crashed(context_map_repo: Path) -> None:
    # A scalar `contexts` must be a distinct diagnostic, never a TypeError/traceback,
    # even with a resolvable map present (which triggers the reference loop).
    write_map(context_map_repo, {"schema_version": 1, "contexts": [
        {"id": "api", "match": ["src/api/**"]},
    ]})
    write_profiles(context_map_repo, {"profiles": [_valid_entry(applies={"contexts": "api"})]})
    res = gateprofiles.validate(context_map_repo)  # must not raise
    assert res.status == gateprofiles.S_INVALID
    assert any("`applies.contexts` must be a list" in d for d in res.extra["defects"])


def test_risk_not_mapping_defect(context_map_repo: Path) -> None:
    # A list `risk` (natural mistake) is dropped by the parser and would silently widen
    # the gate to always-run; validation must flag it.
    entry = _valid_entry(applies={"risk": ["schema-change"]})
    write_profiles(context_map_repo, {"profiles": [entry]})
    res = gateprofiles.validate(context_map_repo)
    assert res.status == gateprofiles.S_INVALID
    assert any("`applies.risk` must be a mapping" in d for d in res.extra["defects"])


def test_non_bool_always_defect(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"profiles": [_valid_entry(applies={"always": "yes"})]})
    res = gateprofiles.validate(context_map_repo)
    assert any("`applies.always` must be a boolean" in d for d in res.extra["defects"])


def test_each_defect_is_distinct(context_map_repo: Path) -> None:
    write_profiles(context_map_repo, {"profiles": [
        {"name": "a", "command": "", "timeout": 0},
        {"name": "a", "command": "x", "timeout": 5},  # duplicate name
    ]})
    res = gateprofiles.validate(context_map_repo)
    defects = res.extra["defects"]
    # empty command + bad timeout + duplicate name = at least 3 distinct diagnostics
    assert len(set(defects)) == len(defects)
    assert len(defects) >= 3
