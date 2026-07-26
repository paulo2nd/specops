# Contract: Promoted Internal API (old → new names)

**Scope**: helpers consumed across production module boundaries. These are *internal contracts for maintainers and tests*, not a supported external API (see spec Assumptions); stability is governed by changelog discipline, not semver on Python imports.

**Policy** (research.md D3): rename in place, document the contract at the definition site, remove the old name — no aliases. Two grammar owners move instead (D5/D6) because co-location is their purpose. After this feature, a cross-module reference to an underscore-prefixed name in `src/specops/` is a defect (SC-002).

## Renames in place

| Old (private) | New (public) | Consumers today | Contract summary |
|---|---|---|---|
| `status._load_for_write` | `status.load_for_write` | handoff, trace | resolve + load ledger for mutation; raises on missing/invalid state |
| `status._finalize` | `status.finalize` | handoff ×9, trace | persist mutated ledger (revision CAS + atomic write) |
| `status._get_feature_dir` | `status.get_feature_dir` | handoff, trace | resolve active feature dir from `.specify/feature.json` |
| `ledger._ledger_path` | `ledger.ledger_path` | lane ×5 | canonical `status.yaml` path for a feature dir |
| `trace._norm` | `trace.norm_path` | handoff ×3, ingestion ×2 | normalize a path to repo-relative POSIX form |
| `trace._is_managed` | `trace.is_managed` | lane ×2 | is path SpecOps/Speckit methodology state (excluded from drift) |
| `contextmap._matches` | `contextmap.matches` | gateprofiles | gitignore-style pattern match |
| `contextmap._classify_pattern` | `contextmap.classify_pattern` | gateprofiles | pattern → specificity class |
| `contextmap._candidates_for_path` | `contextmap.candidates_for_path` | trace | contexts whose patterns cover a path |
| `contextmap._RESOLVABLE` | `contextmap.RESOLVABLE` | trace | statuses with usable context resolution |
| `contextmap._CLASS_FOR_STATUS` | `contextmap.CLASS_FOR_STATUS` | doctor | contextmap status → outcome class map |
| `review._profile_gates` | `review.profile_gates` | lane | gate-profile suite execution entry |
| `review._existing_evidence` | `review.existing_evidence` | cli | evidence records usable for gate caching |
| `gateprofiles._affected_for` | `gateprofiles.affected_for` | review | inputs covered by a profile for a diff |
| `handoff._canonical` | `handoff.canonical_finding` | sarif | canonical dict form of a finding for export |
| `initializer._install_review` | `initializer.install_review` | extension | install the review command asset |
| `initializer._scan_markers` | `initializer.scan_markers` | migration | locate legacy marker blocks |

## Moves (grammar owners)

| Old home | New home | Consumers |
|---|---|---|
| `status._validate_evidence` (+ `_PART_RE`, `EVIDENCE_CLASSES`) | `evidence.validate_string` (+ module constants) | status (task close), handoff (finding close) |
| `trace._FINDING_RE` + `handoff.render_revision_text`'s line formatting | `findings.parse_finding_line` / `findings.format_finding_line` | trace, handoff, sarif |
| finding base-dict literals (handoff ×3) | `findings.new_finding(...)` | handoff (authoring, import preview, import apply) |

## Obligations

1. Each new name carries a docstring stating inputs, outputs, and error behavior (FR-004) — the documented contract *is* the deliverable, not just the rename.
2. Production and test references are updated in the same change set; behavior-level tests move to the public surface where it expresses the same assertion (FR-014).
3. `cli.py`'s `_emit` stays private by design: it has exactly one consumer module (itself) — the rule targets *cross-module* consumption.
4. Verification: the SC-002 static scan (see quickstart) reports zero cross-module underscore references in `src/specops/`.
