# Contract: `lane.yaml` record schema (v1)

Authoritative structure and invariants for the dedicated lightweight-lane record. Full field
shapes and the state-transition diagram live in [data-model.md](../data-model.md); this file is
the terse conformance contract that `lane.py` and its unit tests validate against.

## Top-level keys (required unless noted)

| key | type | notes |
|-----|------|-------|
| `schema_version` | int | MUST be `1`. Independent of `status.yaml`'s `CURRENT_SCHEMA`. |
| `lane_id` | str | feature dir name (stable identity). |
| `feature` | str | feature name. |
| `branch` | str | branch at `lane start`. |
| `baseline` | str | HEAD sha at `lane start`; MUST exist in clone. |
| `created_at` / `updated_at` | str | RFC3339 UTC (`ledger.now_utc`). |
| `state` | str | `OPEN` \| `CLOSED` \| `PROMOTED`. |
| `eligibility` | map | see data-model §1; `confirmed` MUST be `true` to open. |
| `decisions` | list | append-only stop-and-ask log; may be empty. |
| `closure` | map \| null | non-null iff `state == CLOSED`. |
| `promotion` | map \| null | non-null iff `state == PROMOTED`. |

## Invariants (enforced by `lane.py`, asserted in `tests/unit/test_lane.py`)

- **INV-1**: `schema_version == 1`; an unknown/newer value is a hard parse error (exit 2),
  mirroring the ledger's version classification posture.
- **INV-2**: `state` terminal (`CLOSED`/`PROMOTED`) ⇒ exactly one of `closure`/`promotion` set;
  `OPEN` ⇒ both null.
- **INV-3**: no bypass field exists on a `decisions[]` entry — the schema cannot express
  "record reason and continue" (FR-008 by construction).
- **INV-4**: every commit sha recorded in `closure`/`promotion` is reachable from HEAD
  (`gitops.is_ancestor`) — the Principle II reachability invariant.
- **INV-5**: the record is only written through `lane.py` save helpers (atomic write with
  `updated_at` refresh); there is no supported hand-edit path.
- **INV-6**: creating `lane.yaml` when `status.yaml` already exists is refused (a feature is
  either full-lane or lite-lane, never both simultaneously); and vice-versa `lane promote`
  refuses when `status.yaml` already exists.

## Relationship to `status.yaml`

`lane.yaml` and `status.yaml` are mutually exclusive during a feature's active life. Promotion is
the **only** bridge: it reads `lane.yaml` + Git history and *synthesizes* `status.yaml` at PLAN
with additive provenance keys (`promoted_from_lane`, `lane_provenance`). No `status.yaml` schema
bump is required (the keys are additive on v6).
