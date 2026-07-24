<!-- SpecOps: lightweight-lane recognition directive (Feature 013, Principle IV).
     Injected at the lifecycle entry (before_specify). Degrades to a no-op when SpecOps
     is not initialized. The human never drives the `specops` CLI — you (the agent) do. -->

## SpecOps — Lightweight Lane (proportional path for small reversible changes)

Before committing this request to the full `specify → plan → tasks → implement → review`
lifecycle, assess whether it is a **lightweight-lane candidate**: a small, reversible change
(typo/copy fix, a small non-contract-breaking refactor, a config default) that at first read
touches none of the safety-critical categories.

If it looks like a candidate, **propose the lightweight lane** and get the human's explicit
confirmation before entering it. Do **not** auto-classify or auto-enter — the eligibility
confirmation is the human's decision (Design Philosophy: record, do not silently decide).

On confirmation, **you drive the `specops-lite` workflow** — run every `specops lane *` command
yourself; never ask the human to run a `specops` command. The human's only interactions are the
native gates (eligibility, the two attestations, and any halt/promote choice). Concretely:

1. `specops lane start --answers small,reversible,no-high-risk-category` — open the lane.
2. Make the change as ordinary branch commits (the commit history is the working record).
3. `specops lane check` — the four diff-detectable safety categories. Do **not** judge these
   yourself; defer to the command.
4. Present the two always-on attestations and record them:
   `specops lane attest --root-cause {clear|flag} --public-contract {clear|flag}`.
5. If `check` flags a category **or** an attestation is flagged, present the native
   **halt-or-promote** gate. Never rationalize past it or record a bypass reason.
6. If the change outgrows "small/reversible" (scope or risk grew), propose **promotion**:
   `specops lane promote --reason scope-growth` — this is lossless (every commit preserved,
   context carried into the full workflow at PLAN).
7. Otherwise close: `specops lane close` — fail-closed gate suite + retrospective + evidence.

If SpecOps is not initialized (no `specops` command / no `specops.json`), ignore this section
entirely and proceed with the standard Speckit lifecycle.
