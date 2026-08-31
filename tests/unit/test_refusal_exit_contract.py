"""The CLI-wide refusal contract: a refused operation never reports success (#72).

Two complementary guards:

* a **structural** one — every registered command is wrapped by the single error
  boundary, so a subcommand added without ``@_handle_errors`` fails the suite
  instead of a user's ledger;
* a **behavioural** table — the refusals a caller actually hits exit non-zero and
  say why on stderr.

Filed as #72 after a dogfooding session observed `exit 0` on a refusal; the
behaviour did not reproduce (every path already raises through the boundary), but
the invariant was untested, which is what let the report be plausible.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specops.cli import _handle_errors, app
from tests.conftest import cli, git

# `_handle_errors` defines its wrapper once, so every wrapped command shares that
# code object — an exact identity check, not a `__wrapped__` heuristic.
_BOUNDARY_CODE = _handle_errors(lambda: None).__code__


def _all_commands(t: typer.Typer, prefix: str = "") -> list[tuple[str, object]]:
    """Every (dotted-name, callback) registered on *t*, recursing into sub-apps."""
    found: list[tuple[str, object]] = []
    for cmd in t.registered_commands:
        name = cmd.name or getattr(cmd.callback, "__name__", "?")
        found.append((f"{prefix}{name}", cmd.callback))
    for group in t.registered_groups:
        if group.typer_instance is not None:
            found.extend(_all_commands(group.typer_instance, f"{prefix}{group.name} "))
    return found


def test_every_command_is_wrapped_by_the_error_boundary() -> None:
    """No command may bypass `_handle_errors` — that decorator IS the exit contract."""
    unwrapped = [
        name
        for name, cb in _all_commands(app)
        if getattr(cb, "__code__", None) is not _BOUNDARY_CODE
    ]
    assert unwrapped == [], (
        f"commands missing @_handle_errors: {unwrapped} — a refusal in these would "
        "print and exit 0"
    )


# ---------------------------------------------------------------------------
# Behavioural table
# ---------------------------------------------------------------------------

@pytest.fixture()
def refusal_repo(tmp_git_repo: Path) -> Path:
    """A feature repo at IMPLEMENT with T001 DONE and T002 PENDING.

    One state that makes every refusal below reachable without re-staging.
    """
    root = tmp_git_repo
    (root / ".specify").mkdir(parents=True, exist_ok=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/001-refusal"})
    )
    feature_dir = root / "specs" / "001-refusal"
    feature_dir.mkdir(parents=True)
    (feature_dir / "tasks.md").write_text("- [ ] T001 first\n- [ ] T002 second\n")
    git(root, "add", "-A")
    git(root, "commit", "-m", "artifacts")

    assert cli(root, "status", "init-spec").returncode == 0
    for phase in ("PLAN", "TASKS", "IMPLEMENT"):
        assert cli(root, "status", "transition-phase", phase).returncode == 0
    assert cli(root, "status", "start-task", "T001").returncode == 0
    assert cli(
        root, "status", "complete-task", "T001", "--evidence", "CLI_LOG:done"
    ).returncode == 0
    return root


REFUSALS = [
    pytest.param(
        ("status", "init-spec"), "already exists", id="init-spec-on-existing-ledger"
    ),
    pytest.param(
        ("status", "start-task", "T999"), "T999", id="start-task-unknown-id"
    ),
    pytest.param(
        ("status", "start-task", "T001"), "DONE", id="start-task-already-done"
    ),
    pytest.param(
        ("status", "complete-task", "T001", "--evidence", "CLI_LOG:again"),
        "IN_PROGRESS",
        id="complete-task-not-in-progress",
    ),
    pytest.param(
        ("status", "complete-task", "T002", "--evidence", "CLI_LOG:never-started"),
        "IN_PROGRESS",
        id="complete-task-never-started",
    ),
    pytest.param(
        ("status", "transition-phase", "IMPLEMENT", "-r", "REJECTED"),
        "Invalid transition",
        id="transition-phase-noop-without-if-needed",
    ),
    pytest.param(
        ("status", "transition-phase", "DONE", "-r", "APPROVED"),
        "Invalid transition",
        id="transition-phase-skips-review",
    ),
    pytest.param(
        ("status", "transition-phase", "NOWHERE"), "Unknown phase", id="unknown-phase"
    ),
    pytest.param(
        ("status", "transition-phase", "REVIEW", "-r", "SORT-OF"),
        "Invalid result",
        id="unknown-result",
    ),
]


@pytest.mark.parametrize("args,fragment", REFUSALS)
def test_refusal_exits_non_zero_and_explains(
    refusal_repo: Path, args: tuple[str, ...], fragment: str
) -> None:
    """A refused operation is a failure: non-zero exit AND a reason on stderr."""
    result = cli(refusal_repo, *args)
    assert result.returncode != 0, (
        f"'specops {' '.join(args)}' refused but exited 0 — a caller reading the "
        f"exit code would believe it succeeded. stdout={result.stdout!r}"
    )
    assert fragment in (result.stderr or "") + (result.stdout or "")


def test_refusal_leaves_the_ledger_untouched(refusal_repo: Path) -> None:
    """A refusal must not half-write: the ledger is byte-identical afterwards."""
    ledger_path = refusal_repo / "specs" / "001-refusal" / "status.yaml"
    before = ledger_path.read_bytes()
    for args, _fragment in [(p.values[0], p.values[1]) for p in REFUSALS]:
        cli(refusal_repo, *args)
    assert ledger_path.read_bytes() == before


# ---------------------------------------------------------------------------
# The documented review outcome sequence (#77)
# ---------------------------------------------------------------------------

def test_approval_after_a_rejected_round_follows_the_documented_prelude(
    refusal_repo: Path,
) -> None:
    """`templates/review.md`'s prelude makes both verdicts recordable from IMPLEMENT.

    A round following any earlier REJECTED round starts in IMPLEMENT, where a bare
    `transition-phase DONE` is correctly refused (#77). The directive now issues
    `transition-phase REVIEW --if-needed` first — which must work from IMPLEMENT
    (forward) and from REVIEW (no-op).
    """
    root = refusal_repo
    # Round 1: enter REVIEW, reject → back to IMPLEMENT.
    assert cli(root, "status", "transition-phase", "REVIEW", "--if-needed").returncode == 0
    assert cli(
        root, "status", "transition-phase", "IMPLEMENT", "-r", "REJECTED"
    ).returncode == 0

    # Round 2 verdict, recorded exactly as the directive instructs.
    prelude = cli(root, "status", "transition-phase", "REVIEW", "--if-needed")
    assert prelude.returncode == 0, prelude.stderr
    approve = cli(root, "status", "transition-phase", "DONE", "-r", "APPROVED")
    assert approve.returncode == 0, approve.stderr

    # The prelude is a no-op when already in the target phase.
    again = cli(root, "status", "transition-phase", "DONE", "--if-needed")
    assert again.returncode == 0
    assert "no-op" in again.stdout


def test_review_directive_documents_the_prelude() -> None:
    """The shipped directive must carry the prelude the test above exercises."""
    from specops import status

    review_md = (
        Path(status.__file__).parent / "templates" / "review.md"
    ).read_text(encoding="utf-8")
    assert "transition-phase REVIEW --if-needed" in review_md
