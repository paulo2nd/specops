"""Feature 023: the implement directive's Context Read Set section (Principle IV).

Verifies the directive is delivered on the native path (the `after_implement` hook
carries the section) and the legacy marker-block path (idempotent inject), and that
its content encodes the contract C1-C7 of
specs/023-context-readset-implement/contracts/implement-directive.md:
resolve the IMPLEMENT-phase read set at session start and scope reads to it,
guidance-not-gate with discoveries routed through the existing Feature 010 flow,
and safe degradation (no map -> no-op; any non-zero exit -> proceed unscoped).
"""
from __future__ import annotations

import re
from pathlib import Path

from specops import extension

IMPLEMENT_MD = (
    Path(__file__).resolve().parents[2]
    / "src" / "specops" / "templates" / "directives" / "implement.md"
)

SECTION_HEADING = "### Context Read Set (Feature 023)"

# The only CLI surfaces the section may name (contract C7): existing, frozen ones.
ALLOWED_COMMANDS = {"specops context resolve", "specops trace acknowledge"}


def _directive_text() -> str:
    return IMPLEMENT_MD.read_text(encoding="utf-8")


def _readset_section() -> str:
    """The Context Read Set section body (heading to the next ### heading)."""
    text = _directive_text()
    assert SECTION_HEADING in text, f"missing section heading {SECTION_HEADING!r}"
    start = text.index(SECTION_HEADING)
    nxt = text.find("### ", start + len(SECTION_HEADING))
    return text[start:] if nxt == -1 else text[start:nxt]


# --- native path (extensions.yml after_implement hook) ----------------------


def test_native_hook_carries_implement_readset_section() -> None:
    hooks = extension._build_hooks()
    entry = hooks["after_implement"][0]
    assert entry["extension"] == extension.OWNER
    assert SECTION_HEADING in entry["prompt"]


# --- content: US1 — resolve at session start and scope reads (C1/C2/C3) -----


def test_directive_resolves_implement_readset_at_session_start() -> None:
    section = _readset_section()
    # C1: before the first task, one resolve per declared context id from plan.md.
    assert "before the first task" in section
    assert "**SpecOps-Contexts**" in section
    assert "specops context resolve --id" in section
    assert "--phase implement" in section


def test_directive_uses_lowercase_implement_phase_flag() -> None:
    # C2: the literal flag value is the map's lowercase phase key; the uppercase
    # ledger phase name would be a usage error (exit 2).
    text = _directive_text()
    assert "--phase implement" in text
    assert "--phase IMPLEMENT" not in text


def test_directive_scopes_reads_to_union_of_packages() -> None:
    # C3: scope the session's reads to the union of the resolved packages
    # (read_set + expanded_read_set); reading less is always fine.
    section = _readset_section()
    assert "union" in section
    assert "read_set" in section and "expanded_read_set" in section
    assert "Reading less" in section or "reading less" in section


def test_directive_readset_names_no_new_surfaces() -> None:
    # C7: only existing frozen surfaces are named — no new command, flag, or record.
    section = _readset_section()
    for cmd in set(re.findall(r"specops [a-z]+(?: [a-z-]+)?", section)):
        assert any(cmd.startswith(allowed) or allowed.startswith(cmd)
                   for allowed in ALLOWED_COMMANDS), f"unexpected surface: {cmd!r}"
    assert "start-task" not in section  # surfacing declined (research R3)
