#!/usr/bin/env python3
import sys
import os
import argparse
import subprocess
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
    sys.exit(1)

def check_commit_in_history(commit_hash):
    if not commit_hash or commit_hash == "(human)":
        return True
    try:
        # Checks that the commit exists and is part of the current branch history (HEAD)
        res = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit_hash, "HEAD"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return res.returncode == 0
    except Exception:
        return False

def main():
    parser = argparse.ArgumentParser(description="Reconciliation checker for status.yaml against the Git history")
    parser.add_argument("-f", "--file", help="Direct path to the active status.yaml")
    args = parser.parse_args()

    branch = get_git_branch()
    status_file = find_status_file(branch, args.file)

    try:
        with open(status_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Error reading status.yaml: {e}", file=sys.stderr)
        sys.exit(1)

    if not data:
        print("Error: status.yaml is empty or invalid.", file=sys.stderr)
        sys.exit(1)

    failures = 0
    baseline = data.get("baseline")
    if baseline and baseline != "unknown":
        try:
            res = subprocess.run(
                ["git", "cat-file", "-t", baseline],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            if res.returncode != 0:
                print(f"Warning: Baseline commit '{baseline}' was not found in the local repository.", file=sys.stderr)
        except Exception:
            pass

    tasks = data.get("tasks", [])
    for task in tasks:
        task_id = task.get("id")
        status = task.get("status")
        commit_hash = task.get("commit")

        if status == "DONE":
            if not commit_hash:
                print(f"Error: Task '{task_id}' is marked DONE but has no 'commit' hash recorded.", file=sys.stderr)
                failures += 1
            elif not check_commit_in_history(commit_hash):
                print(f"Error: Commit '{commit_hash}' of task '{task_id}' is not part of the current branch history.", file=sys.stderr)
                failures += 1

    if failures > 0:
        print(f"reconcile-status: failed with {failures} consistency error(s).", file=sys.stderr)
        sys.exit(1)

    print("reconcile-status: ok")
    sys.exit(0)

if __name__ == "__main__":
    main()
