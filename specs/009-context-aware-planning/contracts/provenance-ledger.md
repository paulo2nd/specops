# Contract: Map Digest + Ledger v3 Provenance

Covers the greenfield map digest (R1) and the Ledger `v2 → v3` provenance extension (R5/R6).
FR-009/010/018; SC-006/008.

## Map digest

| Aspect | Contract |
|---|---|
| Function | `contextmap.map_digest(root: Path) -> str \| None` |
| Algorithm | `sha256` hex over the canonical JSON of parsed contexts (fixed key order per context: `id`, sorted `match`, `reads` sorted phase keys + codepoint-ordered lists, sorted `dependencies`, sorted `gates`, `risk` sorted keys; `json.dumps(sort_keys=True, ensure_ascii=False, separators=(",", ":"))`). |
| Absent map | returns `None` |
| Invalid/ambiguous/unsupported map | raises no digest; the calling read command fails closed (FR-017); provenance recording stores `{"map": "invalid"}` (R6) |
| Dependency | stdlib `hashlib` only — **no new runtime dependency** |
| Determinism | invariant to comments/whitespace/key-order in the source file (SC-008 measures *meaning* changes) |

## Ledger schema bump `v2 → v3`

| Change | Location |
|---|---|
| `CURRENT_SCHEMA = 3` (was 2) | `ledger.py:32` |
| `migrate_to_current`: for each `tasks[]` and each `review_cycles[]` record lacking `context_provenance`, add `{"map": "none"}`; idempotent, pure, deterministic | `ledger.py:154-196` |
| `validate_invariants`: accept records with or without `context_provenance`; if present, require a valid variant shape | `ledger.py:222-267` |
| `OLDEST_SUPPORTED` stays `1` | `ledger.py:33` |

Migration is exercised in `tests/integration/test_ledger_migration.py` (v1→v3 and v2→v3), asserting
prior ledgers remain readable (FR-018, SC-006) and records without provenance are a valid supported
shape.

## Provenance record (`context_provenance`)

Present on **every** task record and **every** review-cycle record (FR-009).

```yaml
# no map in repo
context_provenance: {map: none}

# map present but unresolvable at close time (recorded; does not block the op)
context_provenance: {map: invalid}

# resolvable map
context_provenance:
  map: present
  digest: "9f2c…"          # contextmap.map_digest at close time
  context_ids: [api, web]   # owning + reverse-impacted contexts for the record's effective paths
  output_version: 1
```

Rules:

1. **Content** — `context_ids` are the contexts that directly **own** the record's **effective
   changed paths** (task diff for a task; cycle diff for a review), codepoint-ordered. Provenance
   records what the change *touched* — the owning contexts — not the reverse-dependent expansion
   `context impact` surfaces for review scoping (which would over-report contexts the change never
   modified). A residually-ambiguous path (an unbroken specificity tie) is not attributed.
2. **Recording sites** — task provenance is written by `status.py` at task close; review provenance by
   `review.py` at cycle record. Both go through the existing atomic + revision-CAS `ledger.save(...,
   base_revision=…)` (`ledger.py:455-486`); recording is interruption-safe and lost-update-safe.
3. **Does not block** — an `invalid` map marker records the condition but does not fail the underlying
   `status`/`review` operation (those keep their own gates); the fail-closed rule (FR-017) applies to
   the read-only `context` commands, not to provenance side-effects.
4. **Digest drift (SC-008)** — the review directive compares the plan-time provenance digest with the
   current digest; a difference is surfaced as a **non-blocking warning** (exit `0`) and remains
   visible in provenance. It never blocks review in this feature (enforcement is Feature 010).
5. **Domain-agnostic** — strings and a small marker only; no coupling to context internals (Principle V).
6. **Determinism** — identical map + effective paths → identical `context_provenance` (recomputable).
