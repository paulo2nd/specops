
## SpecOps Specification Directives

### Graceful Degradation

- If the `specops` command is not available in this environment, skip the SpecOps
  steps in this block and write the specification normally.

### SpecOps Is Active

- This repository is managed with SpecOps. The execution ledger (`status.yaml`)
  is created later, during the tasks stage — do NOT run any ledger command now.

### Language Policy

- Author spec prose (`spec.md`) in any language. Keep structural tokens
  parseable: Success Criteria as `SC-\d+`, tasks as `T\d+`, and plan path
  declarations with action suffixes. SpecOps parses only these tokens, never
  prose.
