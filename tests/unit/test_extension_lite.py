"""Feature 013: additive install of the `specops-lite` workflow + structural checks.

Verifies the generalized workflow install/unregister handles BOTH SpecOps workflows,
preserves foreign registry entries and the bundled `speckit` workflow, and that the
`specops-lite` definition is composed of native step types only with a halt/promote-only
stop-and-ask and no semantic review cycle.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from specops import extension

LITE = (
    Path(__file__).resolve().parents[2]
    / "src" / "specops" / "templates" / "workflows" / "specops-lite" / "workflow.yml"
)
NATIVE_STEP_TYPES = {
    "command", "shell", "prompt", "gate", "if", "switch",
    "while", "do-while", "fan-out", "fan-in", "init",
}


def _flatten(steps: list[dict]) -> list[dict]:
    out: list[dict] = []
    for step in steps:
        out.append(step)
        for key in ("then", "else", "steps"):
            nested = step.get(key)
            if isinstance(nested, list):
                out.extend(_flatten(nested))
    return out


# --- structural validation of the lite definition --------------------------

def test_lite_workflow_identity() -> None:
    wf = yaml.safe_load(LITE.read_text())["workflow"]
    assert wf["id"] == "specops-lite"


def test_lite_all_steps_native() -> None:
    steps = _flatten(yaml.safe_load(LITE.read_text())["steps"])
    for step in steps:
        assert step.get("type", "command") in NATIVE_STEP_TYPES, step["id"]


def test_lite_stop_and_ask_is_halt_or_promote_only() -> None:
    """G-1/FR-008: the stop-and-ask gate exposes exactly halt|promote (no bypass)."""
    steps = _flatten(yaml.safe_load(LITE.read_text())["steps"])
    gate = next(s for s in steps if s["id"] == "halt-or-promote")
    assert set(gate["options"]) == {"halt", "promote"}


def test_lite_has_no_semantic_review_cycle() -> None:
    """G-3/FR-010: the lane opens no review cycle (no specops.review command step)."""
    steps = _flatten(yaml.safe_load(LITE.read_text())["steps"])
    assert all(s.get("command") != "specops.review" for s in steps)


def test_no_lane_surface_names_a_gate_review() -> None:
    """FR-021 vocabulary guard (L1): the deterministic gate is `preflight`; the lite
    workflow's `specops lane *` shell steps never invoke a gate named `review`."""
    steps = _flatten(yaml.safe_load(LITE.read_text())["steps"])
    for s in steps:
        run = s.get("run", "")
        assert "specops review" not in run
        assert "lane review" not in run
    # And the CLI exposes no `lane review` command.
    from specops import cli
    lane_cmds = {c.name for c in cli.lane_app.registered_commands}
    assert "review" not in lane_cmds


# --- additive install / unregister -----------------------------------------

def _speckit(tmp_path: Path) -> Path:
    (tmp_path / ".specify" / "workflows").mkdir(parents=True)
    return tmp_path


def test_install_registers_both_workflows(tmp_path: Path) -> None:
    root = _speckit(tmp_path)
    # A pre-existing foreign workflow that must be preserved.
    reg = root / ".specify" / "workflows" / "workflow-registry.json"
    reg.write_text(json.dumps({"workflows": {"foreign": {"name": "keep"}}}))

    assert extension.install_workflow(root) is True
    data = json.loads(reg.read_text())
    assert set(data["workflows"]) == {"foreign", "specops", "specops-lite"}
    assert (root / ".specify" / "workflows" / "specops-lite" / "workflow.yml").is_file()


def test_install_is_idempotent(tmp_path: Path) -> None:
    root = _speckit(tmp_path)
    assert extension.install_workflow(root) is True
    assert extension.install_workflow(root) is False  # no change on re-run


def test_unregister_removes_both_preserving_foreign(tmp_path: Path) -> None:
    root = _speckit(tmp_path)
    reg = root / ".specify" / "workflows" / "workflow-registry.json"
    reg.write_text(json.dumps({"workflows": {"foreign": {"name": "keep"}}}))
    extension.install_workflow(root)

    assert extension.unregister_workflow(root) is True
    data = json.loads(reg.read_text())
    assert set(data["workflows"]) == {"foreign"}
    assert not (root / ".specify" / "workflows" / "specops-lite").exists()
    assert not (root / ".specify" / "workflows" / "specops").exists()
