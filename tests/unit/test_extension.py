"""Unit tests for the native extension manifest engine (extension.py)."""
from __future__ import annotations

from pathlib import Path

import yaml

from specops import extension


def test_read_manifest_absent_returns_empty(tmp_path: Path) -> None:
    assert extension.read_manifest(tmp_path) == {}


def test_merge_preserves_foreign_hook_entries() -> None:
    existing = {"hooks": {"before_plan": [{"extension": "other", "prompt": "keep me"}]}}
    merged = extension._merge_manifest(existing, [])
    exts = [e["extension"] for e in merged["hooks"]["before_plan"]]
    assert "other" in exts
    assert "specops" in exts


def test_merge_preserves_foreign_commands() -> None:
    existing = {"commands": [{"extension": "other", "id": "x"}]}
    cmds = [
        {"extension": "specops", "id": "specops-review", "integration": "claude", "path": "p"}
    ]
    merged = extension._merge_manifest(existing, cmds)
    ids = [c["id"] for c in merged["commands"]]
    assert "x" in ids
    assert "specops-review" in ids


def test_merge_writes_all_hook_points() -> None:
    merged = extension._merge_manifest({}, [])
    assert set(merged["hooks"]) == {
        "before_specify",  # Feature 013: lightweight-lane recognition directive
        "after_specify",
        "after_clarify",    # Feature 022: run-decision recording
        "after_checklist",  # Feature 022: run-decision recording
        "before_plan",
        "after_tasks",
        "after_analyze",    # Feature 022: run-decision recording
        "before_converge",  # Feature 022: fail-closed recording-path precondition
        "after_converge",   # Feature 022: deterministic ledger append
        "after_implement",
    }
    assert merged["specops"]["cli_compat"]["min_cli_version"] == extension.compat.MIN_CLI_VERSION


def test_atomic_write_roundtrip_no_temp_left(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "extensions.yml"
    extension._atomic_write(target, "a: 1\n")
    assert target.read_text() == "a: 1\n"
    assert list((tmp_path / "sub").glob(".ext-*")) == []


def test_semantically_equal_ignores_order_and_foreign_entries() -> None:
    a = extension._merge_manifest(
        {}, [{"extension": "specops", "id": "specops-review", "integration": "claude", "path": "p"}]
    )
    b = yaml.safe_load(yaml.safe_dump(a))  # normalized round-trip
    # Inject a foreign entry and reorder — SpecOps view must be unchanged.
    b["hooks"]["before_plan"].insert(0, {"extension": "other", "prompt": "z"})
    assert extension.semantically_equal(a, b)


def test_semantically_equal_detects_prompt_change() -> None:
    a = extension._merge_manifest({}, [])
    b = yaml.safe_load(yaml.safe_dump(a))
    b["hooks"]["before_plan"] = [
        {"extension": "specops", "enabled": True, "optional": False,
         "description": "d", "prompt": "CHANGED"}
    ]
    assert not extension.semantically_equal(a, b)


# --- Feature 022 US1: converge hook pair in the built manifest ---------------

def test_manifest_registers_converge_hook_pair() -> None:
    hooks = extension._build_hooks()
    for point, needle in (
        ("before_converge", "sync-tasks --check"),
        ("after_converge", "specops status sync-tasks"),
    ):
        assert point in hooks, f"missing hook point {point}"
        (entry,) = hooks[point]
        assert entry["extension"] == extension.OWNER
        assert entry["enabled"] is True
        assert entry["optional"] is False
        assert needle in entry["prompt"]


# --- Feature 022 US2: run-decision recorders in the built manifest -----------

def test_manifest_registers_optional_step_recorders() -> None:
    hooks = extension._build_hooks()
    for step in ("clarify", "checklist", "analyze"):
        point = f"after_{step}"
        assert point in hooks, f"missing hook point {point}"
        (entry,) = hooks[point]
        assert entry["extension"] == extension.OWNER
        assert entry["optional"] is False  # recording is mandatory, the step is not
        assert f"specops status record-step {step} --decision run" in entry["prompt"]


# ---------------------------------------------------------------------------
# Feature 026 (T062) — amendment is presented as a recovery move, never routine
# ---------------------------------------------------------------------------


def _directives_mentioning_amendment() -> list[Path]:
    from tests.conftest import DIRECTIVES_DIR

    return [
        p for p in sorted(DIRECTIVES_DIR.glob("*.md"))
        if "amend-task" in p.read_text(encoding="utf-8")
    ]


def test_at_least_one_directive_teaches_amendment() -> None:
    """The failure that produced #74 is an agent recovering from a dead session, so
    the directives are where the knowledge has to land."""
    assert _directives_mentioning_amendment()


def test_every_directive_mentioning_amendment_states_the_restriction() -> None:
    """FR-025/SC-010: an agent that can amend freely can also amend away its own bad
    closes — the laundering this feature refuses. The restriction must be *stated*,
    not merely implied by omission."""
    for path in _directives_mentioning_amendment():
        text = path.read_text(encoding="utf-8").lower()
        assert "recovery move" in text, path.name
        assert "previous session" in text, path.name
        assert "current run" in text, path.name


def test_directives_do_not_promise_mechanical_enforcement() -> None:
    """FR-026: SpecOps has no notion of which session closed a task. A directive that
    implied otherwise would set the agent up to trust a refusal that never comes."""
    for path in _directives_mentioning_amendment():
        text = path.read_text(encoding="utf-8").lower()
        assert "will not refuse you" in text or "cannot tell" in text, path.name
