"""Shared runner for client-configured shell commands from specops.json.

Single execution semantics for every consumer (`specops review` gates,
`complete-task --auto`): user-authored shell string, captured output,
decode-tolerant, executed from the repository root.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def run_client_command(command: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run *command* from *cwd* with captured, decode-tolerant text output."""
    return subprocess.run(
        command, shell=True, capture_output=True, text=True,
        errors="replace", cwd=str(cwd),
    )
