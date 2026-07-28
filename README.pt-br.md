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

## Instalação e primeiros passos

```bash
pip install speckit-specops

# Em um repositório inicializado com Speckit:
specops init          # injeta as diretivas, instala /specops-review, cria specops.json
specops status show   # consulta o estado a qualquer momento
```

Requer Python ≥ 3.10 e Git ≥ 2.30. Nenhum I/O de rede após a instalação.

## Documentação

A documentação completa é mantida apenas em inglês, para não divergir da fonte.
(A política de idiomas vale a seu favor no uso: o SpecOps analisa somente tokens
estruturais — `SC-\d+`, `T\d+`, sufixos de ação — então sua prosa em `spec.md`,
`plan.md` e nas tarefas pode estar em **qualquer idioma**, inclusive português.)

- **[README](README.md)** — visão geral, motivação, quick start e a tabela-resumo
  de comandos.
- **[docs/commands.md](docs/commands.md)** — referência completa de cada comando,
  códigos de saída, contratos JSON e o fluxo de review.
- **[docs/stability.md](docs/stability.md)** — o *contract freeze* para a 1.0: classifica
  cada superfície voltada ao adotante (`specops.json`, `status.yaml`, `lane.yaml`, arquivos
  de gate-profile, o envelope JSON, códigos de saída, o contrato de findings, o context-map
  e a saída SARIF) como **congelada**, com a regra aditiva-vs-quebra e as obrigações de
  versionamento/migração pós-1.0. Todo `--json` carrega um `output_version`.
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — setup de desenvolvimento, gates de
  qualidade e princípios do projeto.
- **[CHANGELOG.md](CHANGELOG.md)** — histórico de versões.

## Licença

[MIT](LICENSE) © Paulo Segundo
