# Contract: Ledger Lock Protocol (hardened)

**Feature**: 019-api-state-robustness | **Date**: 2026-07-27 | Research: D1

The `_LedgerLock` in `src/specops/ledger.py` guards a ledger's read-modify-write
critical section via a `.lock` sidecar (`<status.yaml>.lock`). This contract fixes the
stale-reclaim race while preserving every other observable behavior.

## Guarantees

| # | Guarantee | Status |
|---|---|---|
| G1 | Uncontended acquire is a single `os.open(O_CREAT\|O_EXCL)` + token write | unchanged |
| G2 | A fresh lock held by a live process blocks contenders until `timeout` (5 s), then `SpecopsError` "Ledger is locked by another process …" | unchanged (message byte-identical) |
| G3 | A lock older than `stale` (30 s) is reclaimable (crash recovery) | unchanged |
| G4 | **Single-winner reclaim**: when N contenders observe the same stale lock, at most one acquires it | **NEW — the fix** |
| G5 | Release deletes the lock only when it still carries the owner's token | unchanged |
| G6 | A reclaim winner that itself dies leaves a lock that again becomes reclaimable by age | unchanged (its lock is a normal fresh lock) |
| G7 | `ledger.save`'s revision-CAS stays the durable lost-update authority | unchanged |

## Protocol

Acquire loop (per contender):

1. Try `os.open(lock, O_CREAT|O_EXCL|O_WRONLY)`; on success write + fsync the owner
   token (`pid:monotonic_ns`) → **held**.
2. On `FileExistsError`: stat mtime.
   - Not stale → sleep 50 ms, retry until deadline → timeout error (G2).
   - Stale → **atomic reclaim**: `os.rename(lock, lock + ".reclaim.<pid>.<ns>")`.
     - Rename succeeds → unlink the renamed file, loop to step 1 (compete normally).
     - Rename raises `FileNotFoundError`/`OSError` (someone else won, or the holder
       released) → loop (existing "lock vanished — retry" arm).
3. Release: close fd; unlink only if the file's content equals the owner token (G5).

Why the rename closes the race: the old protocol's reclaim was
*check-stale → unlink → recreate* — between B's staleness check and B's unlink, A may
have already reclaimed and created a **fresh** lock, which B then deletes. Rename makes
"take the stale file out of play" a single atomic step on one specific inode: exactly
one rename of a given name can succeed; every loser observes the name gone and re-enters
the normal create race.

Platform notes: `os.rename` to a non-existent destination is atomic on POSIX; on
Windows it succeeds because the stale holder is dead (no open handle). The unique
destination name (`pid` + `monotonic_ns`) can never collide between contenders.

## Regression test contract (FR-002 / SC-002)

`tests/unit/test_ledger_lock.py` MUST:

1. Create the lock file with an artificially old mtime (`os.utime`, > `stale`).
2. Release N (≥ 4) barrier-synchronized threads into `_LedgerLock.__enter__` on the
   same path (short `stale`, generous `timeout`).
3. Inside the critical section, each acquirer (a) increments a concurrency counter and
   asserts it reads 1, and (b) re-reads the lock file and asserts it equals **its own
   token** — under the old protocol a second reclaimer overwrites the file while the
   first holder is inside, so (b) trips deterministically whenever the race lands.
4. Loop the race (≥ 20 iterations) to amplify the window.
5. Also cover: normal contention (fresh lock → timeout diagnostics unchanged) and
   crash recovery (a reclaim winner's leaked lock is again reclaimable — G6).

The test MUST fail when run against the pre-change `_LedgerLock` (verified once during
implementation by temporarily reverting the reclaim arm) and pass repeatedly against
the new one.
