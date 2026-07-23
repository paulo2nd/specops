"""Unit tests for shell command timeouts (Feature 012, US3, T023).

Covers FR-010/SC-002: a command exceeding its timeout is terminated and reported as
`timed_out` (return code 124), not raised; a fast command is unaffected.
"""
from __future__ import annotations

import sys
from pathlib import Path

from specops import shell


def test_timeout_terminates_and_flags(tmp_path: Path) -> None:
    slow = f'"{sys.executable}" -c "import time; time.sleep(10)"'
    result = shell.run_client_command(slow, tmp_path, timeout=1)
    assert result.timed_out is True
    assert result.returncode == 124


def test_fast_command_not_timed_out(tmp_path: Path) -> None:
    fast = f'"{sys.executable}" -c "print(1)"'
    result = shell.run_client_command(fast, tmp_path, timeout=30)
    assert result.timed_out is False
    assert result.returncode == 0
    assert "1" in result.stdout


def test_no_timeout_by_default(tmp_path: Path) -> None:
    result = shell.run_client_command(f'"{sys.executable}" -c "print(1)"', tmp_path)
    assert result.timed_out is False and result.returncode == 0
