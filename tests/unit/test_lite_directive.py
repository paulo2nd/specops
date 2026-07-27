"""Feature 013: the lightweight-lane recognition directive (FR-023, Principle IV).

Verifies the directive is delivered on the native path (a `before_specify` optional hook
carrying the lite prompt) and the legacy marker-block path (idempotent inject), and that its
content encodes the required behavior (recognize → propose, never auto-classify; degrade to
a no-op without SpecOps).
"""
from __future__ import annotations

from pathlib import Path

from specops import extension, initializer

LITE_MD = (
    Path(__file__).resolve().parents[2]
    / "src" / "specops" / "templates" / "directives" / "lite.md"
)


# --- native path (extensions.yml hooks) ------------------------------------

def test_native_hook_registers_lite_before_specify() -> None:
    hooks = extension._build_hooks()
    assert "before_specify" in hooks
    entry = hooks["before_specify"][0]
    assert entry["extension"] == extension.OWNER
    assert entry["optional"] is True  # a proposal, never mandatory
    assert "lightweight" in entry["prompt"].lower() or "lite lane" in entry["prompt"].lower()


def test_directive_content_encodes_required_behavior() -> None:
    text = LITE_MD.read_text(encoding="utf-8").lower()
    assert "propose" in text                     # B-2: propose, don't auto-enter
    assert "auto-classify" in text or "auto-enter" in text  # B-2 negative
    assert "specops lane" in text                # B-3: agent drives the CLI
    assert "not initialized" in text             # D-1: degrade to no-op


# --- legacy path (marker-block injection) ----------------------------------

def test_legacy_inject_is_idempotent(tmp_path: Path) -> None:
    prompt = tmp_path / "specify.md"
    prompt.write_text("# specify prompt\n")
    content = LITE_MD.read_text(encoding="utf-8").strip()

    first = initializer.inject_block(prompt, "lite", content)
    second = initializer.inject_block(prompt, "lite", content)
    assert first == "created"
    assert second == "unchanged"  # a second identical inject is a no-op (idempotent)
    # Exactly one lite block — never duplicated.
    assert prompt.read_text(encoding="utf-8").count("SpecOps: lightweight-lane recognition") == 1
