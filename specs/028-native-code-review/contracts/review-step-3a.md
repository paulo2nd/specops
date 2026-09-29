# Contract: rendered Step 3a native-review paragraph

**Feature 028** | `templates/review.md` gains one placeholder, `{{native_review}}`, which replaces
the current paragraph beginning "If your environment provides a native code-review
capability…". The rest of the template is unchanged. The one exception is Step 4, which
gains the `native-review-not-run` block (variants A and C only, so that block is part of
the placeholder text, not static template).

The texts below are normative in substance. Tests assert the marked phrases (**⟦…⟧**),
not the exact prose.

## Variant A — built-in entry (claude)

> **Native code review (mandatory).** This integration's native reviewer is
> ⟦`/code-review`⟧. Invoke it through ⟦the Skill tool⟧ before your own pass:
> `Skill(skill: "code-review", args: "⟦{effort}⟧ <from>...<head>")`. Here `<from>..<head>` is
> the `reviewed_range` printed by `specops handoff record-scope`, written with three dots.
> Always pass the level explicitly. Do **not** pass `ultra`, `--fix`, `--comment` or
> `--post`. Wait for its report before continuing.
>
> ⟦If you delegate this review to a subagent, that subagent must have the Skill tool.⟧
> A subagent without it cannot run the native reviewer. That run counts as ⟦native
> review not run⟧. Never substitute a manual pass silently.
>
> Carry every confirmed finding into Step 4 as a structured finding. Record defects
> that gate approval individually with `specops handoff finding add --severity
> blocking …`. JSON/SARIF output may be bulk-imported with `specops handoff finding
> import-json` / `import-sarif`, and imported findings are always advisory. The native
> reviewer complements your own pass below. It never replaces it, and it never records
> the verdict.
>
> If the native reviewer did not run, record that and continue with your own review.
> This covers: the Skill tool was unavailable, the invocation was refused or blocked,
> the tool errored, or you skipped it deliberately.
> ```
> specops handoff finding add --severity advisory --rule "⟦native-review-not-run⟧" \
>   --file . --action "Native review not run: /code-review (<reason>)"
> ```

## Variant C — `specops.json` override with a command string

Same structure as A, with these substitutions:

- The command is the configured string, followed by "(configured in `specops.json`)".
- The invocation sentence becomes: "Invoke it with your integration's own mechanism
  (tool, skill or shell), scoped to the round's `reviewed_range` from `specops handoff
  record-scope`."
- The subagent rule becomes: "…that subagent must be able to invoke it."
- There is no effort level and no flag list.

## Variant B — no native review

> **Native code review.** ⟦This integration (`{integration}`) has no native code-review
> command⟧ known to SpecOps. Perform the code review yourself, directly on the diff. A
> project can declare one in `specops.json` → `native_review`.

Variant B contains no `native-review-not-run` instruction (spec US2-AS2).

## Invariants (tested)

- No rendered variant contains `If your environment provides` or `e.g. the /code-review`.
- A copy mentions only its own integration's reviewer, or its absence (SC-002).
- The output contains no unfilled `{{…}}` (`fsutil.render_template` fails closed).
