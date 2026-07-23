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
> disco e verificável pelo Git, as evidências são coletadas por ferramentas em
> vez de alegadas pelo agente, e a revisão rejeita o mais cedo (e barato)
> possível.

## Por que SpecOps?

O desenvolvimento spec-driven com agentes de IA tem três modos de falha
recorrentes. O SpecOps trata cada um:

| Problema | Sem SpecOps | Com SpecOps |
|---|---|---|
| **Agentes alucinam progresso** | "Pronto ✅" sem prova | Cada tarefa fecha com evidência tipada; `--auto` anexa saída de teste, hashes de commit e diffs na fronteira de commit |
| **O estado vive no chat** | Perdido ao resetar o contexto; não auditável | O estado é um ledger físico `status.yaml`, verificável pelo Git e seguro para recuperação |
| **Revisões são lentas e caras** | O agente lê o repo inteiro | `/specops-review` rejeita do mais barato primeiro (reconcile → lint/test → working tree/diff efetivo) antes de ler qualquer código |

## O que ele adiciona ao Speckit

- **📒 Ledger físico de estado (Repo-as-State).** Um `status.yaml` estruturado
  e versionado rastreia fase, tarefas, evidências e ciclos de revisão. Mutado
  apenas por comandos `specops` — nunca editado à mão, nunca mantido na memória
  do agente. As mudanças de estado são atômicas e seguras a interrupções,
  protegidas por concorrência otimista (um `revision` monotônico) e uma
  verificação de identidade do workspace (feature / branch / baseline); ledgers
  antigos migram sem perdas e com backup.
- **🔬 Coleta automática de evidências.** `complete-task --auto` roda o seu
  comando de teste, coleta commits e diffs e os registra como evidência tipada.
  Uma tarefa não pode ficar `DONE` sem prova.
- **🔁 Uma máquina de estados de fase conectada aos prompts.** `specops init`
  injeta diretivas nos prompts specify, plan, tasks e implement para que o
  ledger seja criado e as fases avancem automaticamente — o humano nunca faz a
  escrituração manual.
- **✂️ Revisão cirúrgica otimizada em tokens.** O comando `/specops-review`
  instalado revisa apenas os arquivos do diff efetivo e para na primeira rejeição
  barata.
- **📐 Verificação empírica e gates.** `specops consistency` e
  `specops reconcile` são gates por código de saída que você pode plugar no CI
  ou em prompts de agente.
- **➕ Aditivo e reversível.** Tudo é entregue por blocos delimitados por
  marcadores. Remover esses blocos restaura os arquivos afetados do Speckit
  byte a byte.

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

### `specops extension install | update | disable | enable | remove [--purge] | migrate | status`

Registra o SpecOps através do **mecanismo nativo de extensão** do Spec Kit — um
manifest de hooks `.specify/extensions.yml` de propriedade do SpecOps mais o
registro de comando por integração — em vez de injetar blocos de marcadores em
arquivos de prompt de propriedade do host. O CLI Python permanece o motor
determinístico; os hooks o invocam.

- `install` — registra os hooks de ciclo de vida + o comando `/specops-review`
  em cada integração instalada. **Não** modifica nenhum arquivo do host, é
  idempotente, funciona offline e falha de forma fechada (deixando o repo
  inalterado) quando o CLI está ausente/incompatível ou o diretório não é um
  repositório Spec Kit.
- `update` — reaplica os templates de diretiva atuais (idempotente).
- `disable` / `enable` — cancela o registro na superfície do host (preservando
  configuração e ledgers) / registra novamente a partir da configuração retida.
- `remove [--purge]` — cancela o registro sem modificar nenhum arquivo do host;
  `--purge` também apaga o `specops.json` e os ledgers de feature.
- `migrate` — converte uma instalação legada por injeção de marcadores para a
  nativa, removendo os blocos de marcadores do SpecOps (com um backup automático
  pré-edição que restaura em caso de falha) e preservando a configuração e todos
  os ledgers de feature.
- `status` — somente leitura; reporta o estado detectado
  (`absent | native | legacy | native+legacy`) e a compatibilidade do CLI.

O caminho legado `specops init` acima permanece totalmente suportado. Requer o
CLI `specops` `>= 0.3.0` (a primeira versão que entende o schema do manifest
nativo).

O `install` também registra aditivamente o **workflow `specops`** (abaixo),
deixando o workflow `speckit` embutido do Spec Kit intocado.

### O workflow `specops`

O `specops extension install` registra um workflow instalável, de propriedade do
SpecOps, que compõe **o próprio engine de workflow nativo do Spec Kit** para rodar
o ciclo aumentado — o SpecOps não constrói engine, resume, gate nem loop. Execute
com:

```bash
specify workflow run specops
```

Ele conduz specify → clarify/checklist (gates de skip humanos, registrados no
ledger) → plan → **gate humano de prontidão do planejamento** (nenhuma task antes
da aprovação) → tasks → analyze → um **loop corretivo `do-while`** limitado
(implement → review, repetindo enquanto o veredito determinístico for `REJECTED`)
→ um **gate terminal de review** que falha fechado a menos que o veredito seja
`APPROVED`. As transições de fase forward permanecem de propriedade dos directives
injetados; o workflow nunca as duplica, e uma precondição `specops reconcile`
fail-closed mantém o ledger como autoridade.

### `specops status show`

Somente leitura. Imprime o estado do ledger: feature, branch, fase, tarefa
ativa, contagens de tarefas (pending / in progress / done / orphaned) e o
histórico de ciclos de revisão. Nunca modifica; em um ledger legado, futuro
demais, não suportado ou malformado ainda imprime um resumo de melhor esforço
mais um diagnóstico de uma linha.

### `specops status init-spec [<name>]`

Cria `<feature_dir>/status.yaml` a partir do scaffold empacotado, sincronizando
os IDs de tarefa do `tasks.md`. Normalmente rodado para você pela diretiva de
tasks.

### `specops status migrate`

Atualiza o ledger da feature ativa para o schema atual. Idempotente
(`already current` quando não há nada a fazer). Um ledger legado é migrado sem
perdas — fases, tarefas, evidências e ciclos de revisão são preservados e o
original é copiado para `.specify/.specops-backup/` antes. Um schema futuro
demais ou não suportado é recusado, deixando o ledger intacto. As mudanças de
estado também migram automaticamente na primeira escrita, então rodar isto é
opcional.

### `specops status rebaseline`

Re-ancora o **branch** e o **baseline** registrados no ledger ao workspace
atual — a válvula de escape explícita para quando o gate de identidade recusa
uma mudança de estado após um rename de branch ou reescrita de histórico
deliberados. Nunca altera a identidade da **feature** (se a feature resolvida
deixar de coincidir, falha fechado) e é uma mudança de estado normal (avança o
revision).

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

Gate somente leitura. Verifica que todo commit registrado no ledger é alcançável
a partir de `HEAD` e que toda tarefa `DONE` tem evidência. Tarefas intermediárias
podem intencionalmente não ter commit quando a granularidade é por user story.
Sai com 1 em qualquer divergência.

```bash
specops reconcile || exit 1   # preflight antes da revisão
```

### `specops review`

Gate somente leitura. Executa os gates determinísticos de revisão do-mais-barato-
primeiro com parada antecipada: **reconcile → lint → test → working
tree/diff efetivo → drift**. O primeiro gate que falha interrompe a execução e imprime
sua evidência no stderr (saída 1); passando tudo, imprime um relatório por gate
no stdout (saída 0) que lista os arquivos do diff efetivo — exatamente o escopo
que o agente de revisão lê em seguida. Erros de parse do ledger mantêm a saída 2.
Roda de qualquer diretório dentro do repo, nunca escreve no ledger nem em
qualquer arquivo do repositório, não exige fase específica e nunca pergunta
nada — seguro como step de CI.

O **gate de drift** terminal (Feature 010) rejeita a revisão quando qualquer
caminho do diff efetivo é `unexplained` — nem declarado no `plan.md` nem
registrado via `specops trace acknowledge`. Caminhos `planned` e
`discovered-and-acknowledged` passam, e os artefatos gerenciados pelo
SpecOps/Speckit (`specs/**`, `.specify/**`, `specops.json`) são excluídos por
serem estado da metodologia. Veja `specops trace` abaixo.

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

### `specops context init | validate | resolve | explain`

O **mapa de contexto** (`.specify/specops/context-map.yaml`) é uma descrição
versionada e agnóstica de stack dos contextos do repositório — quais caminhos
cada área governa, os arquivos que um agente deve ler por fase do ciclo de vida,
dependências entre contextos, gates e risco. É interpretado deterministicamente:
o mesmo mapa e as mesmas entradas sempre produzem o mesmo resultado ordenado.

- `specops context init` — cria um mapa inicial (idempotente; nunca sobrescreve).
- `specops context validate` — valida o mapa; reporta todos os defeitos numa
  única passagem (padrão inválido/inseguro, id duplicado, posse ambígua,
  dependência pendente, ciclo de dependência, versão não suportada). Sai com 1
  em caso de defeito.
- `specops context resolve --path <p> | --id <id> [--phase <phase>]` — retorna o
  contexto governante e seu conjunto de leitura ordenado e específico da fase,
  com um conjunto expandido (sem ciclos, deduplicado) vindo das dependências.
- `specops context explain --path <p> | --id <id> [--phase <phase>]` — o rastro
  de razões ordenado: candidatos considerados, o vencedor e qual dimensão de
  especificidade decidiu.

O mapa é **consumido** no ciclo de vida por mais três comandos somente-leitura:

- `specops context plan-check [--plan <p>] [--phase <phase>]` — valida a topologia
  de contextos declarada no plano (uma linha `**SpecOps-Contexts**: …`) contra o
  mapa e exibe o conjunto de leitura mínimo da fase. Bloqueia (saída `1`) quando a
  declaração falta, um contexto declarado é desconhecido, ou um caminho declarado
  é de um contexto não declarado; um caminho sem dono é não-bloqueante. Não
  consulta o sistema de arquivos.
- `specops context impact [--path <p> …]` — os contextos afetados por uma mudança:
  o contexto dono mais seus **dependentes reversos** transitivos, cada um
  atribuído a uma aresta `ownership`/`dependency`/`policy`. Sem `--path`, o
  conjunto de mudanças vem do Git (árvore limpa → vazio, saída `0`; fora de repo /
  sem baseline → saída `2`).
- `specops context stale` — padrões do mapa que não correspondem a nenhum arquivo
  **rastreado pelo Git** (movidos/removidos), com o contexto dono; nunca edita o
  mapa.

Consumir esses comandos também registra a **proveniência de contexto** (ids de
contexto resolvidos + digest do mapa, ou um marcador explícito
`{map: none}`/`{map: invalid}`) em cada registro de tarefa e de ciclo de revisão
do ledger (esquema v3), e `specops review` exibe um aviso não-bloqueante quando o
mapa mudou desde o planejamento.

Todos os comandos aceitam `--json` para uma superfície de máquina estável e
versionada. Códigos de saída: `0` sucesso (incluindo os estados suportados "sem
mapa" e "sem contexto correspondente"), `1` mapa bloqueante/inválido, `2` erro de
uso. A correspondência de caminhos usa globs estilo gitignore; em sobreposição
o padrão mais específico vence (prefixo literal mais longo → menos curingas →
mais segmentos), e um empate genuíno é reportado como posse ambígua. O consumo
por planejamento e revisão chega em uma feature posterior; esta entrega a base
determinística.

### `specops trace classify | validate | report | acknowledge`

**Rastreabilidade ponta a ponta** (Feature 010) conecta cada Critério de Sucesso
do spec, avançando por suas tarefas, contextos/caminhos, commits, evidências e
achados de revisão, e classifica cada caminho do **diff efetivo** (branch da
feature vs. o baseline do ledger, com renames decompostos) em um conjunto fechado
— para que a revisão bloqueie o drift *inexplicado* sem rejeitar descobertas
legítimas.

- `specops trace classify [--path <p> …]` — rotula cada caminho do diff efetivo
  como `planned` (declarado no `plan.md`, ou pertencente a um contexto declarado),
  `discovered-and-acknowledged` (registrado via `acknowledge`) ou `unexplained`.
  Omita `--path` para derivar o conjunto de mudanças do Git (árvore limpa → vazio,
  saída `0`; sem repo / sem baseline → saída `2`). Somente leitura.
- `specops trace validate` — falha fechado (saída `1`) em qualquer caminho
  `unexplained` ou defeito de trace: um Critério de Sucesso sem tarefa, uma tarefa
  concluída sem evidência (ou a tarefa final da user story sem commit), uma
  referência pendente, ou propriedade contraditória. A existência de commits é
  delegada ao `specops reconcile`.
- `specops trace report` — renderiza a cadeia completa (Critérios de Sucesso →
  tarefas → commits → evidências → achados), com descobertas listadas à parte.
- `specops trace acknowledge <path> --task <id> --reason "<motivo>"` — registra um
  reconhecimento único, no nível do caminho, de uma descoberta genuína para que
  ela deixe de ser `unexplained`. Idempotente para um registro idêntico; falha
  fechado (saída `2`) em reconhecimento conflitante ou de tarefa inexistente;
  no-op para um caminho já planejado.

Os reconhecimentos ficam no ledger (schema **v4**, migrado adiante
automaticamente). Todos os comandos aceitam `--json` para uma superfície estável e
versionada, e mapeiam na taxonomia de saída `0`/`1`/`2` com um campo `status`.

### `specops handoff finding … | authorize | close | validate | report | import | render`

**Handoffs corretivos estruturados** (Feature 011) tornam os achados de revisão e a
autorização de correção estado versionado de primeira classe no ledger — de modo
que uma revisão rejeitada pode ser retomada apenas a partir do estado do
repositório e a aprovação é impossível enquanto qualquer achado **bloqueante**
estiver não verificado.

- `specops handoff finding add --severity <blocking|advisory> --rule "…" --file <p>
  [--line <n>] --action "…" [--expected-evidence "…" --closure "…"]` — registra um
  achado com um id estável `R<round>-F<NN>` na rodada de revisão atual. Achados
  bloqueantes exigem evidência esperada + critérios de encerramento.
- `specops handoff finding fix <id> --task <id> --commit <sha> …
  (--evidence <CLASS>:<summary> | --auto)` — `OPEN → FIXED`, vinculando a correção.
- `specops handoff finding verify <id>` — `FIXED → VERIFIED` (pré-condição
  mecânica: evidência presente + vínculos resolvem; sem auto-verificação).
  Transições ilegais falham fechado (saída `2`).
- `specops handoff finding dismiss <id> --reason "…"` — descarta um achado falso
  positivo ou de rodada superada para um estado terminal `DISMISSED` (com motivo
  auditado), de modo que ele deixe de bloquear a aprovação, sem forjar uma correção.
- `specops handoff authorize --path <p> …` — registra os caminhos corretivos
  autorizados da rodada (uma mudança fora deles aparece como `unexplained` via
  `trace`).
- `specops handoff close` — encerra o handoff quando todo achado bloqueante está
  `VERIFIED` (idempotente; saída `1` enquanto restar algum).
- `specops handoff validate` — falha fechado (saída `1`) em referência pendente,
  achado bloqueante sem critério de encerramento, estado contraditório ou id
  duplicado. `specops handoff report` — renderiza cada achado e o conjunto
  bloqueante restante. Ambos somente leitura.
- `specops handoff import [--round <n>]` — importa prosa de revisão legada em
  achados advisory. `specops handoff render --round <n>` — projeta os achados
  estruturados em um `revisions/revision-X.md` compatível.

Os achados ficam no ledger (schema **v5**, migrado adiante automaticamente); o
relatório de revisão em Markdown é uma projeção renderizada desse estado
autoritativo. `specops status transition-phase DONE` falha fechado enquanto
qualquer achado bloqueante estiver não verificado; um repositório sem achados
estruturados degrada para o gate anterior.

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
3. Revisão cirúrgica apenas dos arquivos do diff efetivo.
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
