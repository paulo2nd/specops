# Phase 0 — Research: Context-Aware Planning and Impact

All decisions are grounded in the current worktree (Constitution Principle IV, Empirical
Verification). Symbol/line references are to the code as it exists on `main`.

## R1 — Map digest: canonical `sha256`, greenfield (corrects a spec Assumption)

**Decision**: Add `contextmap.map_digest(root) -> str | None`. It loads and `validate`s the map; on
a resolvable map it returns `sha256` (hex) over a **canonical serialization** of the parsed contexts
(each context reduced to a fixed-order mapping — `id`, sorted `match`, `reads` with sorted phase keys
and codepoint-ordered lists, sorted `dependencies`, sorted `gates`, `risk` with sorted keys — then
JSON-encoded with `sort_keys=True`, `ensure_ascii=False`, no whitespace). Absent map → `None`
(recorded as the explicit no-map marker). Invalid/ambiguous/unsupported map → the command that needs
the digest fails closed (FR-017); provenance recording instead stores a `map_invalid` marker (R6).

**Rationale**: Empirical check confirmed **no digest exists today** — the only `hashlib.sha256` in the
tree is `migration.py:92` (installation-backup checksums, unrelated). The spec Assumption "the map
digest is already available from Feature 008's outputs" is **false**; readiness item CHK034 is
resolved as *greenfield in 009*. A digest over the *parsed, normalized* map (not raw bytes) means
comment/whitespace/formatting changes do not spuriously change the digest, so digest drift (SC-008)
signals a genuine change in the map's *meaning*. `hashlib` is stdlib → no new dependency (Principle V).

**Alternatives considered**: (a) Hash raw file bytes — rejected: reports drift on cosmetic edits.
(b) Reuse a Feature 008 function — rejected: none exists. (c) Add the digest to Feature 008 instead —
rejected: 008 is merged and its non-goals excluded consumption; 009 owns it.

## R2 — Impact model: reverse adjacency + closed `{ownership, dependency, policy}` edge set

**Decision**: `context impact` (a) maps each changed path to its owning context via
`_candidates_for_path` (most-specific-wins; zero candidates → **unowned** observation, non-blocking);
(b) builds a **reverse adjacency** index `dependents[to] += from` from every context's
`dependencies` (the inverse of `_build_expanded`'s forward walk, `contextmap.py:516-541`); and
(c) performs a **cycle-safe DFS over reverse edges** from each directly-affected context to collect
transitive dependents. Every in-scope context is attributed, in the reason trace, to exactly one edge
type from the **closed set** `{ownership, dependency, policy}`:

- `ownership` — the context directly owns a changed path (a `match` hit).
- `dependency` — reached by a declared **reverse** dependency edge (`X depends on Y`, Y affected ⇒ X in scope).
- `policy` — reached by a declared gate/policy edge. **Defined and enforced but currently has no
  members**: Feature 008 models `Context.gates` as a per-context `list[str]` of gate IDs
  (`contextmap.py:94`), not cross-context policy edges, so no `policy` edge can pull a *different*
  context into scope until a future map-schema field expresses one. Gates/risks of already-in-scope
  contexts are still surfaced as metadata (US2).

**Rationale**: The clarification fixed impact as "who is affected by this change" (reverse), the
opposite of Feature 008 forward resolution. Confirmed `_build_expanded` is forward-only, so reverse
adjacency is net-new. Enumerating the edge set as *closed* makes SC-002 ("zero unexplained contexts")
objectively testable and forbids scope creep. Being honest that `policy` has no current members keeps
FR-007/FR-008 truthful against the real schema rather than asserting an edge the map cannot express.

**Alternatives considered**: (a) Both directions — rejected by clarification (over-broad scope).
(b) Add a cross-context policy edge to the map schema now — rejected: schema change to a merged
feature's artifact; out of scope; deferred to when a policy-edge field is warranted.

## R3 — Bounded-expansion trigger

**Decision**: Expansion follows **only** `ownership`/`dependency`/`policy` edges, so it is bounded by
construction. The `unbounded_expansion` condition (reported, not performed) fires when an expansion
step would require reaching a context **not attributable** to such an edge — concretely: a changed
path whose only owner is a catch-all/near-root pattern that would drag in effectively the whole map,
or a request that would compute a whole-map transitive closure. The command returns the
`unbounded_expansion` status (exit `1`) naming the offending path/pattern instead of reading the
repository wide.

**Rationale**: Ties FR-008 directly to R2's closed edge set, making "unbounded" decidable rather than
a vague adjective. Reuses the existing specificity comparator to recognize catch-all owners.

## R4 — Plan declaration surface (reuse the action-suffix convention)

**Decision**: A plan declares topology two ways, both parsed from `plan.md`:
1. **Declared paths** — the existing `` `path/to/x` (create|modify|remove) `` convention parsed by
   `speckit.parse_plan_path_action` (`speckit.py:105-123`), already used by `consistency.py:73-110`.
2. **Declared context IDs** — a new `speckit.parse_plan_context_ids(plan_text)` recognizing a
   SpecOps-owned declaration line (e.g. a `**SpecOps-Contexts**: api, api-auth, config` marker or a
   fenced `specops-contexts` block). Kept in `speckit.py` beside the other plan parsers.

`context plan-check` then validates: every declared ID exists in the map (FR-003, blocking); every
declared path's owning context is among the declared IDs (FR-004, blocking) unless the path is
**unowned** (non-blocking observation); a **missing** declaration while a map is present is blocking
(FR-002). Validation is **existence-agnostic** — it never checks the filesystem (R8 owns that).

**Rationale**: Reuses the proven, tested declaration convention rather than inventing a parallel one,
matching Principle IV's Empirical Verification (declared paths carry action suffixes). Keeps the
surface human-authorable and machine-parseable. Resolves readiness CHK001.

**Alternatives considered**: (a) A separate side-car declaration file — rejected: splits the plan's
source of truth. (b) Infer contexts from declared paths only (no explicit IDs) — rejected: FR-002/FR-003
require an explicit ID declaration that can be checked for existence and completeness.

## R5 — Ledger v2 → v3 provenance schema + migration + read-compat

**Decision**: Bump `ledger.CURRENT_SCHEMA` `2 → 3` (`ledger.py:32`) and extend the pure, idempotent
`migrate_to_current` (`ledger.py:154-196`) to add a `context_provenance` field to each **task record**
and each **review-cycle record**, backfilling the explicit no-map marker `{"map": "none"}` onto
records migrated from v2/v1. `validate_invariants` (`ledger.py:222-267`) is relaxed to accept records
with or without provenance (FR-018). Writes continue through `save(..., base_revision=…)`
(`ledger.py:455-486`) — atomic + revision-CAS, unchanged. `integration/test_ledger_migration.py`
gains v2→v3 coverage.

**Rationale**: Matches the exact Feature 006 pattern ("bump `CURRENT_SCHEMA`, extend
`migrate_to_current`"). An explicit marker (not field-absence) is what the clarification chose so
"no map" is unambiguous and machine-checkable. Resolves readiness CHK004/CHK025.

**Alternatives considered**: Omitting the field when no map exists — rejected by clarification
(ambiguous vs pre-feature records).

## R6 — Provenance content and markers

**Decision**: `context_provenance` is a generic object: `{"map": "none"}` (no map),
`{"map": "invalid"}` (map present but unresolvable at close time — recorded, does not block the
underlying status/review op which has its own gates), or
`{"map": "present", "digest": "<sha256>", "context_ids": ["…"], "output_version": 1}` when resolvable.
The `context_ids` are the contexts that directly **own** the record's **effective changed
paths** (task diff for a task record; the cycle's effective diff for a review record),
codepoint-ordered — what the change *touched*, not the reverse-dependent expansion `context
impact` surfaces for review scoping (which would over-report contexts the change never modified).
Domain-agnostic strings only (Principle V).

**Rationale**: Records exactly what SC-006/SC-008 need — reproduce which contexts and which map
version a record targeted — without coupling the ledger to context internals. Deterministic and
recomputable.

## R7 — `context impact` Git-default and degenerate cases

**Decision**: With explicit `--path` args, use them verbatim (bypass Git). With none, resolve the
baseline from the ledger `baseline` field and diff `baseline → HEAD` via
`gitops.name_only_diff(repo, baseline, "HEAD")` (`gitops.py:73-79`). Degenerate mapping (clarified):
clean tree / empty diff → **empty result, exit `0`** (`status` `impact_ok`); not a Git repo
(`gitops.is_git_repo` false) or no resolvable baseline (`gitops.is_ancestor` false / missing) →
**usage error, exit `2`** (`status` `usage_error`) with a clear message.

**Rationale**: Reuses the existing diff/baseline primitives; distinguishes "no input" (a supported
success) from "can't get input" (an input error) per the exit taxonomy. Resolves readiness CHK022.

## R8 — Stale detection over Git-tracked files, symlink-by-path

**Decision**: `context stale` loads+`validate`s the map (fail closed if unresolvable), lists
**Git-tracked** files (`repo.git.ls_files()` — the tracked-membership idiom already used at
`consistency.py:104` via `ls_files --error-unmatch`), and for each context's `match` patterns reports
those matching **zero** tracked files as stale, with the owning context, codepoint-ordered. Symlinks
are matched by their own path entry (as `ls-files` lists them) and never followed (no traversal).
Operates on the **context map's** patterns only — never on a plan's create-target paths — so
create-targets are never reported as stale, and plan-topology validation stays existence-agnostic (R4).

**Rationale**: Git-tracked membership is deterministic and reproducible from the committed/staged tree
(SC-001/SC-005), ignoring environment-specific untracked/gitignored artifacts. Resolves readiness
CHK009/CHK032.

**Alternatives considered**: Walking the filesystem — rejected: non-deterministic across environments.

## R9 — Phase-token mapping

**Decision**: The lifecycle phases named in the spec map onto Feature 008's `PHASES`
(`contextmap.py:39`, lowercase `("specify","plan","tasks","implement","review")`): planning → `plan`,
implementation → `implement`, review → `review` (`specify`/`tasks` remain available). Phase-scoped
display (FR-001) reuses the existing `context resolve --phase <token>`; no new resolve command is
built. Documented so the closed phase list is authoritative (readiness CHK005).

**Rationale**: Avoids a second phase vocabulary; note that the *ledger* `PHASES` are uppercase
(`ledger.py:36`) and distinct — the context phase tokens are the map's, not the ledger's.

## R10 — New `S_*` statuses and exit taxonomy for the three commands

**Decision**: Add statuses to `contextmap.py:50-61` and map them in `_CLASS_FOR_STATUS`
(`contextmap.py:64-77`): `plan_check_ok`, `impact_ok`, `stale_ok` → PASS (0); `stale_found`,
`unknown_declared_context`, `undeclared_owner`, `missing_declaration`, `unbounded_expansion` → the
appropriate class (see contracts) with blocking ones GATE_REJECTION (1); `unowned` is carried as a
non-blocking detail inside a PASS result. Reuse `S_MALFORMED`/`S_SCHEMA_INVALID`/
`S_UNSUPPORTED_VERSION`/`S_AMBIGUOUS` for fail-closed map states (FR-017). Every command returns a
`CommandResult` rendered by the existing `_emit_context` bridge (`cli.py:450-461`).

**Rationale**: One outcome contract across all context commands (Principle VI); reuses the tested
`outcome.render` + `CommandResult.exit_code` machinery. Resolves readiness CHK008 (error/status shape).

## R11 — Directive wiring and MINOR constitution amendment

**Decision**: Extend three injected directive templates additively:
`templates/directives/plan.md` (run `context plan-check`; declare context IDs),
`templates/directives/implement.md` (provenance recorded at task close),
`templates/directives/review.md` (scope review by `context impact`; surface the **non-blocking**
digest-drift warning). Because these are Principle IV directives, bump the constitution `1.4.0 → 1.5.0`
(MINOR: additive extension of existing directives, no principle removed/redefined), update the Sync
Impact Report, and submit for explicit human approval (roadmap §3). Directives degrade to no-ops where
SpecOps/the map is absent (roadmap Rule 5).

**Rationale**: The feature's mandate *is* integrating context into planning/implementation/review,
which is the directives' domain; delivering only standalone commands would leave the roadmap outcome
"display the minimum context package at each phase" unmet. The change is small and governed.

## R12 — Determinism inputs

**Decision**: Every new output (digest, impact, plan-check, stale) is a pure function of the parsed
map + declared inputs + (for impact/stale) the Git-tracked/diff set: canonical serialization for the
digest, Unicode-codepoint ordering for every list, no timestamps, `output_version: 1` on JSON
envelopes (reusing `contextmap.OUTPUT_VERSION`). This mirrors Feature 008's determinism discipline and
satisfies SC-001.

**Rationale**: Determinism is the feature's central testability guarantee; reusing 008's proven
ordering rules keeps it consistent.

---

**NEEDS CLARIFICATION**: none. All prior clarifications and the deferred readiness items are resolved
above; remaining `readiness.md` items are internal-consistency verifications addressed in
[data-model.md](./data-model.md) and [contracts/](./contracts/).
