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


def test_merge_writes_all_four_hook_points() -> None:
    merged = extension._merge_manifest({}, [])
    assert set(merged["hooks"]) == {
        "after_specify",
        "before_plan",
        "after_tasks",
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
