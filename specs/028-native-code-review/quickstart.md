# Quickstart: validating Feature 028

Run everything under `conda run -n specops`. Never run `specops` against this repository.
The automated scenarios use the existing `fake_speckit_repo` fixtures.

## 1. Automated suite

```bash
conda run -n specops pytest tests/unit/test_nativereview.py tests/unit/test_review.py \
  tests/integration/test_extension_lifecycle.py tests/integration/test_init.py -q
conda run -n specops pytest -q          # full suite: SC-005 (existing suites unchanged)
conda run -n specops ruff check src tests && conda run -n specops mypy src
```

Expected: all pass. `tests/unit/test_frozen_config.py` passes **unmodified**.

## 2. Scenarios the tests must cover

| # | Setup | Action | Expected | Spec |
|---|---|---|---|---|
| 1 | fixture with `claude` installed, no `native_review` | `extension install` | Claude review file contains `/code-review`, `the Skill tool`, `high`, `native-review-not-run`, and the subagent rule. It does not contain `If your environment provides` | US1, SC-001 |
| 2 | fixture with `claude` + `gemini` installed | `extension install` | Claude copy is variant A. Gemini copy is variant B and does not mention `/code-review` or `native-review-not-run` | US2, SC-002 |
| 3 | `native_review: {claude: {effort: max}}` | `extension update` | Claude copy passes `max` | US3-AS1 |
| 4 | `native_review: {claude: {command: null}}` / `{gemini: {command: "/code-review"}}` | `extension update` | Claude copy is variant B; Gemini copy is variant C | US3-AS2 |
| 5 | `native_review: {claude: {effort: ultra}}`, `{claude: {efort: high}}`, `native_review: []` | `extension install` and `specops init` | exit 1, error names the key, no file written or changed | US3-AS3, FR-010 |
| 6 | fixture installed with the old template | `extension update` | review files replaced with the rendered text; a second `update` is idempotent | FR-011, SC-004 |
| 7 | legacy path (`specops init`) with `claude` | `init` | same variant A text as the native path | Principle IV |

## 3. Manual check of the published text

Open a rendered Claude copy from scenario 1 and read Step 3a end to end. It should
read as one unconditional instruction, with no "if available" and no "e.g.".

## 4. One real-session check (before release, not in CI)

In a scratch Spec Kit project with Claude Code v2.1.246 or later, reach a review round and
confirm that `Skill(skill: "code-review", args: "high <sha>...<sha>")` is accepted with
raw commit shas (research R2 risk). If it is refused, switch the invocation to pass
`scope_paths` and update the contract before release.
