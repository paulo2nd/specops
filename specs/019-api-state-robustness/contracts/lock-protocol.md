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
   - Lock vanished between checks (`OSError`) → retry immediately.
   - Stale → attempt the **reclaim mutex**: create `<lock>.reclaim` with
     `O_CREAT|O_EXCL`.
     - Won the sentinel → **re-check the main lock's staleness under the mutex**;
       unlink it only if still stale (a fresh lock means a winner already recreated
       it — never touched); release the sentinel token-checked; loop to step 1
       (compete normally).
     - Sentinel exists (a reclaim is in flight) → if the *sentinel* itself is stale
       (a reclaimer crashed mid-reclaim), unlink it so a later pass retries; either
       way fall through to the ordinary wait (deadline check + 50 ms sleep).
   - Not stale → deadline check → sleep 50 ms, retry; on deadline, timeout error (G2).
3. Release: close fd; unlink only if the file's content equals the owner token (G5).

Why the mutex closes the race: the old protocol's reclaim was
*check-stale → unlink → recreate* — between B's staleness check and B's unlink, A may
have already reclaimed and created a **fresh** lock, which B then deletes. No
name-based single step can fix this (POSIX has no compare-and-unlink, and a rename
grabs whatever inode currently holds the name — the plan's first design was falsified
by this contract's own regression test, which observed 3 simultaneous holders under
rename-based reclaim). Serializing removal through an exclusive sentinel and
re-checking staleness **under** the mutex means the only process that may unlink the
main lock has just verified it is still the abandoned one.

Residual scope: with G3's single-crash assumption (a stale lock's owner is dead),
reclaim is exactly single-winner and a fresh lock is never deleted. Scenarios
requiring a *second* crash (a reclaimer dying mid-reclaim) recover by sentinel age
with the same bounded discipline, and the revision-CAS (G7) remains the durable
backstop throughout.

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
