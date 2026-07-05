#!/usr/bin/env python3
"""
scope-tasks-consistency: gate mecanico zero-token analogo a architectural-lint,
executado pelo architect antes do handoff scoping->implementing.

Valida:
  1. Headers H2/H3 obrigatorios presentes em scope.md e tasks.md (methodology.md secao 10).
  2. Cada item de "## Success Criteria" em scope.md tem cobertura em pelo menos
     uma task de tasks.md (heuristica por sobreposicao de tokens significativos).
  3. Cada referencia "task-XX" em "**Dependencies**" resolve para um task block
     existente em tasks.md.
  4. Existencia empirica dos paths em "**Files to Modify**" (methodology.md secao 17.4):
     - cada bullet deve carregar sufixo "(criar)" ou "(alterar)";
     - sufixo "(alterar)": Path.exists(repo_root/path) obrigatorio - FAIL se ausente;
     - sufixo "(criar)": Path(repo_root/path).parent.exists() obrigatorio - FAIL se ausente;
     - sufixos mistos "(criar OU estender)" / "(criar OU alterar)": aceita
       exists() OU parent.exists();
     - ausencia de sufixo: WARN (transicao gradual de artefatos legados).
     A ancora textual em scope.md permanece como WARN auxiliar.

Saida no formato:
  scope-tasks-consistency: <arquivo>:<linha> - <regra violada e acao corretiva>

Exit code 0 = ok. Exit code 1 = bloqueio (erro). Warnings nao bloqueiam.

Uso:
  python3 scripts/scope-tasks-consistency.py agents/features/<feature-name>/
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SCOPE_REQUIRED_H2 = [
    "## Core Objective",
    "## Success Criteria",
    "## Required Skills & Gaps",
    "## Risks",
    "## Critical Constraints",
    "## Readiness Gate",
    "## AI Impact",
]
TASKS_REQUIRED_H2 = ["## Task Backlog"]
TASK_BULLET_KEYS = [
    "**Objective**",
    "**Acceptance Criteria**",
    "**Files to Modify**",
    "**Strategy**",
    "**Dependencies**",
]

STOPWORDS = {
    "de", "da", "do", "das", "dos", "para", "com", "sem", "em", "na", "no", "nas", "nos",
    "e", "ou", "que", "se", "um", "uma", "uns", "umas", "o", "a", "os", "as", "ao", "aos",
    "the", "an", "of", "to", "in", "on", "with", "for", "and", "or", "by", "as", "is",
    "are", "be", "ser", "esta", "estao", "este", "esse", "essa", "isso", "isto",
    "por", "pelo", "pela", "pelos", "pelas", "sobre", "entre", "como", "quando",
    "apenas", "ja", "nao", "sim", "todo", "toda", "todos", "todas", "cada", "outro",
    "outra", "outros", "outras", "mesmo", "mesma", "mesmos", "mesmas",
}

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]+")


def fail(violations: list[str], file: Path, line: int, message: str) -> None:
    violations.append(f"scope-tasks-consistency: {file}:{line} - {message}")


def warn(warnings: list[str], file: Path, line: int, message: str) -> None:
    warnings.append(f"scope-tasks-consistency: {file}:{line} - WARN {message}")


def tokens(text: str) -> set[str]:
    raw = TOKEN_RE.findall(text.lower())
    return {t for t in raw if len(t) >= 4 and t not in STOPWORDS}


def check_required_headers(
    file: Path, lines: list[str], required: list[str], violations: list[str]
) -> None:
    present = {line.strip(): idx + 1 for idx, line in enumerate(lines)}
    for header in required:
        if not any(line.strip() == header for line in lines):
            fail(violations, file, 1, f'header obrigatorio ausente: "{header}" (methodology.md secao 10)')


def extract_section(lines: list[str], header: str) -> tuple[list[str], int]:
    """Retorna as linhas dentro de uma secao H2 e a linha inicial (1-based)."""
    start: int | None = None
    out: list[str] = []
    for idx, line in enumerate(lines):
        if line.strip() == header:
            start = idx + 1
            continue
        if start is not None:
            if line.startswith("## "):
                break
            out.append(line)
    return out, (start or 0)


def extract_success_criteria(scope_lines: list[str]) -> list[tuple[int, str]]:
    section, base = extract_section(scope_lines, "## Success Criteria")
    items: list[tuple[int, str]] = []
    for offset, line in enumerate(section):
        match = re.match(r"\s*-\s*\[\s*[xX ]?\s*\]\s*(.+)", line)
        if match:
            items.append((base + offset, match.group(1).strip()))
    return items


def extract_task_blocks(tasks_lines: list[str]) -> list[dict]:
    blocks: list[dict] = []
    current: dict | None = None
    current_field: str | None = None
    for idx, raw in enumerate(tasks_lines):
        stripped = raw.strip()
        header_match = re.match(r"###\s+(task-\d+):\s*(.*)", stripped)
        if header_match:
            if current is not None:
                blocks.append(current)
            current = {
                "id": header_match.group(1),
                "goal": header_match.group(2).strip(),
                "line": idx + 1,
                "fields": {key: [] for key in TASK_BULLET_KEYS},
                "raw_body": [],
            }
            current_field = None
            continue
        if current is None:
            continue
        current["raw_body"].append(raw)
        bullet_match = re.match(r"\s*-\s+(\*\*[^*]+\*\*):?\s*(.*)", raw)
        if bullet_match and bullet_match.group(1) in TASK_BULLET_KEYS:
            current_field = bullet_match.group(1)
            tail = bullet_match.group(2).strip()
            if tail:
                current["fields"][current_field].append((idx + 1, tail))
            continue
        sub_match = re.match(r"\s+-\s+(.+)", raw)
        if sub_match and current_field is not None:
            current["fields"][current_field].append((idx + 1, sub_match.group(1).strip()))
            continue
        if stripped.startswith("###") or stripped.startswith("## "):
            current_field = None
    if current is not None:
        blocks.append(current)
    return blocks


def check_success_criteria_coverage(
    scope_file: Path,
    scope_lines: list[str],
    blocks: list[dict],
    violations: list[str],
) -> None:
    task_corpora = []
    for block in blocks:
        text = " ".join([block["goal"], *block["raw_body"]])
        task_corpora.append((block["id"], tokens(text)))

    for line_no, criterion in extract_success_criteria(scope_lines):
        crit_tokens = tokens(criterion)
        if len(crit_tokens) < 2:
            continue
        if not task_corpora:
            fail(
                violations,
                scope_file,
                line_no,
                "Success Criteria sem cobertura: tasks.md nao possui nenhum task block",
            )
            continue
        covered = any(len(crit_tokens & task_tokens) >= 2 for _, task_tokens in task_corpora)
        if not covered:
            short = criterion[:80] + ("..." if len(criterion) > 80 else "")
            fail(
                violations,
                scope_file,
                line_no,
                f'Success Criteria "{short}" sem cobertura em tasks.md - adicionar task ou remover criterio',
            )


def check_dependencies(
    tasks_file: Path, blocks: list[dict], violations: list[str]
) -> None:
    valid_ids = {block["id"] for block in blocks}
    dep_re = re.compile(r"task-\d+")
    for block in blocks:
        for line_no, dep_line in block["fields"]["**Dependencies**"]:
            if not dep_line or dep_line.lower() in {"n/a", "`n/a`", "none"}:
                continue
            for ref in dep_re.findall(dep_line):
                if ref not in valid_ids:
                    fail(
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Dependencies referencia {ref} inexistente no Task Backlog',
                    ) if False else fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Dependencies referencia {ref} inexistente no Task Backlog',
                    )


def scope_path_anchors(scope_text: str) -> set[str]:
    """Extrai tokens que parecem fragmentos de path/modulo citados em scope.md."""
    anchors: set[str] = set()
    path_re = re.compile(r"[A-Za-z0-9_./\-]+/[A-Za-z0-9_./\-]+")
    for match in path_re.findall(scope_text):
        for piece in re.split(r"[/.\\]", match):
            piece = piece.strip("`*_ ,;:()[]")
            if len(piece) >= 4 and piece.lower() not in STOPWORDS:
                anchors.add(piece.lower())
    code_re = re.compile(r"`([^`]+)`")
    for match in code_re.findall(scope_text):
        for piece in re.split(r"[/.\\\s]", match):
            piece = piece.strip("`*_ ,;:()[]")
            if len(piece) >= 4 and piece.lower() not in STOPWORDS:
                anchors.add(piece.lower())
    return anchors


PATH_IN_BACKTICKS_RE = re.compile(r"`([^`]+)`")
ACTION_SUFFIX_RE = re.compile(r"\(([^)]*?)\)")


def parse_files_to_modify_bullet(raw: str) -> tuple[str | None, str]:
    """
    Extrai (path, action) de um bullet de Files to Modify.

    action retorna: "alter" | "create" | "either" | "remove" | "unknown".
    path retorna None quando o bullet nao contem path identificavel (ex.: "N/A").
    """
    text = raw.strip()
    if not text or text.lower() in {"n/a", "none", "`n/a`"}:
        return None, "unknown"

    backtick_match = PATH_IN_BACKTICKS_RE.search(text)
    if backtick_match:
        path = backtick_match.group(1).strip()
    else:
        # Fallback: pega tudo antes do primeiro "(" como path candidato.
        paren_idx = text.find("(")
        path = (text[:paren_idx] if paren_idx >= 0 else text).strip().strip("`")

    if not path or path.lower() in {"n/a", "none"}:
        return None, "unknown"

    has_criar = False
    has_alterar = False
    has_remover = False
    for match in ACTION_SUFFIX_RE.finditer(text):
        suffix = match.group(1).lower()
        if "criar" in suffix:
            has_criar = True
        if "alterar" in suffix:
            has_alterar = True
        if "remover" in suffix or "deletar" in suffix:
            has_remover = True

    if has_criar and has_alterar:
        action = "either"
    elif has_criar:
        action = "create"
    elif has_alterar:
        action = "alter"
    elif has_remover:
        action = "remove"
    else:
        action = "unknown"

    return path, action


def file_existed_in_git(repo_root: Path, relative_path: str) -> bool:
    """Verifica de forma rapida se o arquivo ja existiu rastreado no git recente (HEAD ou main)."""
    for ref in ["HEAD", "origin/main", "main"]:
        try:
            res = subprocess.run(
                ["git", "cat-file", "-e", f"{ref}:{relative_path}"],
                cwd=str(repo_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if res.returncode == 0:
                return True
        except Exception:
            pass
    return False


def check_files_to_modify(
    scope_file: Path,
    scope_text: str,
    tasks_file: Path,
    blocks: list[dict],
    repo_root: Path,
    violations: list[str],
    warnings: list[str],
) -> None:
    anchors = scope_path_anchors(scope_text)
    for block in blocks:
        for line_no, raw_path in block["fields"]["**Files to Modify**"]:
            path, action = parse_files_to_modify_bullet(raw_path)
            if path is None:
                continue

            # Validacao empirica (methodology.md secao 17.4): existencia real no worktree.
            full = (repo_root / path).resolve()
            exists = full.exists()
            parent_exists = full.parent.exists()

            if action == "alter":
                if not exists:
                    fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Files to Modify "{path}" marcado (alterar) mas nao existe no worktree - verificar path ou trocar sufixo para (criar)',
                    )
            elif action == "create":
                if not parent_exists:
                    fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Files to Modify "{path}" marcado (criar) mas pasta-pai "{full.parent.relative_to(repo_root) if full.parent.is_relative_to(repo_root) else full.parent}" nao existe - confirmar destino ou criar pasta-pai antes',
                    )
            elif action == "either":
                if not exists and not parent_exists:
                    fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Files to Modify "{path}" marcado (criar OU alterar) mas nem o arquivo nem a pasta-pai existem - verificar path',
                    )
            elif action == "remove":
                if not exists:
                    if not file_existed_in_git(repo_root, path):
                        fail(
                            violations,
                            tasks_file,
                            line_no,
                            f'task {block["id"]} > Files to Modify "{path}" marcado (remover) mas ele nunca existiu no historico Git',
                        )
            else:  # unknown / sem sufixo
                warn(
                    warnings,
                    tasks_file,
                    line_no,
                    f'task {block["id"]} > Files to Modify "{path}" sem sufixo (criar)/(alterar)/(remover) - adicionar para habilitar verificacao empirica (methodology.md secao 17.4)',
                )

            # Heuristica auxiliar de ancora textual em scope.md (mantida como WARN).
            if anchors:
                pieces = [p.lower() for p in re.split(r"[/.\\\s]", path) if len(p) >= 4]
                if pieces and not any(p in anchors for p in pieces):
                    warn(
                        warnings,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} > Files to Modify "{path}" nao tem ancora em scope.md (modulo/path nao mencionado)',
                    )


def check_unmapped_files_referenced(
    tasks_file: Path,
    blocks: list[dict],
    violations: list[str],
    warnings: list[str],
) -> None:
    # 1. Coleta caminhos declarados em Files to Modify (de todas as tasks da feature)
    declared_paths = set()
    for block in blocks:
        for _, raw_path in block["fields"]["**Files to Modify**"]:
            path, _ = parse_files_to_modify_bullet(raw_path)
            if path:
                declared_paths.add(path.replace("\\", "/").strip().lower())

    # Heuristica para paths explicios com extensao
    file_pattern = re.compile(r"([A-Za-z0-9_./\-]+\.(?:cs|csproj|json|yaml|md|sh))")
    
    # Heuristica para simbolos de wiring conhecidos no projeto
    symbol_pattern = re.compile(
        r"([A-Za-z0-9_]+(?:DbContext|Worker|BackgroundService|ConsistencyChecker|ProjectionHandler|Endpoint|Command|Query))"
    )

    for block in blocks:
        # Analisa Acceptance Criteria e Strategy
        lines_to_check = block["fields"]["**Acceptance Criteria**"] + block["fields"]["**Strategy**"]
        for line_no, content in lines_to_check:
            # Validar paths explicios citados
            for file_ref in file_pattern.findall(content):
                file_ref_lower = file_ref.strip().lower()
                if not any(file_ref_lower in p or p in file_ref_lower for p in declared_paths):
                    fail(
                        violations,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} menciona o arquivo "{file_ref}" em seu AC/Strategy, mas ele nao esta mapeado em "Files to Modify" de nenhuma task.'
                    )

            # Validar simbolos de fiacao (apenas Warning para evitar falsos positivos)
            for symbol_ref in symbol_pattern.findall(content):
                symbol_ref_lower = symbol_ref.strip().lower()
                if not any(symbol_ref_lower in p for p in declared_paths):
                    warn(
                        warnings,
                        tasks_file,
                        line_no,
                        f'task {block["id"]} cita o simbolo "{symbol_ref}" em seu AC/Strategy, mas nenhum arquivo correspondente esta em "Files to Modify".'
                    )


def find_repo_root(start: Path) -> Path:
    """Sobe a hierarquia procurando .git para determinar o repo root."""
    current = start.resolve()
    while current != current.parent:
        if (current / ".git").exists():
            return current
        current = current.parent
    return Path.cwd().resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "feature_dir",
        type=Path,
        help="Caminho para agents/features/<feature-name>/",
    )
    args = parser.parse_args()

    feature_dir: Path = args.feature_dir.resolve()
    scope_file = feature_dir / "scope.md"
    tasks_file = feature_dir / "tasks.md"
    repo_root = find_repo_root(feature_dir)

    if not scope_file.exists():
        print(
            f"scope-tasks-consistency: {scope_file} - scope.md ausente; gate aplicavel apenas a feature_complete",
            file=sys.stderr,
        )
        return 1
    if not tasks_file.exists():
        print(
            f"scope-tasks-consistency: {tasks_file} - tasks.md ausente; architect deve criar antes do handoff",
            file=sys.stderr,
        )
        return 1

    scope_lines = scope_file.read_text(encoding="utf-8").splitlines()
    tasks_lines = tasks_file.read_text(encoding="utf-8").splitlines()
    scope_text = "\n".join(scope_lines)

    violations: list[str] = []
    warnings: list[str] = []

    check_required_headers(scope_file, scope_lines, SCOPE_REQUIRED_H2, violations)
    check_required_headers(tasks_file, tasks_lines, TASKS_REQUIRED_H2, violations)

    blocks = extract_task_blocks(tasks_lines)
    if not blocks:
        fail(
            violations,
            tasks_file,
            1,
            'nenhum task block encontrado (esperado "### task-XX: [Goal]" sob "## Task Backlog")',
        )

    check_success_criteria_coverage(scope_file, scope_lines, blocks, violations)
    check_dependencies(tasks_file, blocks, violations)
    check_files_to_modify(scope_file, scope_text, tasks_file, blocks, repo_root, violations, warnings)
    check_unmapped_files_referenced(tasks_file, blocks, violations, warnings)

    for line in warnings:
        print(line, file=sys.stderr)
    for line in violations:
        print(line, file=sys.stderr)

    if violations:
        print(
            f"scope-tasks-consistency: failed with {len(violations)} violation(s)",
            file=sys.stderr,
        )
        return 1

    print("scope-tasks-consistency: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
