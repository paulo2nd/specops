# Contract: gate-profiles config schema (`.specify/specops/gate-profiles.yaml`)

Versioned, stack-neutral, ordered (FR-001). Sibling of the context map. Absent — or a
present file whose `profiles` list is empty — ⇒ default profile synthesized from
`specops.json` preserving the `lint`/`test` names (FR-005, R11) — a supported state,
never zero gates.

## Schema (`output_version: 1`)

```yaml
output_version: 1
profiles:                      # ordered list; declared order = execution order
  - name: <string>             # required, unique, stable
    command: <string>          # required, non-empty client shell string
    applies:                   # optional; omitted/empty ⇒ { always: true }
      always: <bool>           # optional
      contexts: [<ctx-id>...]  # optional; affected-context match (Feature 009)
      paths: [<glob>...]       # optional; changed-path match (syntactic validation)
      risk: { <key>: <value?> }# optional; named-key presence/equality on ctx.risk
      gate_ref: <string>       # optional; matches a ctx.gates entry (implicit ctx match)
    timeout: <int seconds>     # optional, > 0; default 600 for an AUTHORED gate
    required: <bool>           # optional, default true; the single failure-semantics knob
```

## Field rules

| Field | Required | Default | Validation defect (exit `1`, distinct diagnostic) |
|---|---|---|---|
| `output_version` | yes | — | unsupported version |
| `name` | yes | — | duplicate name |
| `command` | yes | — | empty/missing command |
| `applies` | no | `{always:true}` | non-mapping; unknown key; `contexts`/`paths` not a list; `risk` not a mapping; `always`/`gate_ref` wrong type |
| `applies.contexts[]` | no | — | dangling context reference (when a map exists) |
| `applies.paths[]` | no | — | malformed / unsafe (`..`, absolute) pattern — syntactic only |
| `timeout` | no | `600` (seconds) for an authored gate; **unbounded** for the synthesized default | non-positive or non-int |
| `required` | no | `true` | non-bool |

`required` alone determines failure semantics (a required gate's non-zero exit blocks;
an optional one never does); there is no separate `on_nonzero` knob. Artifact digesting
(`evidence.digest_artifact` / the `artifact_digest` evidence field) is part of the
deferred gate-evidence persistence (spec FR-009 / research R9a), so no `artifact` config
key is exposed in this feature.

## Selection semantics (deterministic — R9)

A gate is **selected** when any predicate branch matches the run's effective diff /
affected contexts; each declared gate carries a machine-readable `reason`
(`always | matched context <id> | matched gate-ref <id> | matched path <glob> |
matched risk key <k> | out-of-scope`). Selected required gates run in declared order;
first required `FAIL`/`unavailable` stops the run (fail-closed). No map / no baseline
⇒ only `always` + `paths` predicates can match; the `reason` records the degrade. A
config file that is **present but invalid** makes `specops review` **fail closed**
(`gateprofiles.resolve_suite` raises) — it never silently falls back to the default
suite, which would skip declared required gates and pass.

## Example — default profile (no file present)

Synthesized equivalent when `.specify/specops/gate-profiles.yaml` is absent, from
`specops.json` `{test_command: "pytest", lint_command: ""}`:

```yaml
profiles:
  - { name: lint, command: "",       applies: {always: true}, timeout: null, required: true }  # empty → SKIPPED
  - { name: test, command: "pytest", applies: {always: true}, timeout: null, required: true }  # null = unbounded (as pre-012)
```
</content>
