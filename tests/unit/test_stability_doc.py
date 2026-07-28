"""Doc-contract test — docs/stability.md (Feature 021). [SC-001][SC-005]

Asserts the published stability policy classifies every frozen surface and states the
post-1.0 versioning obligations. This is a structural check on the policy document, not on
runtime behavior.
"""
from __future__ import annotations

from pathlib import Path

DOC = Path(__file__).resolve().parent.parent.parent / "docs" / "stability.md"

# Every frozen surface must be named in the policy (SC-001). The nine surfaces = the roadmap's
# seven + the two the FR-003 sweep found (context-map file, SARIF output).
_FROZEN_SURFACES = [
    "specops.json",
    "status.yaml",
    "lane.yaml",
    "gate-profiles.yaml",
    "output envelope",
    "exit codes",
    "findings-input",
    "context-map.yaml",
    "SARIF",
]


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_stability_doc_exists() -> None:
    assert DOC.is_file()


def test_all_frozen_surfaces_named() -> None:
    text = _text().lower()
    for surface in _FROZEN_SURFACES:
        assert surface.lower() in text, f"stability.md does not mention frozen surface: {surface}"


def test_states_additive_and_breaking_rules() -> None:
    """SC-001: the policy states both an additive and a breaking rule (the table columns)."""
    text = _text().lower()
    assert "additive change" in text
    assert "breaking change" in text


def test_records_fr003_sweep_result() -> None:
    """SC-001: the sweep result is recorded (no observable surface left unclassified)."""
    text = _text().lower()
    assert "sweep" in text
    assert "context-map" in text and "sarif" in text


def test_versioning_and_migration_section_present() -> None:
    """SC-005: the versioning policy states bump+migration obligations, envelope-version
    semantics, and the rename alias/deprecation discipline."""
    text = _text().lower()
    assert "versioning" in text and "migration" in text
    assert "migrate_to_current" in text or "migration test" in text
    assert "output_version" in text
    assert "deprecated alias" in text and "next minor" in text


def test_documents_exit_codes() -> None:
    text = _text()
    assert "`0`" in text and "`1`" in text and "`2`" in text
    assert "Principle VI" in text
