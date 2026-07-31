"""Feature 022 US1: the converge directive pair (Principle IV).

Verifies native-hook registration (`before_converge`/`after_converge`) and that the
directive content encodes the required behavior: fail closed BEFORE mutation via the
deterministic `sync-tasks --check` precondition (FR-003), the SC-tagging obligation
and recording after converge (FR-001/FR-002), non-blocking coverage reporting
(FR-004), and Rule-5 degradation on unmanaged repositories (FR-010).
"""
from __future__ import annotations

from specops import extension
from tests.conftest import directive_path

CONVERGE_PRE = directive_path("converge-pre")
CONVERGE = directive_path("converge")


# --- native path (extensions.yml hooks) ------------------------------------

def test_native_hook_registers_converge_pre_before_converge() -> None:
    hooks = extension._build_hooks()
    assert "before_converge" in hooks
    entry = hooks["before_converge"][0]
    assert entry["extension"] == extension.OWNER
    assert entry["optional"] is False  # recording is mandatory (FR-006 spirit)
    assert "sync-tasks --check" in entry["prompt"]


def test_native_hook_registers_converge_after_converge() -> None:
    hooks = extension._build_hooks()
    assert "after_converge" in hooks
    entry = hooks["after_converge"][0]
    assert entry["extension"] == extension.OWNER
    assert entry["optional"] is False
    assert "sync-tasks" in entry["prompt"]


# --- converge-pre content: fail closed before mutation (FR-003) -------------

def test_converge_pre_degrades_on_unmanaged_repo() -> None:
    text = CONVERGE_PRE.read_text(encoding="utf-8").lower()
    assert "not available" in text or "not initialized" in text  # Rule-5 no-op clause


def test_converge_pre_orders_check_before_mutation() -> None:
    text = CONVERGE_PRE.read_text(encoding="utf-8")
    assert "specops status sync-tasks --check" in text
    lower = text.lower()
    # The precondition is explicitly BEFORE converge touches tasks.md.
    assert "before" in lower and "tasks.md" in lower
    # Non-zero exit → stop and ask, never mutate.
    assert "stop" in lower and "ask" in lower
    assert "do not run" in lower or "does not run" in lower or "without mutating" in lower


def test_converge_pre_fails_closed_when_managed_but_cli_absent() -> None:
    """A managed repo (specops.json present) with the CLI unavailable is a missing
    recording path — fail closed, distinct from the unmanaged no-op."""
    text = CONVERGE_PRE.read_text(encoding="utf-8").lower()
    assert "specops.json" in text


# --- converge content: tag → record → report (FR-001/FR-002/FR-004) ---------

def test_converge_requires_sc_tags_before_recording() -> None:
    text = CONVERGE.read_text(encoding="utf-8")
    assert "[SC-" in text  # tagging obligation lives in the directive (clarification Q2)
    lower = text.lower()
    assert "before" in lower and "record" in lower


def test_converge_records_via_sync_tasks() -> None:
    text = CONVERGE.read_text(encoding="utf-8")
    assert "specops status sync-tasks" in text


def test_converge_reports_consistency_without_gating() -> None:
    text = CONVERGE.read_text(encoding="utf-8")
    assert "specops consistency" in text
    lower = text.lower()
    # Record, do not validate: coverage output is reported, never a gate/abort.
    assert "do not abort" in lower or "never block" in lower or "not a gate" in lower


def test_converge_degrades_on_unmanaged_repo() -> None:
    text = CONVERGE.read_text(encoding="utf-8").lower()
    assert "not available" in text or "not initialized" in text


# --- negative: no reimplementation, no new surface beyond sync-tasks (Rule 8)

def test_directives_name_no_new_surface_beyond_sync_tasks() -> None:
    for path in (CONVERGE_PRE, CONVERGE):
        text = path.read_text(encoding="utf-8")
        # The only specops CLI surfaces named are the recording seam and the
        # existing read-only reporters — never a bespoke converge engine.
        for line in text.splitlines():
            if "specops " not in line:
                continue
            assert (
                "specops status sync-tasks" in line
                or "specops consistency" in line
                or "specops reconcile" in line
                or "specops.json" in line
            ), f"unexpected specops surface named in {path.name}: {line!r}"
