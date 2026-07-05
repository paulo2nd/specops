# SpecOps CLI — Implementation Plan

This document serves as the high-level technical specification and task plan for the development of the **SpecOps** CLI (`specops`).

The goal of `SpecOps` is to package the agent-guided atomic development methodology (Repo-as-State, status control, atomic commits, operational silence, and token-optimized review) documented in [reference/methodology.md](reference/methodology.md), turning it into an independent, generic, globally installable tool designed to run in cooperation with GitHub's **Speckit**.

---

## 1. Core Objective & Scope

Create a Python package (`specops-cli`) installable via `pip` that extends the Speckit lifecycle in any software repository. The tool is responsible for:
1. **Configuring Speckit compatibility** with our operational model of role transitions (*Roles*).
2. **Controlling the physical state of execution** through a structured ledger (`status.yaml`).
3. **Automating the collection of technical evidence** (`TEST_REPORT` and `CODE_DIFF` from Git) at the closure of each task.
4. **Enforcing surgical behavior in AIs** (Operational Silence §6, Empirical Verification §17.4, and Optimized Review §18) through injected prompt templates.

> [!IMPORTANT]
> The **SpecOps** CLI is agnostic to specific technologies or business rules (such as .NET, CQRS, RLS, or any project-specific linter). The end client's project only needs to configure its local commands in a `specops.json` file.

---

## 2. Package Architecture and Folder Structure

The `SpecOps` repository will have the following file structure:

```text
specops-cli/
├── pyproject.toml             # Python package definition, metadata, and dependencies (Typer, PyYAML, GitPython)
├── README.md                  # CLI usage and installation manual
└── src/
    └── specops/
        ├── __init__.py
        ├── cli.py             # CLI entrypoint (Typer), mapping the global commands
        ├── status.py          # Status Engine logic (port of manage-status.py)
        ├── reconcile.py       # Reconcile Engine logic (port of reconcile-status.py)
        ├── consistency.py     # SDD Consistency logic (port of scope-tasks-consistency.py)
        └── templates/         # Scaffold files injected into the client by `specops init`
            ├── review.md      # Prompt template for the /specops.review command with Skills and Evidence support
            └── status.yaml    # Clean template of the status ledger
```

---

## 3. Portability Mapping of the Reference Components

Development consists of porting the reference scripts stored locally in [`.specs/reference/`](reference/), removing any domain coupling, and packaging them into the `SpecOps` modules:

### A. status.py (Source: [reference/manage-status.py](reference/manage-status.py))
Responsible for the exclusive manipulation of `status.yaml`.
* **Exposed commands:**
  * `specops status init-spec <name>`: Creates the `.specify/specs/<name>/` folder with the initialized `status.yaml`.
  * `specops status start-task <task_id>`: Marks the task as `IN_PROGRESS` and sets it as the recovery point.
  * `specops status complete-task <task_id> [--auto]`: Marks the task as `DONE`. If `--auto` is enabled, the CLI runs the client's local test command, harvests the outputs from Git (commit hashes and diff), and records the evidence string in the `<CLASS>:<summary>` format (per §7 of [reference/methodology.md](reference/methodology.md)).
  * `specops status transition-phase <phase> [-r <result>]`: Transitions the Spec's phases.

### B. reconcile.py (Source: [reference/reconcile-status.py](reference/reconcile-status.py))
Performs offline validation of the active branch against `status.yaml`.
* **Exposed commands:**
  * `specops reconcile`: Validates that every commit hash recorded in `status.yaml` actually exists in the Git tree of the current branch. Blocks execution if there are divergences.

### C. consistency.py (Source: [reference/scope-tasks-consistency.py](reference/scope-tasks-consistency.py))
Logical consistency validator.
* **Exposed commands:**
  * `specops consistency`: Adapted to read the Speckit structure. It parses the business file (`specification.md`) and the technical plan (`plan.md`) of the active Spec's folder and validates that:
    1. Every success criterion of the Spec is covered by at least one task in the plan.
    2. The paths declared in the plan physically exist (with validation of the `(create)`, `(modify)`, etc. suffixes against the repository worktree, per §11.1).

---

## 4. Speckit Integration and Prompt Injection

The `specops init` command configures compatibility in the client's repository:

1. **Generation of `specops.json` at the client's root:**
   ```json
   {
     "test_command": "npm run test", // Client's test command
     "lint_command": "npm run lint", // Client's lint command
     "skills_dir": ".specify/skills"  // Folder where the local Skills reside
   }
   ```
2. **Injection of `/specops.review` (`review.md`):**
   Injects the token-optimized technical review prompt (§18) into Speckit's commands folder. It instructs the review agent to:
   * Load the Skills required by the Spec, located in the client's skills directory.
   * Run `specops reconcile` and abort immediately on failure.
   * Analyze the modified files via `git status --porcelain` and reject on the spot if there are changes outside `plan.md` — without reading the code (zero token cost).
   * Emit the Non-Conformities to `revisions/revision-X.md` in the short format: `[File]:[Line] - [rule violated and short action]`.

---

## 5. Implementation Backlog (Step by Step)

### [x] Task 1: Project Setup and CLI Entrypoint
* **Objective:** Initialize the `specops-cli` repository with `pyproject.toml`, dependencies (Typer, PyYAML, GitPython), and the Typer command skeleton in `src/specops/cli.py`.
* **Acceptance Criteria:** Local installation via `pip install -e .` must expose the `specops` command with a functional help.

### [ ] Task 6: Port of the Status Engine (status.py)
* **Objective:** Translate the logic of [reference/manage-status.py](reference/manage-status.py) into the CLI's [status.py](../src/specops/status.py) module.
* **Acceptance Criteria:** Be able to start, transition, and complete tasks by updating the `status.yaml` file without hallucinating. The `--auto` flag must orchestrate the harvesting of diffs and commits via GitPython.

### [ ] Task 3: Port of the Reconcile Engine (reconcile.py)
* **Objective:** Implement the commit tree validator in the [reconcile.py](../src/specops/reconcile.py) module.
* **Acceptance Criteria:** The `specops reconcile` command returns exit code 0 if the git log is consistent with the yaml, and exit code 1 when it detects orphan or inconsistent commits.

### [ ] Task 4: Port of the Consistency Engine adapted to Speckit (consistency.py)
* **Objective:** Rewrite the logical consistency validation in [consistency.py](../src/specops/consistency.py) to pair Speckit's `specification.md` with its `plan.md`.
* **Acceptance Criteria:** Block the transition (exit code 1) if the AI declares nonexistent paths without the correct suffixes or omits tasks for the Spec's success criteria.

### [ ] Task 5: Initialization Command and Templates (init.py)
* **Objective:** Create the `specops init` command that detects the Speckit folder, generates `specops.json`, and injects the `/specops.review` prompt template into `.specify/prompts/review.md`.
* **Acceptance Criteria:** Running `specops init` in a folder with Speckit leaves the environment 100% prepared with the required prompts and ledgers.

---

## 6. Execution AI System Prompt (The Working Mode)

> [!NOTE]
> The complete mapping of what each Speckit/SpecOps stage runs under each role
> (architect, implementer, reviewer) is defined in
> [lifecycle-roles.md](lifecycle-roles.md). The state machine, invariants, and role
> contracts are vendored in [reference/workflow/](reference/workflow/).

The AI agent operating under this workflow must respect the following universal behavioral guidelines defined in [reference/methodology.md](reference/methodology.md):

1. **Operational Silence (§6):** During the execution of `/speckit.implement`, the AI must act 100% silently in the chat (no step narration, no edit explanations). When switching tasks, it must print exclusively the factual line: `task-XX done (<commit-sha7>), starting task-(XX+1)` and immediately continue execution.
2. **Empirical Verification (§17.4):** The AI is expressly forbidden from declaring paths or code conventions in `plan.md` based on memory. It must run read commands in the terminal to prove the real existence of the structures in the repository before declaring them.
3. **Stop-and-Ask Gates (§8.2):** The AI must halt continuous execution and ask the human upon any change to persisted schemas (migrations), secrets, breaks of public contracts, or technical ambiguities.
