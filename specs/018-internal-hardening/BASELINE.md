# Baseline Measurements — Feature 018 Internal Hardening

Recorded before any refactor lands (T003). Source of truth for the PR description
comparisons (SC-002, SC-005). All numbers on the `018-internal-hardening` branch tip
prior to Phase 2.

## Baseline commit

- SHA: `0c6091f4aaaaa8b6e8d6cb642451123813d8b909`
- Branch: `018-internal-hardening`

## Test suite (full, with coverage)

- `pytest tests/ -q`: **898 passed**
- Wall-clock: **2m36s** (real 2m36.617s)
- Coverage: **87.07%** (floor 85%)

## Test suite (integration only, no coverage)

- `pytest tests/integration/ -q -o addopts=''`: **260 passed**
- Wall-clock: **95.49s (1m35s)**
- SC-005 target after US4: ≤ **66.8s** (≥30% reduction)

## SC-002 cross-module private references

- Baseline: **38** sites (tasks.md/quickstart quoted 39 at the research commit `cb72e21`;
  measured 38 at the branch tip `0c6091f`). Target after US2: **0**.

Full inventory (module.attr → sites):

| Consumer | Private target | Sites |
|---|---|---|
| handoff.py | `status._finalize` | 9 |
| lane.py | `ledger._ledger_path` | 5 |
| handoff.py | `trace._norm` | 3 |
| ingestion.py | `trace._norm` | 2 |
| lane.py | `trace._is_managed` | 2 |
| handoff.py | `status._get_feature_dir` / `status._load_for_write` / `status._validate_evidence` / `trace._FINDING_RE` | 1 each |
| trace.py | `status._finalize` / `status._get_feature_dir` / `status._load_for_write` / `contextmap._candidates_for_path` / `contextmap._RESOLVABLE` | 1 each |
| cli.py | `review._existing_evidence` | 1 |
| doctor.py | `contextmap._CLASS_FOR_STATUS` | 1 |
| extension.py | `initializer._install_review` | 1 |
| gateprofiles.py | `contextmap._matches` / `contextmap._classify_pattern` | 1 each |
| migration.py | `initializer._scan_markers` | 1 |
| review.py | `gateprofiles._affected_for` | 1 |
| sarif.py | `handoff._canonical` | 1 |
