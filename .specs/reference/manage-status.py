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
        print(f"Error getting the git branch: {e}", file=sys.stderr)
        return None

def find_status_file(branch_name, file_path_arg=None):
    if file_path_arg:
        if os.path.exists(file_path_arg):
            return file_path_arg
        else:
            print(f"Error: Specified file does not exist: {file_path_arg}", file=sys.stderr)
            sys.exit(1)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    features_dir = os.path.join(repo_root, "agents", "features")

    if not os.path.exists(features_dir):
        print(f"Error: Features directory not found: {features_dir}", file=sys.stderr)
        sys.exit(1)

    # 1. Try to find the status.yaml whose branch matches the active branch
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

    # 2. Fallback: if the branch is feat/<feature-name>, look for the matching folder
    if branch_name and branch_name.startswith("feat/"):
        feature_name = branch_name[5:]
        fallback_path = os.path.join(features_dir, feature_name, "status.yaml")
        if os.path.exists(fallback_path):
            return fallback_path

    print("Error: Could not determine the active status.yaml for the current branch.", file=sys.stderr)
    print("Please pass the path explicitly using --file <path>", file=sys.stderr)
    sys.exit(1)

def load_yaml(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_yaml(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        # sort_keys=False to preserve key order
        # default_flow_style=False to guarantee clean block format
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
        print(f"Error: Task '{task_id}' not found in status.yaml.", file=sys.stderr)
        sys.exit(1)

    if "recovery" not in data or data["recovery"] is None:
        data["recovery"] = {}
    data["recovery"]["active_task"] = task_id
    data["updated_at"] = get_today_str()

    save_yaml(file_path, data)
    print(f"Success: Task '{task_id}' started (IN_PROGRESS) in {os.path.basename(os.path.dirname(file_path))}.")

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
        print(f"Error: Task '{task_id}' not found in status.yaml.", file=sys.stderr)
        sys.exit(1)

    if "recovery" not in data or data["recovery"] is None:
        data["recovery"] = {}

    if data["recovery"].get("active_task") == task_id:
        data["recovery"]["active_task"] = None

    if commit_hash:
        data["recovery"]["last_commit"] = commit_hash

    data["updated_at"] = get_today_str()

    save_yaml(file_path, data)
    print(f"Success: Task '{task_id}' completed (DONE) in {os.path.basename(os.path.dirname(file_path))}.")

def add_evidence(file_path, task_id, new_evidence):
    data = load_yaml(file_path)
    tasks = data.get("tasks", [])
    task_found = False

    for task in tasks:
        if task.get("id") == task_id:
            current_evidence = task.get("evidence")
            if current_evidence:
                # If evidence already exists, concatenate per the standard (separated by ;)
                task["evidence"] = f"{current_evidence}; {new_evidence}"
            else:
                task["evidence"] = new_evidence
            task_found = True
            break

    if not task_found:
        print(f"Error: Task '{task_id}' not found in status.yaml.", file=sys.stderr)
        sys.exit(1)

    data["updated_at"] = get_today_str()
    save_yaml(file_path, data)
    print(f"Success: Evidence added to task '{task_id}'.")

def transition_phase(file_path, next_phase, result, active_artifact=None, active_task=None):
    data = load_yaml(file_path)
    current_phase = data.get("current_phase")
    phases = data.get("phases", [])
    today = get_today_str()

    # Mapping of the agent responsible for each phase
    phase_agents = {
        "scoping": "architect",
        "implementing": "implementer",
        "reviewing": "reviewer",
        "revision": "reviewer",
        "done": "reviewer"
    }

    if next_phase not in phase_agents:
        print(f"Error: Phase '{next_phase}' not recognized.", file=sys.stderr)
        sys.exit(1)

    # 1. Close the current phase
    if current_phase:
        for phase in phases:
            if phase.get("phase") == current_phase:
                if not phase.get("completed_at"):
                    phase["completed_at"] = today
                if result:
                    phase["result"] = result
                break

    # 2. Start the new phase
    for phase in phases:
        if phase.get("phase") == next_phase:
            phase["started_at"] = today
            phase["completed_at"] = None
            phase["result"] = None
            break

    data["current_phase"] = next_phase
    data["current_agent"] = phase_agents[next_phase]
    data["updated_at"] = today

    # When entering implementing, ensure the full tasks.md backlog is registered
    # in status.yaml. init-feature only seeds task-01, so without this sync the
    # implementer gets stuck at start-task task-02 ("Task not found").
    if next_phase == "implementing":
        added = _sync_tasks_into_data(data, os.path.dirname(file_path))
        if added:
            print(f"Auto sync-tasks: {len(added)} task(s) added to the backlog: {', '.join(added)}")

    if "recovery" not in data or data["recovery"] is None:
        data["recovery"] = {}

    if active_artifact:
        data["recovery"]["active_artifact"] = active_artifact
    if active_task is not None:
        data["recovery"]["active_task"] = active_task if active_task != "null" else None

    save_yaml(file_path, data)
    print(f"Success: Transition to phase '{next_phase}' completed (Agent: {phase_agents[next_phase]}).")

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
    print("Success: PR information updated in status.yaml.")

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

    # 1. Copy scope.md
    scope_tpl = os.path.join(templates_dir, "feature-scope.template.md")
    scope_dest = os.path.join(feature_dir, "scope.md")
    if not os.path.exists(scope_dest):
        with open(scope_tpl, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{feature-name}}", feature_name)
        with open(scope_dest, "w", encoding="utf-8") as f:
            f.write(content)

    # 2. Copy tasks.md
    tasks_tpl = os.path.join(templates_dir, "feature-tasks.template.md")
    tasks_dest = os.path.join(feature_dir, "tasks.md")
    if not os.path.exists(tasks_dest):
        with open(tasks_tpl, "r", encoding="utf-8") as f:
            content = f.read()
        content = content.replace("{{feature-name}}", feature_name)
        with open(tasks_dest, "w", encoding="utf-8") as f:
            f.write(content)

    # 3. Copy status.yaml
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

    print(f"Success: Feature '{feature_name}' initialized in agents/features/{feature_name}/.")

def init_revision(status_file):
    feature_dir = os.path.dirname(status_file)
    revisions_dir = os.path.join(feature_dir, "revisions")
    os.makedirs(revisions_dir, exist_ok=True)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    templates_dir = os.path.join(repo_root, "agents", "templates")
    revision_tpl = os.path.join(templates_dir, "feature-revision.template.md")

    # Determine the number of the next revision
    existing_revisions = []
    if os.path.exists(revisions_dir):
        for f in os.listdir(revisions_dir):
            match = re.match(r"revision-(\d+)\.md", f)
            if match:
                existing_revisions.append(int(match.group(1)))

    next_rev = max(existing_revisions) + 1 if existing_revisions else 1
    dest_file = os.path.join(revisions_dir, f"revision-{next_rev}.md")

    if os.path.exists(dest_file):
        print(f"Error: The revision file {os.path.basename(dest_file)} already exists.", file=sys.stderr)
        sys.exit(1)

    with open(revision_tpl, "r", encoding="utf-8") as f:
        content = f.read()

    feature_name = os.path.basename(feature_dir)
    content = content.replace("{{feature-name}}", feature_name)
    content = content.replace("{{revision-number}}", str(next_rev))

    with open(dest_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Success: Revision '{os.path.basename(dest_file)}' initialized.")

def init_fix(fix_name=None):
    branch = get_git_branch()
    if not fix_name:
        if branch and branch.startswith("fix/"):
            fix_name = branch[4:]
        else:
            print("Error: Could not determine the fix name from the Git branch.", file=sys.stderr)
            print("Please provide the name explicitly: python3 scripts/manage-status.py init-fix <fix-name>", file=sys.stderr)
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

    print(f"Success: Lightweight fix '{fix_name}' initialized in agents/fixes/{fix_name}/.")


def _sync_tasks_into_data(data, feature_dir):
    """Adds to `data['tasks']` the tasks present in tasks.md and absent from status.yaml.

    Mutates `data` in place and returns the list of added IDs (possibly empty),
    or None when tasks.md does not exist or has no task-XX block. Does not persist to disk.
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
        print(f"Error: tasks.md not found in {feature_dir}", file=sys.stderr)
        sys.exit(1)

    data = load_yaml(file_path)
    added = _sync_tasks_into_data(data, feature_dir)

    if added is None:
        print("Warning: No task-XX found in tasks.md.")
        return

    if not added:
        print("sync-tasks: status.yaml is already in sync with tasks.md — no tasks added.")
        return

    data["updated_at"] = get_today_str()
    save_yaml(file_path, data)
    print(f"sync-tasks: added {len(added)} task(s) to status.yaml: {', '.join(added)}")


def run_preflight(status_file):
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # 1. Validate that the status.yaml branch matches the active local branch
    data = load_yaml(status_file)
    git_branch = get_git_branch()
    yaml_branch = data.get("branch")

    if yaml_branch and git_branch and git_branch != yaml_branch:
        print(f"Preflight error: Active Git branch '{git_branch}' differs from the branch '{yaml_branch}' configured in status.yaml.", file=sys.stderr)
        sys.exit(1)

    failures = 0
    print("Starting Preflight checks...")

    # 2. Run architectural-lint.py
    arch_script = os.path.join(repo_root, "scripts", "architectural-lint.py")
    if os.path.exists(arch_script):
        print("- Running architectural linter...")
        res = subprocess.run([sys.executable, arch_script])
        if res.returncode != 0:
            failures += 1

    # 3. Run reconcile-status.py
    rec_script = os.path.join(repo_root, "scripts", "reconcile-status.py")
    if os.path.exists(rec_script):
        print("- Running status reconciler...")
        res = subprocess.run([sys.executable, rec_script, "-f", status_file])
        if res.returncode != 0:
            failures += 1

    # 4. If it is a full feature, run scope-tasks-consistency.py
    parent_dir = os.path.basename(os.path.dirname(os.path.dirname(status_file)))
    if parent_dir == "features":
        consistency_script = os.path.join(repo_root, "scripts", "scope-tasks-consistency.py")
        if os.path.exists(consistency_script):
            print("- Running scope-tasks consistency validator...")
            res = subprocess.run([sys.executable, consistency_script, os.path.dirname(status_file)])
            if res.returncode != 0:
                failures += 1

    # 5. Run ci-cost-guard.py
    cost_script = os.path.join(repo_root, "scripts", "ci-cost-guard.py")
    if os.path.exists(cost_script):
        print("- Running CI/CD cost validator...")
        res = subprocess.run([sys.executable, cost_script])
        if res.returncode != 0:
            failures += 1

    if failures > 0:
        print(f"\nPreflight error: The workspace has {failures} failing suite(s). Fix them before continuing.", file=sys.stderr)
        sys.exit(1)

    print("\nPreflight complete: Workspace healthy!")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Automation utility for manipulating status.yaml")
    parser.add_argument("-f", "--file", help="Direct path to the active status.yaml")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # start-task command
    parser_start = subparsers.add_parser("start-task", help="Starts a task in status.yaml")
    parser_start.add_argument("task_id", help="Task ID (e.g., task-01)")

    # complete-task command
    parser_complete = subparsers.add_parser("complete-task", help="Completes a task in status.yaml")
    parser_complete.add_argument("task_id", help="Task ID (e.g., task-01)")
    parser_complete.add_argument("-c", "--commit", help="Commit hash associated with the completion")
    parser_complete.add_argument("-e", "--evidence", help="Short delivery evidence (e.g., CLI_LOG:test ok)")
    parser_complete.add_argument("--auto", action="store_true", help="Auto-detects the latest commit and modified files for evidence")

    # add-evidence command
    parser_evidence = subparsers.add_parser("add-evidence", help="Adds evidence to an active task")
    parser_evidence.add_argument("task_id", help="Task ID (e.g., task-01)")
    parser_evidence.add_argument("evidence_str", help="Evidence to add (e.g., CLI_LOG:build ok)")

    # transition-phase command
    parser_phase = subparsers.add_parser("transition-phase", help="Performs the development phase transition")
    parser_phase.add_argument("phase", choices=["scoping", "implementing", "reviewing", "revision", "done"], help="Name of the next phase")
    parser_phase.add_argument("-r", "--result", help="Result/status of the completed phase (e.g., APPROVED, REJECTED, etc.)")
    parser_phase.add_argument("--active-artifact", help="Updates recovery.active_artifact")
    parser_phase.add_argument("--active-task", help="Updates recovery.active_task (use 'null' to clear)")

    # set-pr command
    parser_pr = subparsers.add_parser("set-pr", help="Sets Pull Request information in status.yaml")
    parser_pr.add_argument("-n", "--number", type=int, help="PR number")
    parser_pr.add_argument("-u", "--url", help="PR URL")
    parser_pr.add_argument("-c", "--created-at", help="PR creation date (YYYY-MM-DD)")

    # init-feature command
    parser_init_feat = subparsers.add_parser("init-feature", help="Initializes the base documents of a new feature")
    parser_init_feat.add_argument("feature_name", help="Feature name (e.g., billing-dunning-cascade)")

    # init-revision command
    parser_init_rev = subparsers.add_parser("init-revision", help="Initializes the next revision of the active feature")

    # init-fix command
    parser_init_fix = subparsers.add_parser("init-fix", help="Initializes the documents of a lightweight fix")
    parser_init_fix.add_argument("fix_name", nargs="?", help="Fix name (optional when deducible from the branch)")

    # sync-tasks command
    subparsers.add_parser("sync-tasks", help="Syncs tasks from tasks.md into status.yaml, adding missing entries as PENDING")

    # preflight command
    parser_preflight = subparsers.add_parser("preflight", help="Runs local workspace preflight integrity checks")

    args = parser.parse_args()

    # Commands that do not require a pre-existing active status.yaml
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
