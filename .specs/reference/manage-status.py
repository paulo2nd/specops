#!/usr/bin/env python3
import sys
import os
import re
import argparse
import subprocess
from datetime import datetime
import yaml

def get_git_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"Erro ao obter a branch git: {e}", file=sys.stderr)
        return None

def find_status_file(branch_name, file_path_arg=None):
    if file_path_arg:
        if os.path.exists(file_path_arg):
            return file_path_arg
        else:
            print(f"Erro: Arquivo especificado não existe: {file_path_arg}", file=sys.stderr)
            sys.exit(1)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    features_dir = os.path.join(repo_root, "agents", "features")

    if not os.path.exists(features_dir):
        print(f"Erro: Diretório de features não encontrado: {features_dir}", file=sys.stderr)
        sys.exit(1)

    # 1. Tenta buscar pelo nome da branch correspondente no status.yaml
    if branch_name:
        for root, dirs, files in os.walk(features_dir):
            if "status.yaml" in files:
                status_path = os.path.join(root, "status.yaml")
                try:
                    with open(status_path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data and data.get("branch") == branch_name:
                            return status_path
                except Exception:
                    pass

    # 2. Fallback: Se a branch for feat/nome-da-feature, busca a pasta correspondente
    if branch_name and branch_name.startswith("feat/"):
        feature_name = branch_name[5:]
        fallback_path = os.path.join(features_dir, feature_name, "status.yaml")
        if os.path.exists(fallback_path):
            return fallback_path

    print("Erro: Não foi possível determinar o status.yaml ativo para a branch atual.", file=sys.stderr)
    print("Por favor, passe o caminho explicitamente usando --file <caminho>", file=sys.stderr)
    sys.exit(1)

def load_yaml(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_yaml(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        # sort_keys=False para preservar a ordem das chaves
        # default_flow_style=False para garantir formato de bloco limpo
        yaml.safe_dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True)

def get_today_str():
    return datetime.today().strftime("%Y-%m-%d")

def start_task(file_path, task_id):
    data = load_yaml(file_path)
    tasks = data.get("tasks", [])
    task_found = False

    for task in tasks:
        if task.get("id") == task_id:
            task["status"] = "IN_PROGRESS"
            task_found = True
            break

    if not task_found:
        print(f"Erro: Tarefa '{task_id}' não encontrada no status.yaml.", file=sys.stderr)
        sys.exit(1)

    if "recovery" not in data or data["recovery"] is None:
        data["recovery"] = {}
    data["recovery"]["active_task"] = task_id
    data["updated_at"] = get_today_str()

    save_yaml(file_path, data)
    print(f"Sucesso: Tarefa '{task_id}' iniciada (IN_PROGRESS) no {os.path.basename(os.path.dirname(file_path))}.")

def complete_task(file_path, task_id, commit_hash, evidence, auto=False):
    data = load_yaml(file_path)
    tasks = data.get("tasks", [])
    task_found = False

    if auto:
        commit_hash = get_git_head_commit()
        try:
            res = subprocess.run(
                ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            modified_files = [os.path.basename(f) for f in res.stdout.strip().splitlines() if f]
            files_str = ", ".join(modified_files[:5])
            if len(modified_files) > 5:
                files_str += f" (+{len(modified_files) - 5} files)"
            evidence = f"CLI_LOG:git commit ok; CODE_DIFF:Modified {files_str}"
        except Exception:
            evidence = "CLI_LOG:git commit ok"

    for task in tasks:
        if task.get("id") == task_id:
            task["status"] = "DONE"
            if commit_hash:
                task["commit"] = commit_hash
            if evidence:
                task["evidence"] = evidence
            task["completed_at"] = get_today_str()
            task_found = True
            break

    if not task_found:
        print(f"Erro: Tarefa '{task_id}' não encontrada no status.yaml.", file=sys.stderr)
        sys.exit(1)

    if "recovery" not in data or data["recovery"] is None:
        data["recovery"] = {}
    
    if data["recovery"].get("active_task") == task_id:
        data["recovery"]["active_task"] = None
    
    if commit_hash:
        data["recovery"]["last_commit"] = commit_hash
        
    data["updated_at"] = get_today_str()

    save_yaml(file_path, data)
    print(f"Sucesso: Tarefa '{task_id}' completada (DONE) no {os.path.basename(os.path.dirname(file_path))}.")

def add_evidence(file_path, task_id, new_evidence):
    data = load_yaml(file_path)
    tasks = data.get("tasks", [])
    task_found = False

    for task in tasks:
        if task.get("id") == task_id:
            current_evidence = task.get("evidence")
            if current_evidence:
                # Se já tiver evidência, concatena conforme o padrão (separado por ;)
                task["evidence"] = f"{current_evidence}; {new_evidence}"
            else:
                task["evidence"] = new_evidence
            task_found = True
            break

    if not task_found:
        print(f"Erro: Tarefa '{task_id}' não encontrada no status.yaml.", file=sys.stderr)
        sys.exit(1)

    data["updated_at"] = get_today_str()
    save_yaml(file_path, data)
    print(f"Sucesso: Evidência adicionada à tarefa '{task_id}'.")

def transition_phase(file_path, next_phase, result, active_artifact=None, active_task=None):
    data = load_yaml(file_path)
    current_phase = data.get("current_phase")
    phases = data.get("phases", [])
    today = get_today_str()

    # Mapeamento do agente responsável por cada fase
    phase_agents = {
        "scoping": "architect",
        "implementing": "implementer",
        "reviewing": "reviewer",
        "revision": "reviewer",
        "done": "reviewer"
    }

    if next_phase not in phase_agents:
        print(f"Erro: Fase '{next_phase}' não reconhecida.", file=sys.stderr)
        sys.exit(1)

    # 1. Finaliza a fase atual
    if current_phase:
        for phase in phases:
            if phase.get("phase") == current_phase:
                if not phase.get("completed_at"):
                    phase["completed_at"] = today
                if result:
                    phase["result"] = result
                break

    # 2. Inicia a nova fase
    for phase in phases:
        if phase.get("phase") == next_phase:
            phase["started_at"] = today
            phase["completed_at"] = None
            phase["result"] = None
            break

    data["current_phase"] = next_phase
    data["current_agent"] = phase_agents[next_phase]
    data["updated_at"] = today

    # Ao entrar em implementing, garante que o backlog completo de tasks.md esteja
    # registrado no status.yaml. init-feature so semeia task-01, entao sem este sync
    # o implementer trava em start-task task-02 ("Tarefa nao encontrada").
    if next_phase == "implementing":
        added = _sync_tasks_into_data(data, os.path.dirname(file_path))
        if added:
            print(f"Auto sync-tasks: {len(added)} tarefa(s) adicionada(s) ao backlog: {', '.join(added)}")

    if "recovery" not in data or data["recovery"] is None:
        data["recovery"] = {}

    if active_artifact:
        data["recovery"]["active_artifact"] = active_artifact
    if active_task is not None:
        data["recovery"]["active_task"] = active_task if active_task != "null" else None

    save_yaml(file_path, data)
    print(f"Sucesso: Transição para a fase '{next_phase}' realizada (Agente: {phase_agents[next_phase]}).")

def set_pr(file_path, number, url, created_at):
    data = load_yaml(file_path)
    if "pr" not in data or data["pr"] is None:
        data["pr"] = {}
    if number:
        data["pr"]["number"] = int(number)
    if url:
        data["pr"]["url"] = url
    if created_at:
        data["pr"]["created_at"] = created_at
    data["updated_at"] = get_today_str()
    save_yaml(file_path, data)
    print("Sucesso: Informações do PR atualizadas no status.yaml.")

def get_git_head_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"

def init_feature(feature_name):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    feature_dir = os.path.join(repo_root, "agents", "features", feature_name)
    revisions_dir = os.path.join(feature_dir, "revisions")
    templates_dir = os.path.join(repo_root, "agents", "templates")
    
    os.makedirs(revisions_dir, exist_ok=True)
    
    # 1. Copiar scope.md
    scope_tpl = os.path.join(templates_dir, "feature-scope.template.md")
    scope_dest = os.path.join(feature_dir, "scope.md")
    if not os.path.exists(scope_dest):
        with open(scope_tpl, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{feature-name}}", feature_name)
        with open(scope_dest, "w", encoding="utf-8") as f:
            f.write(content)
            
    # 2. Copiar tasks.md
    tasks_tpl = os.path.join(templates_dir, "feature-tasks.template.md")
    tasks_dest = os.path.join(feature_dir, "tasks.md")
    if not os.path.exists(tasks_dest):
        with open(tasks_tpl, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{feature-name}}", feature_name)
        with open(tasks_dest, "w", encoding="utf-8") as f:
            f.write(content)
            
    # 3. Copiar status.yaml
    status_tpl = os.path.join(templates_dir, "feature-status.template.yaml")
    status_dest = os.path.join(feature_dir, "status.yaml")
    if not os.path.exists(status_dest):
        with open(status_tpl, "r", encoding="utf-8") as f:
            content = f.read()
        
        today = get_today_str()
        commit_hash = get_git_head_commit()
        
        content = content.replace("{{feature-name}}", feature_name)
        content = content.replace("{{commit-hash}}", commit_hash)
        content = content.replace("{{YYYY-MM-DD}}", today)
        
        with open(status_dest, "w", encoding="utf-8") as f:
            f.write(content)
            
    print(f"Sucesso: Feature '{feature_name}' inicializada em agents/features/{feature_name}/.")

def init_revision(status_file):
    feature_dir = os.path.dirname(status_file)
    revisions_dir = os.path.join(feature_dir, "revisions")
    os.makedirs(revisions_dir, exist_ok=True)
    
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    templates_dir = os.path.join(repo_root, "agents", "templates")
    revision_tpl = os.path.join(templates_dir, "feature-revision.template.md")
    
    # Descobre o numero da proxima revisao
    existing_revisions = []
    if os.path.exists(revisions_dir):
        for f in os.listdir(revisions_dir):
            match = re.match(r"revision-(\d+)\.md", f)
            if match:
                existing_revisions.append(int(match.group(1)))
                
    next_rev = max(existing_revisions) + 1 if existing_revisions else 1
    dest_file = os.path.join(revisions_dir, f"revision-{next_rev}.md")
    
    if os.path.exists(dest_file):
        print(f"Erro: O arquivo de revisao {os.path.basename(dest_file)} ja existe.", file=sys.stderr)
        sys.exit(1)
        
    with open(revision_tpl, "r", encoding="utf-8") as f:
        content = f.read()
        
    feature_name = os.path.basename(feature_dir)
    content = content.replace("{{feature-name}}", feature_name)
    content = content.replace("{{revision-number}}", str(next_rev))
    
    with open(dest_file, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Sucesso: Revisao '{os.path.basename(dest_file)}' inicializada.")

def init_fix(fix_name=None):
    branch = get_git_branch()
    if not fix_name:
        if branch and branch.startswith("fix/"):
            fix_name = branch[4:]
        else:
            print("Erro: Nao foi possivel determinar o nome do fix a partir da branch Git.", file=sys.stderr)
            print("Por favor, informe o nome explicitamente: python3 scripts/manage-status.py init-fix <fix-name>", file=sys.stderr)
            sys.exit(1)
            
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    fix_dir = os.path.join(repo_root, "agents", "fixes", fix_name)
    templates_dir = os.path.join(repo_root, "agents", "templates")
    
    os.makedirs(fix_dir, exist_ok=True)
    
    fix_tpl = os.path.join(templates_dir, "lightweight-fix.template.md")
    dest_file = os.path.join(fix_dir, "fix.md")
    
    if not os.path.exists(dest_file):
        with open(fix_tpl, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{fix-name}}", fix_name)
        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(content)
            
    print(f"Sucesso: Lightweight fix '{fix_name}' inicializado em agents/fixes/{fix_name}/.")


def _sync_tasks_into_data(data, feature_dir):
    """Adiciona a `data['tasks']` as tasks presentes em tasks.md e ausentes no status.yaml.

    Muta `data` in-place e retorna a lista de IDs adicionados (possivelmente vazia),
    ou None se tasks.md nao existir ou nao tiver nenhum bloco task-XX. Nao persiste em disco.
    """
    tasks_md_path = os.path.join(feature_dir, "tasks.md")
    if not os.path.exists(tasks_md_path):
        return None

    with open(tasks_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    task_ids_in_md = re.findall(r"^###\s+(task-\d+)\b", content, re.MULTILINE)
    if not task_ids_in_md:
        return None

    tasks = data.get("tasks") or []
    existing_ids = {t["id"] for t in tasks}

    added = []
    for task_id in task_ids_in_md:
        if task_id not in existing_ids:
            tasks.append({
                "id": task_id,
                "status": "PENDING",
                "commit": None,
                "evidence": None,
                "completed_at": None,
            })
            added.append(task_id)

    data["tasks"] = tasks
    return added


def sync_tasks(file_path):
    feature_dir = os.path.dirname(file_path)

    if not os.path.exists(os.path.join(feature_dir, "tasks.md")):
        print(f"Erro: tasks.md não encontrado em {feature_dir}", file=sys.stderr)
        sys.exit(1)

    data = load_yaml(file_path)
    added = _sync_tasks_into_data(data, feature_dir)

    if added is None:
        print("Aviso: Nenhum task-XX encontrado em tasks.md.")
        return

    if not added:
        print("sync-tasks: status.yaml já está em sincronia com tasks.md — nenhuma tarefa adicionada.")
        return

    data["updated_at"] = get_today_str()
    save_yaml(file_path, data)
    print(f"sync-tasks: adicionadas {len(added)} tarefa(s) ao status.yaml: {', '.join(added)}")


def run_preflight(status_file):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # 1. Valida se a branch do status.yaml confere com a branch local ativa
    data = load_yaml(status_file)
    git_branch = get_git_branch()
    yaml_branch = data.get("branch")
    
    if yaml_branch and git_branch and git_branch != yaml_branch:
        print(f"Erro no Preflight: Branch Git ativa '{git_branch}' difere da branch '{yaml_branch}' configurada no status.yaml.", file=sys.stderr)
        sys.exit(1)
        
    failures = 0
    print("Iniciando verificacoes de Preflight...")
    
    # 2. Executa architectural-lint.py
    arch_script = os.path.join(repo_root, "scripts", "architectural-lint.py")
    if os.path.exists(arch_script):
        print("- Rodando architectural linter...")
        res = subprocess.run([sys.executable, arch_script])
        if res.returncode != 0:
            failures += 1
            
    # 3. Executa reconcile-status.py
    rec_script = os.path.join(repo_root, "scripts", "reconcile-status.py")
    if os.path.exists(rec_script):
        print("- Rodando reconciliador de status...")
        res = subprocess.run([sys.executable, rec_script, "-f", status_file])
        if res.returncode != 0:
            failures += 1
            
    # 4. Se for feature completa, roda scope-tasks-consistency.py
    parent_dir = os.path.basename(os.path.dirname(os.path.dirname(status_file)))
    if parent_dir == "features":
        consistency_script = os.path.join(repo_root, "scripts", "scope-tasks-consistency.py")
        if os.path.exists(consistency_script):
            print("- Rodando validador de consistência escopo-tarefas...")
            res = subprocess.run([sys.executable, consistency_script, os.path.dirname(status_file)])
            if res.returncode != 0:
                failures += 1
                
    # 5. Executa ci-cost-guard.py
    cost_script = os.path.join(repo_root, "scripts", "ci-cost-guard.py")
    if os.path.exists(cost_script):
        print("- Rodando validador de custos de CI/CD...")
        res = subprocess.run([sys.executable, cost_script])
        if res.returncode != 0:
            failures += 1

    if failures > 0:
        print(f"\nErro no Preflight: O workspace possui {failures} suite(s) com falha. Corrija-as antes de continuar.", file=sys.stderr)
        sys.exit(1)
        
    print("\nPreflight concluido: Workspace íntegro!")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Utilitário de automação para manipulação de status.yaml")
    parser.add_argument("-f", "--file", help="Caminho direto para o status.yaml ativo")
    
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Comando start-task
    parser_start = subparsers.add_parser("start-task", help="Inicia uma tarefa no status.yaml")
    parser_start.add_argument("task_id", help="ID da tarefa (ex: task-01)")

    # Comando complete-task
    parser_complete = subparsers.add_parser("complete-task", help="Completa uma tarefa no status.yaml")
    parser_complete.add_argument("task_id", help="ID da tarefa (ex: task-01)")
    parser_complete.add_argument("-c", "--commit", help="Hash do commit associado à conclusão")
    parser_complete.add_argument("-e", "--evidence", help="Evidência curta de entrega (ex: CLI_LOG:test ok)")
    parser_complete.add_argument("--auto", action="store_true", help="Auto-detecta o último commit e arquivos modificados para evidência")

    # Comando add-evidence
    parser_evidence = subparsers.add_parser("add-evidence", help="Adiciona uma evidência a uma tarefa ativa")
    parser_evidence.add_argument("task_id", help="ID da tarefa (ex: task-01)")
    parser_evidence.add_argument("evidence_str", help="Evidência a ser adicionada (ex: CLI_LOG:build ok)")

    # Comando transition-phase
    parser_phase = subparsers.add_parser("transition-phase", help="Realiza a transição de fase de desenvolvimento")
    parser_phase.add_argument("phase", choices=["scoping", "implementing", "reviewing", "revision", "done"], help="Nome da próxima fase")
    parser_phase.add_argument("-r", "--result", help="Resultado/Status da fase concluída (ex: APPROVED, REJECTED, etc.)")
    parser_phase.add_argument("--active-artifact", help="Atualiza o recovery.active_artifact")
    parser_phase.add_argument("--active-task", help="Atualiza o recovery.active_task (use 'null' para limpar)")

    # Comando set-pr
    parser_pr = subparsers.add_parser("set-pr", help="Configura informações do Pull Request no status.yaml")
    parser_pr.add_argument("-n", "--number", type=int, help="Número do PR")
    parser_pr.add_argument("-u", "--url", help="URL do PR")
    parser_pr.add_argument("-c", "--created-at", help="Data de criação do PR (YYYY-MM-DD)")

    # Comando init-feature
    parser_init_feat = subparsers.add_parser("init-feature", help="Inicializa os documentos base de uma nova feature")
    parser_init_feat.add_argument("feature_name", help="Nome da feature (ex: billing-dunning-cascade)")

    # Comando init-revision
    parser_init_rev = subparsers.add_parser("init-revision", help="Inicializa a proxima revisao da feature ativa")

    # Comando init-fix
    parser_init_fix = subparsers.add_parser("init-fix", help="Inicializa os documentos de um lightweight fix")
    parser_init_fix.add_argument("fix_name", nargs="?", help="Nome do fix (opcional se puder deduzir da branch)")

    # Comando sync-tasks
    subparsers.add_parser("sync-tasks", help="Sincroniza tasks do tasks.md com o status.yaml, adicionando entradas ausentes como PENDING")

    # Comando preflight
    parser_preflight = subparsers.add_parser("preflight", help="Executa verificacoes de integridade de preflight locais do workspace")

    args = parser.parse_args()

    # Comandos que nao exigem a existencia previa de status.yaml ativo
    if args.command == "init-feature":
        init_feature(args.feature_name)
        sys.exit(0)
    elif args.command == "init-fix":
        init_fix(args.fix_name)
        sys.exit(0)

    branch = get_git_branch()
    status_file = find_status_file(branch, args.file)

    if args.command == "start-task":
        start_task(status_file, args.task_id)
    elif args.command == "complete-task":
        complete_task(status_file, args.task_id, args.commit, args.evidence, args.auto)
    elif args.command == "add-evidence":
        add_evidence(status_file, args.task_id, args.evidence_str)
    elif args.command == "transition-phase":
        transition_phase(status_file, args.phase, args.result, args.active_artifact, args.active_task)
    elif args.command == "set-pr":
        set_pr(status_file, args.number, args.url, args.created_at)
    elif args.command == "init-revision":
        init_revision(status_file)
    elif args.command == "sync-tasks":
        sync_tasks(status_file)
    elif args.command == "preflight":
        run_preflight(status_file)

if __name__ == "__main__":
    main()
