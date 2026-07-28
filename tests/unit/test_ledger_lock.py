"""Feature 019 US1: the ledger lock's stale reclaim is single-winner (FR-001/FR-002).

Contract: specs/019-api-state-robustness/contracts/lock-protocol.md.

The race test detects a double-grant deterministically: every acquirer, while
inside the critical section, re-reads the lock file and asserts it still carries
its OWN token. Under the old check -> unlink -> recreate reclaim, a second
reclaimer deletes the first winner's fresh lock and stamps its own, so the first
holder observes a foreign token (and the holder counter exceeds 1). The window is
amplified with barrier-synchronized threads, a tiny GIL switch interval, and many
iterations — it trips reliably against the old implementation (falsification run
recorded in the T005/T006 commit) and never against the rename-based reclaim.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

import pytest

from specops import ledger
from specops.errors import SpecopsError

# Amplification knobs (G4 single-winner race).
_THREADS = 8
_ITERATIONS = 40


def _stale_lock(target: Path, age_seconds: float = 3600.0) -> Path:
    """Pre-create the lock sidecar as if leaked by a long-dead process."""
    lock = Path(str(target) + ".lock")
    lock.write_bytes(b"dead-process-token")
    old = time.time() - age_seconds
    os.utime(lock, (old, old))
    return lock


def _contend(
    target: Path,
    barrier: threading.Barrier,
    state: dict[str, int],
    state_lock: threading.Lock,
    violations: list[str],
) -> None:
    barrier.wait()
    try:
        lk = ledger._LedgerLock(target, timeout=5.0, stale=30.0)
        with lk:
            with state_lock:
                state["holders"] += 1
                state["max_holders"] = max(state["max_holders"], state["holders"])
            # Double-grant detector: while held, the lock file must still carry
            # OUR token; a foreign token means another contender re-reclaimed
            # our fresh lock (the TOCTOU).
            try:
                content = lk.lock_path.read_bytes()
            except OSError:
                violations.append("lock file vanished while held")
            else:
                if content != lk._token:
                    violations.append("foreign token while held")
            time.sleep(0.002)  # widen the held window
            with state_lock:
                state["holders"] -= 1
    except SpecopsError:
        pass  # timing out while a legitimate holder works is legal


def test_stale_reclaim_single_winner(tmp_path: Path) -> None:
    """G4: N contenders racing one stale lock — never two simultaneous holders."""
    target = tmp_path / "status.yaml"
    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)  # force dense thread interleaving in the race window
    try:
        for _ in range(_ITERATIONS):
            _stale_lock(target)
            barrier = threading.Barrier(_THREADS)
            state = {"holders": 0, "max_holders": 0}
            state_lock = threading.Lock()
            violations: list[str] = []
            threads = [
                threading.Thread(
                    target=_contend,
                    args=(target, barrier, state, state_lock, violations),
                )
                for _ in range(_THREADS)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert not violations, violations
            assert state["max_holders"] == 1, (
                f"double-grant: {state['max_holders']} simultaneous holders"
            )
            # Between iterations no lock artifacts may linger (all released).
            leftovers = [p.name for p in tmp_path.iterdir() if ".lock" in p.name]
            assert leftovers == [], leftovers
    finally:
        sys.setswitchinterval(old_interval)


def test_uncontended_acquire_release(tmp_path: Path) -> None:
    """G1: the fast path is a plain O_CREAT|O_EXCL create; release removes the file."""
    target = tmp_path / "status.yaml"
    lock = ledger._LedgerLock(target)
    with lock:
        assert lock.lock_path.is_file()
        assert lock.lock_path.read_bytes() == lock._token
    assert not lock.lock_path.exists()


def test_fresh_lock_times_out_with_exact_diagnostic(tmp_path: Path) -> None:
    """G2: a live (non-stale) lock blocks until timeout with the unchanged message."""
    target = tmp_path / "status.yaml"
    lock_path = Path(str(target) + ".lock")
    lock_path.write_bytes(b"live-holder")  # fresh mtime: not reclaimable
    with pytest.raises(SpecopsError) as exc, ledger._LedgerLock(
        target, timeout=0.2, stale=30.0
    ):
        pass  # pragma: no cover — must not acquire
    assert str(exc.value) == (
        f"Ledger is locked by another process: {lock_path.name}. Retry."
    )
    assert lock_path.read_bytes() == b"live-holder"  # never touched a live lock


def test_release_preserves_foreign_lock(tmp_path: Path) -> None:
    """G5: __exit__ only deletes a lock that still carries the owner's token."""
    target = tmp_path / "status.yaml"
    lock = ledger._LedgerLock(target)
    with lock:
        # Simulate a (buggy or racing) foreign overwrite while held.
        lock.lock_path.write_bytes(b"someone-else")
    assert lock.lock_path.read_bytes() == b"someone-else"  # not deleted by us


def test_reclaim_winner_crash_is_recoverable(tmp_path: Path) -> None:
    """G6: a reclaim winner that dies leaves a normal fresh lock, reclaimable by age."""
    target = tmp_path / "status.yaml"
    _stale_lock(target)

    winner = ledger._LedgerLock(target, timeout=1.0, stale=30.0)
    winner.__enter__()  # reclaims the stale lock, holds a fresh one
    assert winner.lock_path.read_bytes() == winner._token
    # Simulate the winner crashing: no __exit__; its lock goes stale by age.
    if winner._fd is not None:
        os.close(winner._fd)
    old = time.time() - 3600
    os.utime(winner.lock_path, (old, old))

    with ledger._LedgerLock(target, timeout=1.0, stale=30.0) as second:
        assert second.lock_path.read_bytes() == second._token
    assert not second.lock_path.exists()


def test_leaked_sentinel_does_not_wedge_reclaim_past_timeout(tmp_path: Path) -> None:
    """G4/G6: a `.reclaim` sentinel leaked by a crashed reclaimer must clear within
    the acquire deadline so a genuinely stale main lock is still reclaimed.

    Regresses the bug where the sentinel reused the main lock's `stale` (30 s) as
    its own leaked-age bound: with `timeout` (here 2 s) < 30 s, a young leaked
    sentinel blocked every waiter until it aged out — so a stale main lock failed
    to reclaim within `timeout` and raised "Ledger is locked by another process".
    """
    target = tmp_path / "status.yaml"
    _stale_lock(target)
    # Simulate a reclaimer that died AFTER creating the sentinel but BEFORE
    # unlinking the stale main lock: a fresh (age ~= 0) leaked sentinel.
    sentinel = Path(str(target) + ".lock.reclaim")
    sentinel.write_bytes(b"crashed-reclaimer-token")

    with ledger._LedgerLock(target, timeout=2.0, stale=30.0) as lk:
        assert lk.lock_path.read_bytes() == lk._token
    assert not lk.lock_path.exists()
    assert not sentinel.exists()  # leaked sentinel cleared, not left behind
