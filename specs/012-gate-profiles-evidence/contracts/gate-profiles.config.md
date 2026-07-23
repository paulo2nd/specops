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
    timeout: <int seconds>     # required, > 0
    required: <bool>           # optional, default true
    on_nonzero: block|advise   # optional, default block if required else advise
    artifact: <repo-rel path>  # optional; local file digested at run time
```

## Field rules

| Field | Required | Default | Validation defect (exit `1`, distinct diagnostic) |
|---|---|---|---|
| `output_version` | yes | — | unsupported version |
| `name` | yes | — | duplicate name |
| `command` | yes | — | empty/missing command |
| `applies` | no | `{always:true}` | unknown key / unparseable predicate |
| `applies.contexts[]`, `applies.gate_ref` | no | — | dangling context/gate reference (when a map exists) |
| `applies.paths[]` | no | — | malformed / unsafe (`..`, absolute) pattern — syntactic only |
| `timeout` | no | `600` (seconds) | non-positive or non-int |
| `required` | no | `true` | non-bool |
| `on_nonzero` | no | derived | value ∉ {block, advise} |
| `artifact` | no | — | unsafe path (`..`, absolute) |

## Selection semantics (deterministic — R9)

A gate is **selected** when any predicate branch matches the run's effective diff /
affected contexts; each declared gate carries a machine-readable `reason`
(`always | matched context <id> | matched gate-ref <id> | matched path <glob> |
matched risk key <k> | out-of-scope`). Selected required gates run in declared order;
first required `FAIL`/`unavailable` stops the run (fail-closed). No map / no baseline
⇒ only `always` + `paths` predicates can match; the `reason` records the degrade.

## Example — default profile (no file present)

Synthesized equivalent when `.specify/specops/gate-profiles.yaml` is absent, from
`specops.json` `{test_command: "pytest", lint_command: ""}`:

```yaml
profiles:
  - { name: test, command: "pytest", applies: {always: true}, timeout: 600, required: true }  # 600s = documented default
  # lint gate added only when lint_command is non-empty
```
</content>
