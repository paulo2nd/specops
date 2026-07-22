# Contract — Path Classification & Drift Gate

## Effective diff

- Command: `gitops.effective_diff(repo, baseline, end="HEAD")` → `git diff --name-only --no-renames <baseline>..HEAD`.
- **Baseline**: `ledger["baseline"]` (authoritative, set at `init-spec`); fallback merge-base(current, default) when absent.
- **Rename**: decomposed — old path `removed` + new path `added` (no similarity threshold).
- **Mode-only** change: included as `modified`.
- **`--path` override**: replaces Git derivation entirely (hermetic tests).
- **Degenerate**: clean tree / empty diff → empty result, exit `0`; not-a-repo / unresolvable baseline → exit `2` (never a silent empty result).

## Class precedence (first match wins)

1. `path ∈ acknowledgements` → **`discovered-and-acknowledged`**  *(discovery precedence — preserves execution-time provenance)*
2. `path ∈ plan-declared paths` (`speckit.parse_plan_path_action`) → **`planned`** (`attribution: plan-declared`)
3. map present **and** `path` owned by a plan-declared context (`speckit.parse_plan_context_ids` + `contextmap._candidates_for_path`) → **`planned`** (`attribution: owned-by:<ctx>`)
4. else → **`unexplained`**

Invariant: exactly one class per path; every path attributable (SC-002). No-map repos evaluate steps 1,2,4 only (SC-008).

## Drift gate (inside `specops review`)

- `review.GATE_ORDER` becomes `reconcile → lint → test → working-tree → drift`.
- The `drift` gate reuses the effective diff already computed by `_working_tree_gate`, classifies it, and:
  - **PASS** when zero `unexplained` paths (all `planned`/`discovered-and-acknowledged`).
  - **FAIL** (review REJECTED, exit `1`) listing only the `unexplained` paths.
- `planned` and `discovered-and-acknowledged` paths never FAIL the gate (0% false-block, SC-003).
- The pre-existing `digest_drift_warning` remains a **non-blocking** appended warning (map-digest drift ≠ path drift; SC-008).
