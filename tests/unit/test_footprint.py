"""Feature 020 US1 (SC-001): GitPython is gone from the dependency footprint.

Deterministic regardless of what happens to be installed in a dev environment:
the source truth is that no production module imports a git library and the
declared runtime dependencies name no gitpython/gitdb/smmap.
"""
from __future__ import annotations

import re
from pathlib import Path

import specops

SRC = Path(specops.__file__).parent
PYPROJECT = SRC.parent.parent / "pyproject.toml"


def _runtime_dependencies_block() -> str:
    """Return the `[project] dependencies = [...]` array text (3.10-safe, no tomllib)."""
    text = PYPROJECT.read_text(encoding="utf-8")
    match = re.search(r"\ndependencies = \[(.*?)\]", text, re.DOTALL)
    return match.group(1) if match else ""


def test_no_production_module_imports_a_git_library() -> None:
    offenders = []
    for py in SRC.glob("*.py"):
        text = py.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped == "import git" or stripped.startswith("from git ") \
                    or stripped.startswith("from git."):
                offenders.append(py.name)
    assert offenders == [], f"git-library imports remain in: {offenders}"


def test_gitops_module_imports_only_subprocess_for_git() -> None:
    text = (SRC / "gitops.py").read_text(encoding="utf-8")
    assert "import git" not in text
    assert "import subprocess" in text


def test_runtime_dependencies_name_no_gitpython() -> None:
    if not PYPROJECT.is_file():  # installed wheel without sources — skip
        return
    deps = _runtime_dependencies_block().lower()
    for banned in ("gitpython", "gitdb", "smmap"):
        assert banned not in deps


def test_no_mypy_git_override_remains() -> None:
    if not PYPROJECT.is_file():
        return
    text = PYPROJECT.read_text(encoding="utf-8")
    assert 'module = "git.*"' not in text
