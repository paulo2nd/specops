"""Shared runner for client-configured shell commands from specops.json.

Single execution semantics for every consumer (`specops review` gates,
`complete-task --auto`): user-authored shell string, captured output,
decode-tolerant, executed from the repository root, with an optional deterministic
timeout (Feature 012, FR-010).
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NamedTuple


class ShellResult(NamedTuple):
    """Outcome of a client command. Exposes the fields consumers read on a
    ``subprocess.CompletedProcess`` (``returncode``/``stdout``/``stderr``), plus an
    explicit ``timed_out`` flag so a timeout is distinguishable from an exit code."""

    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


def _decode(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_client_command(command: str, cwd: Path, timeout: int | None = None) -> ShellResult:
    """Run *command* from *cwd* with captured, decode-tolerant text output.

    When *timeout* (seconds) is given and exceeded, the process is terminated and a
    ``timed_out`` result is returned (return code 124, the conventional timeout code)
    rather than raising — the caller records the timeout deterministically (FR-010).
    """
    try:
        cp = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            errors="replace", cwd=str(cwd), timeout=timeout,
        )
        return ShellResult(cp.returncode, cp.stdout, cp.stderr, timed_out=False)
    except subprocess.TimeoutExpired as exc:
        return ShellResult(124, _decode(exc.stdout), _decode(exc.stderr), timed_out=True)
