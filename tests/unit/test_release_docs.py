"""Release-docs contract test — freeze is recorded and discoverable (Feature 021). [SC-006][SC-008]

Asserts the CHANGELOG and both README entry points reference the freeze / stability policy,
and that no committed test evaluates the release strategy's real-usage criterion (the rc tag
is an external release-owner judgment, not forced by this feature).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_changelog_links_stability_policy() -> None:
    text = _read("CHANGELOG.md")
    assert "docs/stability.md" in text
    assert "Contract Freeze" in text


def test_both_readmes_reference_the_freeze() -> None:
    """SC-006: EN and PT entry points both point at the stability policy (dual-language
    presence; equivalence itself is maintained by manual review)."""
    assert "docs/stability.md" in _read("README.md")
    assert "docs/stability.md" in _read("README.pt-br.md")


def test_no_test_evaluates_real_usage_criterion() -> None:
    """SC-008: this feature references the rc real-usage criterion but does not evaluate it;
    no committed test asserts the criterion is met / forces the rc tag."""
    tests_dir = ROOT / "tests"
    offenders = []
    for p in tests_dir.rglob("test_*.py"):
        body = p.read_text(encoding="utf-8").lower()
        # Allow a mention that explicitly documents the non-evaluation (this file).
        mentions = "real-usage criterion" in body or "real_usage_criterion" in body
        if mentions and p.name != "test_release_docs.py":
            offenders.append(p.name)
    assert offenders == [], f"tests must not evaluate the rc criterion: {offenders}"
