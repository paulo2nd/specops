# SpecOps CLI

[![CI](https://github.com/paulo2nd/specops/actions/workflows/ci.yml/badge.svg)](https://github.com/paulo2nd/specops/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/speckit-specops.svg)](https://pypi.org/project/speckit-specops/)
[![Python](https://img.shields.io/pypi/pyversions/speckit-specops.svg)](https://pypi.org/project/speckit-specops/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Leia em: [English](README.md) | **Português (BR)**

**O SpecOps transforma o fluxo spec-driven do
[GitHub Spec Kit](https://github.com/github/spec-kit) em um processo imposto e
auditável.** Ele adiciona uma metodologia de *desenvolvimento atômico* guiada
por agentes sobre qualquer repositório Speckit — um ledger físico de estado,
evidências tipadas com coleta por máquina e revisão otimizada em tokens — **sem
substituir nem forkar um único arquivo do Speckit.**

> O Speckit dá aos seus agentes ótimos artefatos (spec → plan → tasks →
> implement). O SpecOps garante que eles realmente os sigam: o estado fica em
> disco e é verificável pelo Git, as evidências são coletadas por ferramentas em
> vez de alegadas pelo agente, e a revisão rejeita o mais cedo (e barato)
> possível.

## Por que SpecOps?

O desenvolvimento spec-driven com agentes de IA tem três modos de falha
recorrentes. O SpecOps trata cada um deles:

| Problema | Sem SpecOps | Com SpecOps |
|---|---|---|
| **Agentes alucinam progresso** | "Feito ✅" sem nenhuma prova | Toda tarefa fecha com evidência tipada; `--auto` anexa saída de testes, hashes de commit e diffs na fronteira do commit |
| **O estado vive no chat** | Perdido a cada reset de contexto; não auditável | O estado é um ledger físico `status.yaml`, verificável pelo Git e seguro para recuperação |
| **Reviews são lentos e caros** | O agente lê o repositório inteiro | O `/specops-review` rejeita do mais barato para o mais caro (reconcile → perfis de gate (lint/test por padrão) → working tree/diff efetivo → drift) antes de ler qualquer código |

## O que ele adiciona ao Speckit

- **📒 Ledger físico de estado (Repo-as-State).** Um `status.yaml` versionado e
  estruturado rastreia fase, tarefas, evidências e ciclos de review. Mutado
  apenas por comandos `specops` — nunca editado à mão, nunca mantido na memória
  do agente. As mudanças de estado são atômicas e seguras contra interrupção,
  protegidas por concorrência otimista (um `revision` monotônico) e por uma
  checagem de identidade do workspace (feature / branch / baseline); ledgers
  antigos migram sem perdas, com backup.
- **🔬 Coleta automatizada de evidências.** `complete-task --auto` executa seu
  comando de testes, colhe commits e diffs e os registra como evidência tipada.
  Uma tarefa não pode ficar `DONE` sem prova.
- **🔁 Uma máquina de estados de fases ligada aos prompts.** `specops init`
  injeta diretivas nos prompts de specify, plan, tasks e implement, de modo que
  o ledger é criado e as fases avançam automaticamente — o humano nunca faz a
  escrituração à mão.
- **✂️ Review cirúrgico otimizado em tokens.** O comando `/specops-review`
  instalado revisa apenas os arquivos do diff efetivo e para na primeira
  rejeição barata.
- **📐 Verificação empírica e gates.** `specops consistency` e
  `specops reconcile` são gates por código de saída que você pode plugar no CI
  ou nos prompts dos agentes.
- **➕ Aditivo e reversível.** Tudo é entregue em blocos delimitados por
  marcadores. Remover esses blocos restaura os arquivos afetados do Speckit
  byte a byte.

## Instalação

```bash
pip install speckit-specops
```

Instala o comando `specops`. Requer Python ≥ 3.10 e Git ≥ 2.30. Nenhum I/O de
rede após a instalação.

## Início rápido

```bash
# Em um repositório inicializado com Speckit:
specops init          # injeta as diretivas, instala /specops-review, cria specops.json
```

É só isso. A partir daqui você conduz o Speckit como sempre
(`/speckit.specify`, `/speckit.plan`, `/speckit.tasks`, `/speckit.implement`) e
as diretivas injetadas cuidam do ledger e das transições de fase. Consulte o
estado a qualquer momento:

```bash
specops status show
```

## Como funciona

O SpecOps acompanha o ciclo de vida do Speckit. Depois que `specops init`
rodou, as diretivas injetadas conduzem o ledger em cada costura de estágio:

| Estágio Speckit | O que o SpecOps faz |
|---|---|
| **specify** | Marca o repositório como gerenciado pelo SpecOps (informativo; ainda sem ledger) |
| **clarify / checklist / analyze** | Registra a decisão de rodar; um skip é derivado — nunca forçado — no estágio seguinte (`record-step`, com buffer antes de o ledger existir) |
| **plan** | Impõe a verificação empírica de caminhos e o gate `consistency` |
| **tasks** | Cria o ledger (`status init-spec`, drenando decisões em buffer), avança a fase para `TASKS` e exige tags de cobertura `[SC-xxx]` em toda tarefa |
| **implement** | Abre `IMPLEMENT`, resolve o read set mínimo do mapa de contexto e parte dele para as leituras (orientação, nunca um gate nem um teto para discovery; no-op sem mapa), executa o loop do ledger com evidências e então abre `REVIEW` |
| **converge** | Falha fechado *antes* de uma mutação irregistrável da lista de tarefas (`sync-tasks --check`), depois registra as tarefas anexadas com tags de cobertura (`sync-tasks`) |
| **taskstoissues** | Nada — verificado como somente leitura para o estado do ledger, protegido por teste de regressão |
| **review** | O `/specops-review` valida o diff e registra `APPROVED` / `REJECTED` |

A máquina de fases é `SPECIFY → PLAN → TASKS → IMPLEMENT → REVIEW → DONE`.
Se o SpecOps não estiver instalado, os prompts do Speckit continuam funcionando
sozinhos — as diretivas degradam para no-ops.

## Comandos em resumo

| Comando | O que faz |
|---|---|
| `specops init` | Prepara um repositório Speckit: injeta diretivas, instala o `/specops-review`, cria `specops.json` |
| `specops extension …` | Ciclo de vida nativo de extensões do Spec Kit, mais os workflows `specops` e `specops-lite` |
| `specops status …` | Conduz o ledger: `show`, `init-spec`, `start-task`, `complete-task`, `transition-phase`, `record-step`, `sync-tasks`, `migrate`, `rebaseline` |
| `specops preflight` | Gate determinístico de review, do mais barato para o mais caro — seguro para CI (antigo `specops review`) |
| `specops reconcile` | Gate somente leitura: todo commit registrado é alcançável, toda tarefa `DONE` tem evidência |
| `specops consistency` | Gate somente leitura: tags de cobertura SC + sufixos de ação nos caminhos do plano |
| `specops doctor` | Diagnóstico de saúde somente leitura sobre todas as superfícies do SpecOps |
| `specops report` | Superfície de máquina compacta e estável para o status da feature ativa |
| `specops context …` | Mapa de contexto: ownership, read sets por fase, impacto, staleness |
| `specops trace …` | Rastreabilidade ponta a ponta; classifica e reconhece drift do diff efetivo |
| `specops gate …` | Suíte de gate-profiles e inspeção de evidências estruturadas |
| `specops handoff …` | Handoffs corretivos estruturados; importa findings externos (JSON/SARIF) |
| `specops lane …` | Lane leve para mudanças pequenas e reversíveis |

A referência completa — flags, códigos de saída, contratos JSON, exemplos e o
fluxo de review — está em **[docs/commands.md](docs/commands.md)** (em inglês).

### Estabilidade e contract freeze

Construindo automação sobre o SpecOps? **[docs/stability.md](docs/stability.md)**
é o *contract freeze* para a 1.0: ele classifica cada superfície voltada ao
adotante — `specops.json`, `status.yaml`, `lane.yaml`, arquivos de gate-profile,
o envelope de saída `--json`, códigos de saída, o contrato de entrada de
findings, o arquivo de context-map e a saída SARIF — como **congelada**, e
enuncia a regra aditivo-vs-quebra e as obrigações de versionamento/migração
pós-1.0 de cada uma. Toda saída `--json` carrega um `output_version` para que
você detecte mudanças de envelope.

## Como o SpecOps se comporta: um caminho pavimentado que você pode deixar — mas fica registrado

O SpecOps não é nem um gate rígido que te bloqueia nem uma sugestão que você
pode ignorar. Ele apresenta um **caminho correto** e permite **desviar — desde
que o desvio seja registrado**. O que ele bloqueia é o desvio *silencioso*, não
o desvio em si:

- Um caminho que você mudou e o plano não previu não é rejeitado — você o
  **reconhece** com um motivo (`specops trace acknowledge`).
- Um finding de review que se revela falso positivo não é um beco sem saída —
  você o **descarta** com um motivo (`specops handoff finding dismiss`).
- Um gate que foi pulado é **registrado** como finding, nunca aprovado em
  silêncio.

O SpecOps **registra** o desvio e seu motivo; ele **não** julga se o motivo é
bom — essa decisão é do time, não da ferramenta. (Um pequeno núcleo de gates
críticos de segurança — mudanças em schemas persistidos, segredos, quebras de
contrato público, ações destrutivas — *não* é perfurável; ali o SpecOps para e
pergunta a um humano.)

## Configuração — `specops.json`

| Chave | Propósito | Padrão |
|---|---|---|
| `test_command` | Comando executado por `complete-task --auto` | `pytest` |
| `lint_command` | Gate de lint executado por `specops preflight` (vazio = pulado) | `""` |
| `skills_dir` | Diretório de onde o prompt de review carrega skills | `.specify/skills` |

Chaves desconhecidas são preservadas em um novo `init`.

## Política de idiomas

Toda a saída operacional do SpecOps (mensagens do CLI, assets injetados) é em
inglês. Sua prosa (`spec.md`, `plan.md`, descrições de tarefas) pode estar em
**qualquer idioma** — o SpecOps analisa apenas tokens estruturais (`SC-\d+`,
`T\d+`, sufixos de ação), nunca o conteúdo.

## Layouts Speckit suportados

O SpecOps resolve os alvos dos prompts em tempo de execução a partir de
`.specify/integrations/<agent>.manifest.json`. Qualquer integração Speckit com
manifest registrado é suportada; layouts desconhecidos falham de forma fechada.
Testado com Speckit ≥ 0.12 (modo de skills do Claude, separador `-`).

## Desinstalação

Remova o bloco anexado de cada arquivo de prompt e depois apague o
`specops.json` e o comando de review instalado. Nenhum outro arquivo é escrito;
a restauração é byte-idêntica.

## Contribuindo

Contribuições são bem-vindas — veja o [CONTRIBUTING.md](CONTRIBUTING.md) para o
setup de desenvolvimento, os gates de qualidade e os princípios do projeto. O
SpecOps está em `0.x`; a superfície do CLI e o formato do ledger ainda podem
mudar antes da `1.0` (veja o [CHANGELOG.md](CHANGELOG.md)).

## Licença

[MIT](LICENSE) © Paulo Segundo
