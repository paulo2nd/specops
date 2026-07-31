"""Feature 022 US3: `/speckit.taskstoissues` is read-only w.r.t. ledger state.

Contract by absence (SC-004, clarification Q5): SpecOps registers no hook and no
directive for taskstoissues — its only write surface is external (tracker
issues), it invokes no `specops` command, and ledger state cannot change. These
regression tests keep that contract deliberate: a future hook addition must
update the documented registry here, and the SpecOps surfaces that do run
(install/update) must leave a ledger byte-identical.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from specops import compat, extension
from tests.conftest import make_v1_ledger

# The complete, documented SpecOps hook registry. taskstoissues is deliberately
# absent — if this set changes, the change must be a conscious contract decision.
DOCUMENTED_HOOK_POINTS = {
    "before_specify",
    "after_specify",
    "after_clarify",
    "after_checklist",
    "before_plan",
    "after_tasks",
    "after_analyze",
    "before_converge",
    "after_converge",
    "after_implement",
}


def test_no_taskstoissues_hooks_registered() -> None:
    hooks = extension._build_hooks()
    assert "before_taskstoissues" not in hooks
    assert "after_taskstoissues" not in hooks


def test_hook_registry_equals_documented_set_exactly() -> None:
    """Guard against accidental future additions: the registry is a closed,
    documented set — new hook points require updating this contract test."""
    assert set(extension._build_hooks()) == DOCUMENTED_HOOK_POINTS


def test_no_taskstoissues_directive_template_exists() -> None:
    directives = Path(extension.__file__).parent / "templates" / "directives"
    assert not (directives / "taskstoissues.md").exists()


@pytest.fixture()
def compat_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the CLI-compat gate to satisfied, independent of the ambient install."""
    monkeypatch.setattr(compat, "installed_version", lambda: compat.MIN_CLI_VERSION)


def test_ledger_byte_identical_across_install_and_update(
    fake_speckit_repo: Path, compat_ok: None,
) -> None:
    """SC-004: the SpecOps surfaces involved in delivering Feature 022 never
    touch ledger state — a fixture ledger survives install + re-install
    (update path) byte-identical."""
    root = fake_speckit_repo
    feature_dir = root / "specs" / "001-demo"
    make_v1_ledger(feature_dir, feature="001-demo")
    ledger_path = feature_dir / "status.yaml"
    before = ledger_path.read_bytes()

    assert extension.install(root) == "created"
    assert ledger_path.read_bytes() == before
    extension.install(root)  # idempotent re-install (update path)
    assert ledger_path.read_bytes() == before
