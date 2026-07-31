# Research: Context Read-Set Consumption in IMPLEMENT

**Feature**: 023-context-readset-implement | **Date**: 2026-07-31

All findings below were verified against the worktree (Empirical Verification,
Principle IV) — file/line references are to the current `main`-derived branch
state, not memory.

## R1 — Resolution invocation pattern: feature-level, per declared context id

**Decision**: at IMPLEMENT session start (before the first task), the directive
instructs the agent to read the `**SpecOps-Contexts**: …` line from the active
feature's `plan.md` and run, for each declared context id:

```
specops context resolve --id <cid> --phase implement --json
```

(`--json` is required: the package — `read_set`, `expanded_read_set` — is
emitted only in the JSON envelope; the human output is a one-line summary.)

The session's **context package** is the union of each resolved package's
`read_set` plus `expanded_read_set`. Task-level reads are scoped to this union
for the whole session.

**Rationale**:

- Read sets are **context-granular**, not file-granular
  (`contextmap.py:515` `_read_set_for(ctx, phase)` keys on the context's
  `reads` mapping). Resolving per task path returns the same package as
  resolving the path's owning context id — no additional information.
- Coverage is already guaranteed by the plan gate: `context plan-check`
  (required at plan time by the plan directive) **blocks** when any
  plan-declared path is owned by a context missing from the declaration
  (`S_UNDECLARED_OWNER`, `contextmap.py:1008-1014`). Therefore every task's
  prescribed paths resolve to a declared context, and the union of
  declared-context packages covers each task's reads — exactly the feature's
  acceptance gate.
- One `resolve` call per declared context (typically 1–3 per feature) is the
  token-minimal pattern consistent with the methodology's token-optimization
  ethos; per-task invocation would multiply calls by task count.

**Alternatives considered**:

- **Per-task `--path` resolution** (`resolve --path <task-path> --phase
  implement` at each `start-task`): rejected — same packages as the id-based
  union (see coverage argument above), many more invocations, and it requires
  the agent to pick "the task's path" from tasks.md at runtime, an
  interpretation step the feature-level pattern avoids.
- **Single `plan-check --phase implement` call**: attractive (one call, all
  declared contexts), but rejected — its `read_sets` extra
  (`contextmap.py:1016-1019`) contains only each context's **direct** read
  set, not the dependency-expanded package (`expanded_read_set` is computed
  only by `resolve`/`explain` via `_build_expanded`, `contextmap.py:539`).
  The spec defines the context package as including the expanded set. Also,
  plan-check's failure modes are topology gates (exit 1 on
  missing-declaration/unknown-context/undeclared-owner) — the wrong semantics
  for a step that must never gate.

## R2 — The literal phase flag value is lowercase `implement`

**Decision**: the directive text uses `--phase implement` (lowercase).

**Rationale**: the CLI validates the flag against
`PHASES = ("specify", "plan", "tasks", "implement", "review")`
(`contextmap.py:41`) with **no case normalization**
(`contextmap.py:674`: `phase not in PHASES` → `S_USAGE_ERROR`, exit 2).
`--phase IMPLEMENT` (as the roadmap brief and spec write it, referring to the
ledger's IMPLEMENT phase) would be a usage error. The ledger phase name
(uppercase `IMPLEMENT`) and the context-map read-set key (lowercase
`implement`) are distinct vocabularies; the directive must use the latter.

## R3 — `status start-task` read-set surfacing: declined

**Decision**: `status start-task` output is **not** changed; the read set is
not surfaced anywhere new. The spec's FR-009/Assumption left this to the plan;
the plan declines it.

**Rationale**:

- The roadmap justifies 023-before-022 on **zero contract risk**. Touching
  `start-task` output — even additively under the 021 freeze — drags a frozen
  ledger-CLI surface into what is otherwise a pure template/docs change, adds
  a second source of truth for data `resolve` already provides through one
  read-only call, and would require frozen-surface tests for no new
  information.
- This also discharges the spec's assumption: the existing `context resolve`
  surface **is sufficient** (R1), so the roadmap's conditional ("no new CLI
  surface unless the plan proves `context resolve` insufficient") resolves to
  no new surface.

**Alternatives considered**: additive `read_set` field in `start-task --json`
— rejected per above; may be revisited by a future feature if real usage shows
the extra call is a friction point.

## R4 — Degradation semantics per map state (Rule 5)

**Decision**: the directive encodes three degradation behaviors, all consuming
**existing** exit contracts (no CLI change):

| Map state | `resolve` behavior today (verified) | Directive instruction |
|-----------|-------------------------------------|----------------------|
| No map | `S_NO_MAP` → `outcome.PASS`, exit 0, "context: no map present" (`contextmap.py:624-625`, `CLASS_FOR_STATUS` `contextmap.py:78`) | Step is a supported no-op — proceed exactly as today |
| Invalid map (malformed/schema-invalid/unsupported version) | `S_MALFORMED`/`S_SCHEMA_INVALID`/`S_UNSUPPORTED_VERSION` → `GATE_REJECTION`, exit 1 (`contextmap.py:89-91`) | Any non-zero exit of the resolution step → proceed **without** read-set scoping; never halt, never treat as a gate |
| Valid map, id/path matches nothing | `S_NO_MATCH` → PASS, exit 0 (`contextmap.py:82`) | No package for that selector — read normally for that scope |
| CLI absent | n/a | Already covered by the directive's existing Graceful Degradation section |

**Rationale**: FR-005/FR-006 (safe degradation) must hold **without** changing
the frozen exit-code classification of an invalid map (exit 1 is correct for
`validate`-style consumers and frozen under 021). The degradation therefore
lives in the directive: the step's outcome never blocks the session.

## R5 — Delivery vehicle: single-source directive text, both paths already wired

**Decision**: edit only `src/specops/templates/directives/implement.md`; no
wiring changes.

**Rationale** (verified): the native extension path builds hook prompts from
the directive files (`extension._build_hooks`, manifest skeleton
`templates/extensions.yml:32-38` shows `after_implement` sourcing
`directives/implement.md`), and the legacy path injects the same file
(`initializer.py:229` reads `directives/implement.md`,
`initializer.py:261` `inject_block(impl_path, "implement", …)`). Both paths
pick up the new section with zero code changes. The `workflow.yml` orchestration
(`templates/workflows/specops/workflow.yml`) invokes `speckit.implement` and
needs no change — the directive rides in via the hook.

## R6 — Out-of-set discoveries reuse Feature 010 acknowledgement verbatim

**Decision**: the new directive section cross-references the existing
"Discovered Paths (Feature 010)" section (`directives/implement.md:45-54`)
rather than restating the acknowledgement contract; one sentence connects the
concepts: a genuine read outside the resolved package that leads to a change
follows the same `specops trace acknowledge` flow, and an out-of-set **read**
alone requires no acknowledgement (acknowledgements exist for changed paths —
`trace acknowledge <path> --task … --reason …` feeds the drift gate, which
evaluates the effective diff, not reads).

**Rationale**: the spec (FR-004) requires routing discoveries through the
existing flow; duplicating the contract text in two sections of the same
directive invites drift. The read-set is guidance for *reading*; the trace
drift gate governs *changes* — the directive must not conflate them, and must
not invent a new "read acknowledgement" record (that would be a new surface,
out of scope).

## R7 — Test strategy: directive-content tests + fixture coverage tests

**Decision**: two test surfaces, following established patterns:

1. `tests/unit/test_implement_directive.py` (create) — mirrors
   `test_lite_directive.py`: native hook carries the new section
   (`extension._build_hooks()["after_implement"]` prompt contains the
   read-set instruction), legacy inject is idempotent, and the directive text
   encodes the required behaviors (resolve-at-session-start, lowercase
   `--phase implement`, union scoping, never-a-gate/non-zero→proceed,
   no-map no-op, discovery → existing acknowledgement flow).
2. `tests/unit/test_contextmap_consume.py` (extend) — acceptance-gate proof on
   the existing `context_map_repo` fixture: for every plan-declared path, the
   package resolved via `--path … --phase implement` is contained in the union
   of the declared contexts' id-resolved packages (coverage), plus the
   degradation rows of R4 asserted through `cmd_resolve` statuses (no-map PASS,
   invalid-map GATE_REJECTION — already partially covered; add the
   implement-phase read-set angle).

**Rationale**: the acceptance gate ("prescribed reads covered by the resolved
context package for each task; unmapped repo behaves exactly as today") is
fully checkable with deterministic fixtures — no self-application, no live
agent run needed (Dev Workflow gate 3).

## R8 — Documentation targets (EN/PT parity)

**Decision**: update `docs/commands.md` (the "map is consumed in the
lifecycle" list gains the implement-time consumption — currently it names
plan-check/impact/stale only, `docs/commands.md:299-310`), `README.md`
(context feature row/description, `README.md:109`), and `README.pt-br.md`
(equivalent line, `README.pt-br.md:114`) in the same PR — full parity per the
standing rule. `docs/stability.md` needs **no** change: no frozen surface is
touched.
