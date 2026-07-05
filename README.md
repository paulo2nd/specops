# SpecOps CLI

A CLI **SpecOps** (`specops`) é um orquestrador de processo projetado para estender o **Speckit** do GitHub com a metodologia de desenvolvimento guiado por agentes (*Spec-Driven Development* rigoroso).

Enquanto o Speckit define o escopo do negócio e o plano técnico, o `SpecOps` gerencia a esteira de execução física (controle de estados, commits atômicos do Git, silêncio operacional e auditoria de código focada em tokens).

## Instalação

Como pacote local em desenvolvimento:

```bash
pip install -e .
```

## Comandos Principais

* `specops init`: Inicializa a compatibilidade e injeta prompts/templates no projeto.
* `specops status start-task <task_id>`: Inicia a execução física de uma tarefa do plano.
* `specops status complete-task <task_id>`: Roda testes, colhe diffs/evidências e gera o commit atômico de encerramento da tarefa.
* `specops reconcile`: Valida a árvore do Git contra o ledger do `status.yaml`.
* `specops consistency`: Valida o pareamento entre o `specification.md` e o `plan.md` do Speckit.
