"""Frozen-shape contract test — gate-profile file (Feature 021). [SC-002]

Locks the gate-profile file's output_version and the per-profile / applies-predicate
field set, using the committed fixtures. A change to the file output_version, a profile
field, or an applies-predicate key fails here.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specops import gateprofiles

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "gate-profiles"

# Enumerated frozen baseline (data-model.md Entity 4).
_PROFILE_FIELDS = {"name", "command", "timeout", "required", "applies"}
_APPLIES_KEYS = {"always", "contexts", "paths", "risk", "gate_ref"}


def test_gateprofiles_file_output_version_pinned() -> None:
    assert gateprofiles.OUTPUT_VERSION == 1


def test_valid_fixture_parses_and_validates(tmp_path: Path) -> None:
    """The valid fixture round-trips through parse + validate with no defects."""
    from tests.conftest import write_profiles

    raw = yaml.safe_load((FIXTURES / "valid.yaml").read_text(encoding="utf-8"))
    write_profiles(tmp_path, raw)
    result = gateprofiles.validate(tmp_path)
    # validate returns a GateCommandResult; a valid config yields no defects.
    assert result.status in {gateprofiles.S_VALID, gateprofiles.S_LIST_OK}, result.human


def test_minimal_fixture_parses(tmp_path: Path) -> None:
    from tests.conftest import write_profiles

    raw = yaml.safe_load((FIXTURES / "minimal.yaml").read_text(encoding="utf-8"))
    write_profiles(tmp_path, raw)
    result = gateprofiles.validate(tmp_path)
    assert result.status in {gateprofiles.S_VALID, gateprofiles.S_LIST_OK}, result.human


def test_profile_and_applies_field_sets_frozen() -> None:
    """The known per-profile field names and applies-predicate keys are frozen. Derived
    from the module's declarative field tables so a renamed field is caught."""
    # `name` is the profile identity (validated separately from the declarative value
    # table) and `applies` is the predicate block — both frozen alongside _PROFILE_FIELDS.
    known_profile = set(gateprofiles._PROFILE_FIELDS) | {"name", "applies"}
    assert known_profile == _PROFILE_FIELDS
    assert set(gateprofiles._APPLIES_FIELDS) == _APPLIES_KEYS


@pytest.mark.parametrize("fixture", ["valid.yaml", "minimal.yaml"])
def test_fixtures_use_only_frozen_fields(fixture) -> None:
    """The committed fixtures may only use frozen fields — a guard that the fixtures
    themselves do not silently introduce a new field the freeze has not classified."""
    raw = yaml.safe_load((FIXTURES / fixture).read_text(encoding="utf-8"))
    top = set(raw)
    assert top <= {"output_version", "profiles"}
    for prof in raw.get("profiles", []):
        assert set(prof) <= _PROFILE_FIELDS
        assert set(prof.get("applies", {})) <= _APPLIES_KEYS
