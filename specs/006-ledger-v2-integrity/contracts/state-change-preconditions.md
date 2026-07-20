# Contract: State-Change Precondition Gate

Every state-changing `specops status` command (`init-spec`, `start-task`, `complete-task`,
`transition-phase`, and the new `migrate`) MUST pass this ordered gate before it writes. The gate is
implemented once (in `ledger.py`, called from `status.py`) so all commands share identical behavior.
Read-only commands (`show`, `reconcile`, `consistency`) do **not** run this gate.

## Ordered precondition sequence

For a state-changing command on the active feature:

1. **Resolve Git repo** — not a repo ⇒ exit 1 (existing `_require_git`).
2. **Resolve feature** — `speckit.resolve_feature_dir(root)`; unresolvable/ambiguous ⇒ fail closed,
   exit 1 (FR-020).
3. **Load ledger** — read raw dict + capture `base_revision`. Unparseable ⇒ `LedgerParseError`,
   exit 2. (`init-spec` instead requires the ledger be **absent**.)
4. **Classify schema** (FR-002):
   - `too_new` ⇒ refuse, exit 1, "requires a newer SpecOps version" (FR-005). No write.
   - `unsupported` ⇒ refuse, exit 1, "unsupported ledger shape" (FR-006). No write.
   - `migratable` ⇒ back up original (FR-008a), migrate in memory (FR-008b auto-trigger).
   - `current` ⇒ continue.
5. **Validate workspace identity** (FR-018/019) — check feature, branch, baseline in that order;
   first mismatch ⇒ refuse, exit 1, naming the diverged dimension. No write. Baseline check uses
   `gitops.is_ancestor(repo, ledger.baseline)` (FR-017a). The refusal message points the user at
   `specops status rebaseline` (FR-019a) — the explicit escape hatch that re-anchors branch +
   baseline to the current workspace after a deliberate rename/rewrite, but never crosses the
   feature identity. `cmd_migrate` runs this same identity check (it is a write path).
6. **Capture baseline invariants** — record `validate_invariants(data)` at load time as
   `base_violations` (pre-existing legacy defects). These are tolerated; only violations a
   command *newly introduces* are fatal (FR-025). This prevents a legacy ledger from being
   permanently locked out while still refusing to write new invalid state.
7. **Apply the command mutation** in memory.
8. **Re-validate invariants** on the mutated data; block only on violations **not** in
   `base_violations` (newly introduced by this command). No write on a new violation.
9. **Save with CAS** — `ledger.save(feature_dir, data, base_revision=base_revision)`:
   - on-disk `revision != base_revision` ⇒ `StaleLedgerError`, exit 1, "ledger moved on — re-read
     and retry" (FR-013/015). No write.
   - logical content unchanged ⇒ stable no-op, no write, no revision bump (FR-011).
   - otherwise atomic write with `revision = base_revision + 1` (FR-012, FR-022).

Any failure in steps 2–9 leaves the on-disk ledger **unmodified**.

## Idempotency & interruption guarantees

- Re-running a command that produces no logical change yields a byte-stable ledger (SC-005).
- An interruption at any point during step 9 leaves the previous complete, valid ledger readable
  (SC-004); a migration interrupted before step 9 leaves the original ledger intact and its backup
  present.
- Migration triggered in step 4 and the command's own mutation are committed in a **single** atomic
  write (one revision advance), not two.

## Read-only contract (no gate)

`show`, `reconcile`, `consistency` and future diagnostics:

- MUST NOT migrate or write (FR-007/FR-021).
- MUST remain available for `current`, `migratable`, `too_new`, `unsupported`, and malformed
  ledgers, reporting best-effort status + a clear diagnostic rather than failing destructively
  (FR-029a). `reconcile` keeps emitting identity divergence as **warnings**, not blocking errors.
