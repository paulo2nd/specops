# Contract: Stability Policy (`docs/stability.md`)

This defines the **structure and required content** of the published stability policy that
ships with the feature. `docs/stability.md` is the adopter-facing document; this contract is
what the policy MUST contain (the implementation renders it into prose + tables).

## Required sections

1. **Scope & audience** — who this is for (adopters building automation) and what "frozen"
   promises at 1.0.
2. **Frozen-surface table** — one row per surface, each classified **FROZEN**:

   | Surface | What it is | Version field | Additive change = | Breaking change = |
   |---|---|---|---|---|
   | `specops.json` | project config | *(none; preserve-unknown)* | new optional key | remove/rename/retype an existing key |
   | `status.yaml` | ledger (v7) | `schema_version` | new optional field / record | remove/rename/retype a required field |
   | `lane.yaml` | lane state (v1) | `schema_version` | new optional field | change top-level/sub-shape or `state` enum |
   | gate-profile file | gate suite config | `output_version` (1) | new optional profile/applies key | change/rename profile field or predicate key |
   | JSON envelope | `--json` command result | `output_version` (1) | new documented per-command key | remove/rename a base key or change a value enum |
   | exit codes | process exit status | *(the set {0,1,2})* | *(none — the set is closed)* | change a code's meaning or add a code |
   | findings-input | ingestion contract (v1) | `contract_version` | new optional finding field | change a required field or `contract_version` semantics |

3. **Per-surface field reference** — links to the authoritative field tables
   (`data-model.md` here; and the shipped contract docs `specs/012/…gate-profiles.config.md`,
   `specs/015/…findings-input.schema.json`, `specs/018/…cli-output.md`). The policy references
   them; it does not duplicate the field lists.
4. **The additive-vs-breaking rule** (general): additive = a new **optional** field/key that
   older consumers ignore safely; breaking = any removal, rename, retype, enum-value change,
   or semantic change of a frozen field/code. Stated once, then specialized per surface in the
   table above.
5. **Breaking-change announcement discipline** — a breaking change requires: a version bump on
   that surface's version field (or MAJOR release for the versionless/closed surfaces), the
   migration obligation (see `versioning-policy.md`), a CHANGELOG entry, and — for renames —
   the Feature 017 alias + deprecation-window discipline.
6. **What is NOT frozen** — internal module APIs, `templates/` literals, test fixtures, prose
   wording; and any surface the FR-003 sweep explicitly records as still-evolving (none at
   1.0 unless the sweep finds one).

## Acceptance (maps to spec)

- Every one of the seven surfaces appears with an explicit **FROZEN** class and both an
  additive-change and a breaking-change rule (FR-001, FR-002, SC-001).
- The FR-003 sweep result is recorded: either "no additional observable surface found" or the
  new surface + its class (SC-001).
- The document is linked from `README.md`, `README.pt-br.md`, `docs/commands.md`, and
  `CHANGELOG.md` (FR-011, SC-006).
