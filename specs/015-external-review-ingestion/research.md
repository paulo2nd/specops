# Research: External Review Ingestion (Phase 0)

All decisions were verified against the current repository (roadmap Rule 3). No
`NEEDS CLARIFICATION` remains; the three spec clarifications (content identity,
all-or-nothing, per-finding staleness) are the inputs to R1/R3/R4 below.

## R1 — Finding identity / idempotency key

- **Decision**: Content identity = the tuple **(producer, rule, file, line, action)**, digest-**independent**. A re-import whose normalized finding equals an existing finding by this tuple is a *match* (update in place); otherwise a new finding via `handoff._next_id` (`R<round>-F<NN>`). Within-document duplicates collapse by the same tuple.
- **Rationale**: Matches spec §Clarifications/FR-008. Keeping the reviewed-diff digest out of identity is what lets re-import after diff movement refresh staleness without duplicating (FR-009). Producer is part of identity so two tools reporting the "same" line are distinct, attributable findings.
- **Alternatives rejected**: (a) identity including the digest → re-import accumulates duplicates, contradicting FR-009; (b) producer-supplied stable ID as key → couples to producers that emit IDs, weakening stack-neutrality (many JSON/SARIF sources omit stable IDs).
- **Repo anchor**: `handoff._next_id`, `handoff._find_by_id`, `handoff._canonical` (canonical sort already includes file/line/severity/id). Identity check is a new pure helper in `ingestion.py`.

## R2 — Where ingestion logic lives

- **Decision**: New pure module `src/specops/ingestion.py` for parse/validate/map/identity/digest/staleness (no I/O). Three thin state-changing commands added to `handoff.py` (`cmd_finding_import_json`, `cmd_finding_import_sarif`, `cmd_finding_promote`) reuse `handoff._load_write` → `status._finalize` for the atomic + revision-CAS write.
- **Rationale**: Mirrors the existing `sarif.py` (pure projection) vs `handoff.py` (state) split. Ledger mutation stays behind the one audited write preamble (Principle II). Pure parsing is unit-testable without a git repo.
- **Alternatives rejected**: Putting everything in `handoff.py` (already 639 lines, mixes concerns); a standalone command group outside `handoff` (imported findings ARE handoff findings — FR-002/FR-017 forbid a parallel store).

## R3 — All-or-nothing import semantics

- **Decision**: Parse and validate the **entire** document first, accumulating every defect — structural (unknown/unsupported contract version, missing required field, invalid SARIF, missing producer) **and** per-result (a SARIF result with no usable location, FR-012). If the defect list is non-empty → return `BAD_ARGS` (exit `2`) naming **all** defects and write nothing. Otherwise apply every finding in a single `status._finalize`.
- **Rationale**: Spec §Clarifications + FR-013. The Feature 011 write preamble is already single-transaction, so "no partial state" is naturally atomic. Reconciles the FR-012/FR-013 tension: a per-result defect is *named*, never silently dropped, and never a partial import.
- **Alternatives rejected**: Import-valid-report-skipped (state depends on which findings were malformed — weakens determinism/idempotency); placeholder-defect findings (adds a new finding sub-state, more surface, against the "no new lifecycle" constraint).
- **Repo anchor**: `handoff.cmd_finding_add` shows the fail-closed `BAD_ARGS` pattern; `status._finalize` is the atomic commit point.

## R4 — Reviewed-diff digest & per-finding staleness

- **Decision**: Staleness is **per finding, against its own location**. At import, store `reviewed_digest` = the **git blob SHA** of the finding's `file` at the reviewed commit (the commit the producer names, else current `HEAD`), via a new `gitops.blob_sha(repo, rev, path)`. At **report time** (read-only), recompute the current blob SHA of `file` at `HEAD`; `stale = (stored reviewed_digest != current blob SHA)`. A file that no longer exists at HEAD is stale (target removed). A matching re-import refreshes the stored `reviewed_digest` in place (the FR-009 "except staleness" clause).
- **Rationale**: Spec §Clarifications + FR-004/FR-010. Git's blob hash is a deterministic, offline, stack-neutral, per-path content digest — a change to any other file does not stale a finding whose target is unchanged. Reuses the Feature 009/010 digest-drift *pattern* (a stored digest compared to a recomputed one) without adding a drift **gate**.
- **Alternatives rejected**: One feature-wide effective-diff digest (any commit mass-stales everything — signal collapses to "anything changed"); per-hunk/line digest (needs producer line ranges + blame; over-engineered for "the path it flagged changed"); commit-range identity (sensitive to rebase/squash, FR framing is content not commit-identity).
- **Repo anchor**: `gitops.effective_diff_status` / `commits_in_range` (existing git access); `contextmap.map_digest` shows the stored-digest pattern. `blob_sha` implemented with `repo.commit(rev).tree / path` → `.hexsha`, guarded for missing paths.

## R5 — SARIF input adapter

- **Decision**: Optional, dependency-free. `ingestion.parse_sarif(doc)` reads a SARIF 2.1.0 document, maps each `runs[].results[]` to a normalized finding: `ruleId → rule`, `message.text → action`, primary physical location → `file`(+`line`), and records `runs[].tool.driver.{name,version}` as the producer. Severity: **every** imported result lands `advisory` (FR-005); the SARIF `level` is retained only as informational. Reuses `sarif.SARIF_VERSION` and the inverse of `sarif._LEVEL`. Version mismatch or a result with no usable physical location → a defect (all-or-nothing, R3).
- **Primary-location rule**: the first `locations[]` entry bearing a `physicalLocation.artifactLocation.uri`; `region.startLine` → `line` when present. No usable physical location on a result ⇒ per-result defect (R3), never dropped.
- **Rationale**: FR-011/FR-012, roadmap acceptance gate (two producers). Symmetric with the Feature 012 output adapter so the pair round-trips rule/location/severity.
- **Alternatives rejected**: Adding a SARIF library dependency (breaks offline/minimal-deps posture; output adapter proved plain-dict is enough); honoring SARIF `level` to set `blocking` (violates advisory-by-default — no external input raises severity).

## R6 — Promotion (advisory → blocking) and Feature 011 compatibility

- **Decision**: `handoff.cmd_finding_promote(fid, *, closure, expected_evidence)` flips `severity` to `blocking`, records a `promotion` object (`{at: <ts>}`, audited), and sets `closure_criteria`/`expected_evidence` — which Feature 011 **requires** of any blocking finding (`cmd_finding_add` rejects a blocking finding without them, and `validate` flags `MISSING_CLOSURE`). The promoted finding then flows through the unchanged `fix → verify` lifecycle and gates approval via the existing `blocking_approval_check`. Withdrawal/demotion reuses the existing `cmd_finding_dismiss` (terminal `DISMISSED`) — no new mechanism (spec FR-006, resolves checklist CHK005). A matching re-import never overwrites `promotion`/`severity`/`closure` (FR-007); it only refreshes `reviewed_digest`.
- **Rationale**: FR-006/FR-007/FR-017. Promotion must attach closure + expected evidence or the blocking finding is un-verifiable and `validate` would report it defective — so promotion is the natural point to capture them.
- **Repo anchor**: `handoff.cmd_finding_add` (blocking requires `expected_evidence`+`closure`), `handoff.cmd_finding_dismiss` (existing withdrawal), `handoff.blocking_approval_check`, `ledger.finding_structural_defects` (`FINDING_DEFECT_MISSING_CLOSURE`).

## R7 — Ledger schema v6 → v7

- **Decision**: Bump `ledger.CURRENT_SCHEMA` 6 → 7. The new finding fields (`producer`, `reviewed_digest`, `imported`, `promotion`) are **optional** and appear only on imported findings, so `migrate_to_current` needs only the version bump (no backfill — a pre-feature finding simply lacks them and is a non-imported finding). `finding_structural_defects` is updated to **accept** the new optional fields (never flag their presence/absence as a defect). Forward-migration test upgrades a v6 ledger (findings without the new fields) with zero data loss.
- **Rationale**: FR-015, roadmap "persisted formats are versioned with forward migration tests". Additive, so v6 reads remain valid (Rule 5 degrade).
- **Alternatives rejected**: A required backfill (unnecessary — absence is meaningful: "not imported"); a separate top-level ingestion list (a parallel store, forbidden by FR-002).
- **Repo anchor**: `ledger.CURRENT_SCHEMA`, `ledger.migrate_to_current`, `ledger.backfill_*` (pattern), `tests/unit/test_ledger_v6_migration.py` (test template).

## R8 — Read-only staleness in `handoff report`

- **Decision**: Extend `handoff._finding_view` / `cmd_report` to include `producer`, `reviewed_digest`, and a computed `stale` boolean (+ current digest). `cmd_report` acquires the repo via `gitops.find_repo` to recompute per-location digests; it performs **no** writes (staleness is derived, not stored), preserving the FR-016 read-only guarantee (verifiable by before/after ledger comparison). JSON output keeps `OUTPUT_VERSION` and adds the fields additively.
- **Rationale**: FR-010/FR-016/FR-017. Computing staleness at read time keeps it always-current and avoids a write on read; the stored `reviewed_digest` is only ever written by import/promote.
- **Alternatives rejected**: Storing a `stale` flag (would require a write on read, or go stale itself); a separate `handoff staleness` command (report is the natural, existing surface).

## Cross-cutting: determinism, exit codes, EN/PT docs

- **Determinism/idempotency** (FR-008/FR-009): normalized findings are sorted by content identity before assigning IDs; the write path already serializes deterministically (`ledger.atomic_write`). Covered by a byte-identical re-import unit test.
- **Exit-code taxonomy** (FR-018): reuse `HandoffResult` + `outcome` (`PASS`/`GATE_REJECTION`/`INFRA_ERROR` → 0/1/2). New statuses: `findings_imported` (PASS), `finding_promoted` (PASS); malformed input → `BAD_ARGS` (exit 2). Empty-but-valid document → PASS no-op.
- **EN/PT docs** (FR-020): README + README.pt-br + CHANGELOG updated in the same change set; behavioral equivalence verified by review.
