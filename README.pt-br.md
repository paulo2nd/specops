# SpecOps CLI

[![CI](https://github.com/paulo2nd/specops/actions/workflows/ci.yml/badge.svg)](https://github.com/paulo2nd/specops/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/speckit-specops.svg)](https://pypi.org/project/speckit-specops/)
[![Python](https://img.shields.io/pypi/pyversions/speckit-specops.svg)](https://pypi.org/project/speckit-specops/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Leia em: [English](README.md) | **Português (BR)**

**O SpecOps transforma o fluxo spec-driven do
[GitHub Speckit](https://github.com/vgrecov/speckit) em um processo imposto e
auditável.** Ele adiciona uma metodologia de *desenvolvimento atômico* guiada
por agentes sobre qualquer repositório Speckit — um ledger físico de estado,
evidências coletadas por máquina e revisão otimizada em tokens — **sem
substituir nem forkar um único arquivo do Speckit.**

> O Speckit dá aos seus agentes ótimos artefatos (spec → plan → tasks →
> implement). O SpecOps garante que eles realmente os sigam: o estado fica em
> disco e verificável pelo Git, as evidências são coletadas por ferramentas em
> vez de alegadas pelo agente, e a revisão rejeita o mais cedo (e barato)
> possível.

## Por que SpecOps?

O desenvolvimento spec-driven com agentes de IA tem três modos de falha
recorrentes. O SpecOps trata cada um:

| Problema | Sem SpecOps | Com SpecOps |
|---|---|---|
| **Agentes alucinam progresso** | "Pronto ✅" sem prova | Cada tarefa é fechada com evidência coletada por máquina (saída de teste, hashes de commit, diffs) registrada no ledger |
| **O estado vive no chat** | Perdido ao resetar o contexto; não auditável | O estado é um ledger físico `status.yaml`, verificável pelo Git e seguro para recuperação |
| **Revisões são lentas e caras** | O agente lê o repo inteiro | `/specops-review` rejeita do mais barato primeiro (reconcile → lint/test → arquivos fora do plano) antes de ler qualquer código |

## O que ele adiciona ao Speckit

- **📒 Ledger físico de estado (Repo-as-State).** Um `status.yaml` estruturado
  rastreia fase, tarefas, evidências e ciclos de revisão. Mutado apenas por
  comandos `specops` — nunca editado à mão, nunca mantido na memória do agente.
- **🔬 Coleta automática de evidências.** `complete-task --auto` roda o seu
  comando de teste, coleta commits e diffs e os registra como evidência tipada.
  Uma tarefa não pode ficar `DONE` sem prova.
- **🔁 Uma máquina de estados de fase conectada aos prompts.** `specops init`
  injeta diretivas nos prompts specify, plan, tasks e implement para que o
  ledger seja criado e as fases avancem automaticamente — o humano nunca faz a
  escrituração manual.
- **✂️ Revisão cirúrgica otimizada em tokens.** O comando `/specops-review`
  instalado revisa apenas os arquivos no escopo e para na primeira rejeição
  barata.
- **📐 Verificação empírica e gates.** `specops consistency` e
  `specops reconcile` são gates por código de saída que você pode plugar no CI
  ou em prompts de agente.
- **➕ Aditivo e reversível.** Tudo é entregue por blocos delimitados por
  marcadores. Desinstalar restaura os seus arquivos do Speckit byte a byte.

## Instalação

```bash
pip install speckit-specops
```

Instala o comando `specops`. Requer Python ≥ 3.10 e Git ≥ 2.30. Sem I/O de rede
após a instalação.

## Início rápido

```bash
# Em um repositório inicializado com Speckit:
specops init          # injeta diretivas, instala /specops-review, cria specops.json
```

É isso. Daqui em diante você conduz o Speckit normalmente (`/speckit.specify`,
`/speckit.plan`, `/speckit.tasks`, `/speckit.implement`) e as diretivas
injetadas cuidam do ledger e das transições de fase. Veja o estado a qualquer
momento:

```bash
specops status show
```

## Como funciona

O SpecOps acompanha o ciclo de vida do Speckit. Depois que `specops init` roda,
as diretivas injetadas conduzem o ledger em cada emenda de estágio:

| Estágio do Speckit | O que o SpecOps faz |
|---|---|
| **specify** | Marca o repo como gerenciado pelo SpecOps (informativo; ainda sem ledger) |
| **plan** | Impõe a verificação empírica de caminhos e o gate `consistency` |
| **tasks** | Cria o ledger (`status init-spec`), avança a fase para `TASKS` e exige tags de cobertura `[SC-xxx]` em cada tarefa |
| **implement** | Abre `IMPLEMENT`, roda o loop de ledger com evidências, depois abre `REVIEW` |
| **review** | `/specops-review` valida o diff e registra `APPROVED` / `REJECTED` |

A máquina de fases é `SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE`. Se o
SpecOps não estiver instalado, os prompts do Speckit continuam funcionando
sozinhos — as diretivas degradam para no-ops.

## Referência de comandos

### `specops init [--non-interactive]`

Prepara um repositório Speckit em uma execução: valida (ou oferece criar) um
repo Git, detecta o Speckit, resolve os alvos de prompt a partir dos manifests
de integração do Speckit (funciona com qualquer layout de agente registrado —
Claude skills, GitHub Copilot, etc.), cria/preserva-mesclando o `specops.json`,
instala o `/specops-review` e injeta os blocos de diretiva nos prompts specify,
plan, tasks e implement (aditivo, idempotente, restauração byte-idêntica na
remoção). `--non-interactive` recusa todos os prompts (seguro para CI).

> **Nota sobre upgrade do Speckit**: um upgrade do Speckit pode reescrever os
> arquivos de prompt e remover os blocos injetados. Basta rodar `specops init`
> de novo para reinjetar.

### `specops status show`

Somente leitura. Imprime o estado do ledger: feature, branch, fase, tarefa
ativa, contagens de tarefas (pending / in progress / done / orphaned) e o
histórico de ciclos de revisão.

### `specops status init-spec [<name>]`

Cria `<feature_dir>/status.yaml` a partir do scaffold empacotado, sincronizando
os IDs de tarefa do `tasks.md`. Normalmente rodado para você pela diretiva de
tasks.

### `specops status start-task <task-id>`

Marca a tarefa como `IN_PROGRESS` e registra `started_commit = HEAD`. Impõe a
regra de tarefa-ativa-única.

### `specops status complete-task <task-id> [--auto | --evidence "CLASS:summary"]`

Marca a tarefa como `DONE` com exatamente uma fonte de evidência:

- `--auto`: roda `test_command`; em caso de sucesso, coleta os commits de
  `started_commit..HEAD` + diff como evidência `TEST_REPORT`/`CODE_DIFF`.
- `--evidence "CLASS:summary"`: fornecida por quem chama, com `CLASS` em
  `CLI_LOG | TEST_REPORT | SCREENSHOT_PATH | CODE_DIFF`.

### `specops status transition-phase <phase> [-r APPROVED|REJECTED]`

Avança a fase um passo à frente. Duas transições exigem `-r`:

```bash
specops status transition-phase DONE -r APPROVED      # aprovado → fecha a feature
specops status transition-phase IMPLEMENT -r REJECTED # rejeitado → volta para retrabalho
```

Entrar em `DONE` exige que o último ciclo de revisão seja `APPROVED`.

### `specops reconcile`

Gate somente leitura. Verifica que todo hash de commit do ledger é alcançável a
partir de `HEAD` e que toda tarefa `DONE` tem commits e evidências. Sai com 1 em
qualquer divergência.

```bash
specops reconcile || exit 1   # preflight antes da revisão
```

### `specops review`

Gate somente leitura. Executa os gates determinísticos de revisão do-mais-barato-
primeiro com parada antecipada: **reconcile → lint → test → working
tree/diff efetivo**. O primeiro gate que falha interrompe a execução e imprime
sua evidência no stderr (saída 1); passando tudo, imprime um relatório por gate
no stdout (saída 0) que lista os arquivos do diff efetivo — exatamente o escopo
que o agente de revisão lê em seguida. Erros de parse do ledger mantêm a saída 2.
Roda de qualquer diretório dentro do repo, nunca escreve no ledger nem em
qualquer arquivo do repositório, não exige fase específica e nunca pergunta
nada — seguro como step de CI.

```bash
specops review                # local: valida os gates da mudança atual
```

Como gate de CI:

```yaml
# .github/workflows/ci.yml (step)
- run: pip install speckit-specops
- run: specops review
```

Como gate automatizado dentro de um workflow do Speckit (substitui um gate
humano de approve/reject; o YAML é seu, sem acoplamento ao SpecOps):

```yaml
- id: review
  type: shell
  run: specops review
  on_fail: abort
```

### `specops consistency`

Gate somente leitura. Verifica que todo `SC-\d+` na spec tem ≥ 1 tarefa com uma
tag `[SC-xxx]` correspondente, e que toda declaração de caminho em `plan.md`
carrega um sufixo de ação válido (`(create)`/`(modify)`/`(remove)`). Sai com 1
em caso de violação.

### `specops --version`

Imprime a versão e sai. Funciona em qualquer lugar.

## Configuração — `specops.json`

| Chave | Propósito | Padrão |
|---|---|---|
| `test_command` | Comando rodado por `complete-task --auto` | `pytest` |
| `lint_command` | Gate de lint executado por `specops review` (vazio = pulado) | `""` |
| `skills_dir` | Diretório de onde o prompt de revisão carrega skills | `.specify/skills` |

Chaves desconhecidas são preservadas na reinicialização.

## O comando `/specops-review`

Instalado por `specops init` (o nome segue o separador do layout, ex.:
`/specops-review` para Claude skills). Não é um comando de CLI — um prompt
empacotado que conduz o agente de revisão do-mais-barato-primeiro:

1. Carrega skills de `skills_dir`.
2. `specops review` — a CLI executa todos os gates determinísticos (reconcile,
   lint, test, working tree); qualquer saída diferente de zero é um REJECTED
   imediato sem ler uma única linha de código.
3. Revisão cirúrgica do diff apenas dos arquivos no escopo.
4. Escreve `revisions/revision-X.md` e registra o resultado `APPROVED`/`REJECTED`.

## Política de idioma

Toda saída operacional do SpecOps (mensagens de CLI, assets injetados) é em
inglês. A sua prosa (`spec.md`, `plan.md`, descrições de tarefas) pode estar em
**qualquer idioma** — o SpecOps analisa apenas tokens estruturais (`SC-\d+`,
`T\d+`, sufixos de ação), nunca o conteúdo.

## Layouts de Speckit suportados

O SpecOps resolve os alvos de prompt em tempo de execução a partir de
`.specify/integrations/<agent>.manifest.json`. Qualquer integração Speckit com
um manifest registrado é suportada; layouts desconhecidos falham fechado (fail
closed). Testado com Speckit ≥ 0.12 (modo Claude skills, separador `-`).

## Desinstalação

Remova o bloco anexado de cada arquivo de prompt, depois apague o `specops.json`
e o comando de revisão instalado. Nenhum outro arquivo é escrito; a restauração
é byte-idêntica.

## Contribuindo

Contribuições são bem-vindas — veja o [CONTRIBUTING.md](CONTRIBUTING.md) para
setup de desenvolvimento, os quality gates e os princípios do projeto. O SpecOps
está em `0.x`; a superfície da CLI e o formato do ledger ainda podem mudar antes
do `1.0` (veja o [CHANGELOG.md](CHANGELOG.md)).

## Licença

[MIT](LICENSE) © Paulo Segundo
