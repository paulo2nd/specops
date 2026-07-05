# Delivery Revision

## Revision

## Work Item Reference

- Type: `feature` ou `lightweight-fix`
- Path: `agents/features/<feature-name>/` ou `agents/fixes/<fix-name>/`

## PR Reference

## PR Decision Mirror

- Decision Comment URL: ``
- Decision Comment Summary: ``

Toda decisao formal, inclusive `APPROVED`, nasce primeiro neste artefato. Quando `Decision=APPROVED`, este bloco deve apontar para o comentario no PR que espelha a decisao versionada e referencia os artefatos aprovados. `Approve` nativo pode existir por conveniencia, mas nao substitui esse registro.

## Summary

## Non-Conformities

| # | Artefato afetado | Descricao | Severidade | Correcao esperada |
| :--- | :--- | :--- | :--- | :--- |

## Approved Items

- ``

Quando `Decision=APPROVED`, listar apenas os artefatos versionados realmente reconciliados antes da publicacao do comentario no PR.

## Corrective Handoff

| Field | Value |
| :--- | :--- |
| Return Target | `implementer` ou `fixer` |
| Scope Status | `approved_scope` ou `scope_expanded_by_revision` |
| Authorized Files | `` |
| Expected Evidence Updates | `` |
| Handoff Criteria | `` |

`Authorized Files` definem o escopo corretivo inicial. Se a implementacao precisar ampliar o scope dentro da mesma feature, a rastreabilidade dessa ampliacao deve aparecer nos artefatos citados em `Expected Evidence Updates`.

Quando `Decision=APPROVED`, esta secao deve permanecer `N/A` e nao autoriza retorno para `implementer` nem `fixer`.

Quando o item revisado for lightweight fix, `Authorized Files` podem apontar para `fix.md`, `status.yaml` do fix e os arquivos de produto estritamente necessarios. Se surgir qualquer novo gatilho de exclusao, o pacote corretivo deve exigir promocao para o workflow completo em vez de manter o fix no lane leve.

## Required Actions

- ``

## Correction Evidence (Self-Report)

| # | NC Ref | Evidence (Tests/Logs/Links) | Commit Hash |
| :--- | :--- | :--- | :--- |

Seção preenchida pelo `implementer` ou `fixer` durante a rodada corretiva para comprovar a resolução das Non-Conformities citadas acima.
