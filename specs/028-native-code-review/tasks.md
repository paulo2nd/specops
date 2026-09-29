---
description: "Task list for Feature 028 — Native Code Review in /specops-review"
---

# Tasks: Native Code Review in `/specops-review`

**Input**: Design documents from `/specs/028-native-code-review/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/native-review-config.md](./contracts/native-review-config.md), [contracts/review-step-3a.md](./contracts/review-step-3a.md), [quickstart.md](./quickstart.md)

**Tests**: Mandatory. Constitution *Development Workflow & Quality Gates* §2 says no task is complete without tests. Every scenario runs against the `fake_speckit_repo` fixture (`tests/conftest.py`). This repository is never self-applied (§3).

**Organization**: Grouped by user story. Phase 2 holds the placeholder and the single render function wired into both install paths, because every story renders through it. US2 and US3 each add a variant or a resolution rule on top. They depend on Phase 2 and not on each other.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: US1 / US2 / US3, mapping to the user stories in spec.md
- `[SC-00N]` tags record success-criteria coverage

## Path Conventions

Single Python package: `src/specops/`, `tests/unit/`, `tests/integration/` at the repository root. All tooling runs under `conda run -n specops …`.

---

## Phase 1: Setup

**Purpose**: Establish a known-green baseline.

- [X] T001 Confirm the baseline suite is green by running `conda run -n specops pytest -q`, `conda run -n specops mypy src` and `conda run -n specops ruff check src tests`, and record the pass counts in the task evidence

**Checkpoint**: baseline recorded.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: One render function, used by both install paths, with the placeholder in the template. After this phase the output is still today's behavior: the placeholder renders to the current paragraph. Each story then changes what it renders to.

- [X] T002 Create `src/specops/nativereview.py` with `render_review(root: Path, integration: str) -> str`. It reads `templates/review.md` and fills it through `fsutil.render_template(text, {"native_review": step_3a(root, integration)})`. For now, `step_3a` returns the existing native paragraph verbatim. Add a module docstring stating its purpose: the per-integration native-review map, `native_review` config resolution, and the Step 3a render (Feature 028).
- [X] T003 In `src/specops/templates/review.md`, replace the Step 3a paragraph that begins "If your environment provides a native code-review capability" with a line holding only `{{native_review}}`. Leave the rest of the template byte-identical.
- [X] T004 [P] In `src/specops/initializer.py` `run_init`, replace `review_content = _read_template("review.md")` and the per-target `install_review(review_path, review_content, sep)` with `install_review(review_path, nativereview.render_review(root, target["integration"]), sep)`. Before step 4 (`config.create_or_merge`), render every target once into a dict keyed by integration. An invalid `native_review` then raises before `specops.json` or any prompt file is written, and step 5 installs from that dict.
- [X] T005 [P] In `src/specops/extension.py` `register_commands`, render every target first into a list of `(target, content)` via `nativereview.render_review(root, target["integration"])`, and only then loop over `initializer.install_review(...)`. A render error must leave no file written (plan Constraints).
- [X] T006 Run `tests/unit/test_review.py` and `tests/unit/test_refusal_exit_contract.py`. They read the raw `review.md`, but their phrases lie outside Step 3a: no test references the replaced paragraph (checked 2026-09-29), so they must pass unchanged.
- [X] T007 Add `tests/unit/test_nativereview.py` with (a) the rendered output contains no `{{`, and (b) the text written by `specops init` equals the text written by `extension.install` for the same fixture (Principle IV parity).

**Checkpoint**: full suite green. The installed text is unchanged apart from placeholder plumbing.

---

## Phase 3: User Story 1 — The review command names and requires the native reviewer (Priority: P1) 🎯 MVP

**Goal**: The Claude Code copy's Step 3a is contract variant A: `/code-review` through the Skill tool, explicit effort, `reviewed_range` target, the forbidden flags, the subagent rule, the findings path, and the `native-review-not-run` fallback.

**Independent Test**: `extension.install` on `fake_speckit_repo` (claude installed). Then read the Claude review file and assert the variant A phrases, and assert that none of the old conditional wording remains.

### Tests for User Story 1

- [X] T008 [P] [US1] In `tests/unit/test_nativereview.py`, test that `render_review(root, "claude")` contains `/code-review`, `the Skill tool`, `Skill(skill: "code-review", args: "high `, `reviewed_range`, `ultra`, `--fix`, `If you delegate this review to a subagent, that subagent must have the Skill tool`, `native review not run`, `--rule "native-review-not-run"`, `specops handoff finding add --severity blocking` and `import-json`. It must NOT contain `If your environment provides` or `e.g. the /code-review`. Also assert that the built-in map keys are exactly `{"claude"}`, so any new entry forces a test update and a citation in research.md R1 [SC-001, SC-003]
- [X] T009 [P] [US1] In `tests/integration/test_extension_lifecycle.py`, test that after `extension.install(root)` the installed Claude review file (path from `speckit.review_command_targets`) contains `/code-review` and `the Skill tool`, and that a second `extension.update(root)` leaves it byte-identical (FR-011 idempotency) [SC-001, SC-004]
- [X] T010 [US1] In `tests/integration/test_extension_lifecycle.py`, test that a review file pre-seeded with the old template text (the "If your environment provides…" paragraph) is replaced by `extension.update(root)` [SC-004]

### Implementation for User Story 1

- [X] T011 [US1] In `src/specops/nativereview.py`, add the built-in map as one dict entry for `claude`, with the data-model Entity 1 fields: `command="/code-review"`, `mechanism="the Skill tool"`, `invocation='Skill(skill: "code-review", args: "{effort} <from>...<head>")'`, `efforts=("low","medium","high","xhigh","max")`, `default_effort="high"`. Make `step_3a` render variant A from `contracts/review-step-3a.md` for a mapped integration, including the `native-review-not-run` `finding add` block.

**Checkpoint**: US1 is independently shippable. Claude projects get the unconditional instruction. Other integrations still render the old paragraph until US2. Commit.

---

## Phase 4: User Story 2 — Integrations without a native reviewer get an honest instruction (Priority: P2)

**Goal**: Unmapped integrations render contract variant B. Every copy mentions only its own reviewer, or its absence.

**Independent Test**: A two-integration fixture (claude + gemini, built the same way as the existing test at `tests/integration/test_extension_lifecycle.py` ~L150). Claude's copy is variant A and Gemini's is variant B.

### Tests for User Story 2

- [ ] T012 [P] [US2] In `tests/unit/test_nativereview.py`, test that `render_review(root, "gemini")` and `render_review(root, "some-future-id")` contain `has no native code-review command` and the integration id, and contain none of `/code-review`, `native-review-not-run`, `Skill tool` or `If your environment provides` [SC-002]
- [ ] T013 [P] [US2] In `tests/integration/test_extension_lifecycle.py`, test that on a claude + gemini install `.gemini/commands/specops-review.md` is variant B, the Claude copy is variant A, and neither mentions the other's reviewer [SC-002]

### Implementation for User Story 2

- [ ] T014 [US2] In `src/specops/nativereview.py`, make `step_3a` return variant B (`contracts/review-step-3a.md`) for any integration absent from the map. Remove the verbatim old paragraph from the module, so no integration renders it any more.

**Checkpoint**: every integration renders A or B. Commit.

---

## Phase 5: User Story 3 — Projects can override the map (Priority: P3)

**Goal**: The optional `specops.json` → `native_review` block (contract `native-review-config.md`) sets the effort, overrides the command, or declares none. Invalid config fails closed with exit 1 (the existing `ConfigError` code) and writes nothing, on both install paths.

**Independent Test**: Write `specops.json` variants into the fixture, run `extension.update`, and assert the rendered text. For invalid variants, assert `ConfigError`/exit 1 and an unchanged tree via `snapshot_tree`.

### Tests for User Story 3

- [ ] T015 [P] [US3] In `tests/unit/test_nativereview.py`, table-test the resolution rules from data-model Entity 2: absent → claude `high`; `{claude:{effort:"max"}}` → args `"max `; `{claude:{command:null}}` → variant B; `{gemini:{command:"/code-review"}}` → variant C containing `/code-review (configured in \`specops.json\`)` and `your integration's own mechanism`, with no effort; keys for uninstalled integrations are ignored; no `specops.json` file → defaults
- [ ] T016 [US3] In `tests/unit/test_nativereview.py`, test that each of these raises `config.ConfigError` naming the key: `native_review: []`; `{claude: "x"}`; `{claude:{efort:"high"}}`; `{claude:{command:""}}`; `{claude:{command:3}}`; `{claude:{effort:"ultra"}}`; `{claude:{effort:"turbo"}}`; `{gemini:{effort:"high"}}` (effort on no-native); `{claude:{command:"/x", effort:"high"}}` (effort on override)
- [ ] T017 [P] [US3] In `tests/integration/test_extension_lifecycle.py`, test that with `{"native_review": {"claude": {"effort": "ultra"}}}` in `specops.json`, both `specops extension install` and `specops init` exit 1 when run through the CLI (via `conftest.cli`), and `snapshot_tree` is identical before and after each [US3-AS3, FR-010]
- [ ] T018 [US3] In `tests/unit/test_nativereview.py`, assert (leaving `tests/unit/test_frozen_config.py` unedited) that `"native_review" not in config._DEFAULTS`, and that `config.create_or_merge` on a fresh fixture does not write the key (freeze, research R4)

### Implementation for User Story 3

- [ ] T019 [US3] In `src/specops/nativereview.py`, add `_resolve(root, integration)`. It reads `specops.json` with `config.load(root)` only when `config.config_path(root).is_file()`, validates `native_review` per data-model Entity 2, raises `config.ConfigError` with the offending key, and returns one of: a built-in entry plus effort, an override command string, or none. `step_3a` renders variant A, C or B from it.

**Checkpoint**: all stories are functional. Commit.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T020 [P] Add a `native_review` row to the `specops.json` configuration table in `README.md` (~L171). It is optional, per integration, `{command, effort}`, and takes effect on `specops extension update`. Add a sentence in the review section that `/specops-review` now invokes the agent's native reviewer where one exists (Claude Code: `/code-review`).
- [ ] T021 [P] Mirror T020 in `README.pt-br.md` (full parity rule)
- [ ] T022 [P] In `docs/commands.md`, document in the review section the per-integration native reviewer, the `native_review` block, and the `native-review-not-run` advisory convention
- [ ] T023 [P] In `CHANGELOG.md` under `[Unreleased]`, add an entry that covers: `/specops-review` names the integration's native reviewer and makes it mandatory (Claude Code: `/code-review` via the Skill tool, effort `high`); the subagent rule; the `native-review-not-run` advisory finding convention; the new optional `native_review` block in `specops.json`; installed projects receive it with `specops extension update`. Also state that the ledger, commands and gates are unchanged.
- [ ] T024 [P] In `ROADMAP.md`, add Feature 028 "Native Code Review in /specops-review" as `ACTIVE` to the tracking table (depends on 005, 011, 015), plus a short brief section after Feature 027
- [ ] T025 Run the full quickstart §1: `conda run -n specops pytest -q`, `mypy src`, `ruff check src tests`. Confirm that `tests/unit/test_frozen_config.py` passes unmodified [SC-005]
- [ ] T026 Before release, not in CI: do quickstart §4 in a real Claude Code session (v2.1.246 or later) to confirm `Skill(skill: "code-review", args: "high <sha>...<sha>")` accepts raw commit shas. If it is refused, switch the variant A invocation to pass `scope_paths`, and update `contracts/review-step-3a.md` and T008.

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2**: baseline first.
- **Phase 2 blocks all stories**: T002 → T003 → (T004 ∥ T005) → T006 → T007.
- **US1 (Phase 3)**: depends on Phase 2 only. It is the MVP.
- **US2 (Phase 4)**: depends on Phase 2. It touches `step_3a` in the same file as US1, so run it after US1 to avoid edit conflicts, although the behavior is independent.
- **US3 (Phase 5)**: depends on US1 (variant A must exist for effort overrides) and on US2 (variant B must exist for `command: null`).
- **Polish**: T020–T024 in parallel after US3. T025 after all. T026 before release.

### Parallel Opportunities

- Phase 2: T004 and T005 (different files).
- US1: T008 ∥ T009 (different files). T010 follows T009 (same file).
- US2: T012 and T013.
- US3: T015 ∥ T017 (different files). T016 and T018 share T015's file.
- Polish: T020–T024 (all different files).

### Parallel Example: User Story 3

```text
Task: "T015 resolution table test in tests/unit/test_nativereview.py"
Task: "T017 CLI exit-1 + snapshot_tree test in tests/integration/test_extension_lifecycle.py"
```
(T015, T016 and T018 share one file. Write them together, or serialize them.)

## Implementation Strategy

1. **MVP = Phase 1 + 2 + US1**. This fixes the field failure (the silent fallback on Claude Code) on its own, so it can ship first if needed.
2. **US2** removes the last trace of the conditional example for every other integration.
3. **US3** adds overrides and validation.
4. Commit once per user story (memory: commit granularity per user story). Phase 2 goes with US1's commit or in its own commit.
