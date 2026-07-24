"""Shared runner for client-configured shell commands from specops.json.

Single execution semantics for every consumer (`specops review` gates,
`complete-task --auto`): user-authored shell string, captured output,
decode-tolerant, executed from the repository root, with an optional deterministic
timeout (Feature 012, FR-010).
"""
from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
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


def run_client_command(command: str, cwd: Path, timeout: int | None = None) -> ShellResult:
    """Run *command* from *cwd* with captured, decode-tolerant text output.

    When *timeout* (seconds) is given and exceeded, the process **group** is terminated
    and a ``timed_out`` result is returned (return code 124, the conventional timeout
    code) rather than raising — the caller records the timeout deterministically
    (FR-010). The command runs in its own session/group (POSIX ``start_new_session``) so
    that a shell wrapper's grandchildren (e.g. the real ``pytest`` process) are killed
    too, rather than orphaned and left holding the output pipe past the timeout.
    """
    posix = sys.platform != "win32"
    proc = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, errors="replace", cwd=str(cwd),
        start_new_session=posix,  # POSIX: own process group so we can kill the tree
    )
    try:
        out, err = proc.communicate(timeout=timeout)
        return ShellResult(proc.returncode, out or "", err or "", timed_out=False)
    except subprocess.TimeoutExpired:
        _kill_tree(proc, posix)
        out, err = proc.communicate()  # the whole group is dead → does not block
        return ShellResult(124, out or "", err or "", timed_out=True)


def _kill_tree(proc: subprocess.Popen, posix: bool) -> None:
    """Kill the timed-out process and its descendants (best-effort, never raises)."""
    if posix:
        with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            return
    with contextlib.suppress(ProcessLookupError, OSError):
        proc.kill()
