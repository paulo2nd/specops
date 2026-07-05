"""specops init: marker-injection engine and full init flow (US1)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from specops import config, gitops, speckit

# ---------------------------------------------------------------------------
# Marker grammar (R3, contracts/directive-blocks.md)
# ---------------------------------------------------------------------------

_BEGIN_RE = re.compile(r"<!-- SPECOPS:BEGIN (\S+) v(\d+) -->")
_END_RE = re.compile(r"<!-- SPECOPS:END (\S+) -->")

SEPARATOR = "\n"  # one blank line before each block at EOF


class InjectionError(Exception):
    """Raised on corrupted markers; no file is written."""


def _scan_markers(text: str) -> list[tuple[str, int, int]]:
    """
    Parse all SPECOPS marker regions in *text*.

    Returns a list of (block_id, begin_line_index, end_line_index) tuples
    where indices refer to positions in text.splitlines().

    Raises InjectionError on:
    - BEGIN without END
    - Duplicate BEGIN for the same block_id
    - Nested markers
    """
    lines = text.splitlines(keepends=True)
    open_blocks: dict[str, int] = {}  # block_id -> begin char offset
    results = []
    open_stack: list[str] = []

    # Work character-offset level for replace, but also track for error reporting
    for i, line in enumerate(lines):
        begin_m = _BEGIN_RE.search(line)
        end_m = _END_RE.search(line)
        if begin_m and end_m:
            raise InjectionError(
                f"Line {i + 1}: both BEGIN and END markers on the same line."
            )
        if begin_m:
            block_id = begin_m.group(1)
            if block_id in open_blocks:
                raise InjectionError(
                    f"Line {i + 1}: duplicate BEGIN for block '{block_id}'."
                )
            if open_stack:
                raise InjectionError(
                    f"Line {i + 1}: nested BEGIN for block '{block_id}' inside '{open_stack[-1]}'."
                )
            open_blocks[block_id] = i
            open_stack.append(block_id)
        elif end_m:
            block_id = end_m.group(1)
            if block_id not in open_blocks:
                raise InjectionError(
                    f"Line {i + 1}: END for block '{block_id}' without matching BEGIN."
                )
            begin_idx = open_blocks.pop(block_id)
            open_stack.pop()
            results.append((block_id, begin_idx, i))

    if open_blocks:
        for block_id, line_idx in open_blocks.items():
            raise InjectionError(
                f"Line {line_idx + 1}: BEGIN for block '{block_id}' without matching END."
            )

    return results


def inject_block(file_path: Path, block_id: str, block_content: str, version: int = 1) -> str:
    """
    Inject or update a SPECOPS marker block in *file_path*.

    - If no block with *block_id* exists: append at EOF (with one blank separator line).
    - If block exists: replace the content between markers in-place and update version.
    - Returns "created", "updated", or "unchanged".
    - Raises InjectionError on corrupted markers (no write performed).
    """
    text = file_path.read_text(encoding="utf-8")
    regions = _scan_markers(text)

    begin_marker = f"<!-- SPECOPS:BEGIN {block_id} v{version} -->"
    end_marker = f"<!-- SPECOPS:END {block_id} -->"
    full_block = f"\n{begin_marker}\n{block_content}\n{end_marker}\n"

    existing = {r[0]: r for r in regions}
    if block_id not in existing:
        # Append at EOF — never modify pre-existing bytes (SC-010)
        new_text = text.rstrip("\n") + "\n" + full_block
        file_path.write_text(new_text, encoding="utf-8")
        return "created"

    # In-place replacement between markers
    lines = text.splitlines(keepends=True)
    _, begin_idx, end_idx = existing[block_id]

    # Check whether content is already identical
    current_lines = lines[begin_idx + 1: end_idx]
    current_content = "".join(current_lines).strip("\n")
    if current_content == block_content.strip("\n") and f"v{version}" in lines[begin_idx]:
        return "unchanged"

    new_lines = (
        lines[:begin_idx]
        + [f"{begin_marker}\n"]
        + [block_content.strip("\n") + "\n"]
        + [f"{end_marker}\n"]
        + lines[end_idx + 1:]
    )
    file_path.write_text("".join(new_lines), encoding="utf-8")
    return "updated"


def remove_block(file_path: Path, block_id: str) -> bool:
    """
    Remove a SPECOPS marker block (block + its preceding blank separator line).

    Returns True if a block was removed, False if not present.
    Raises InjectionError on corrupted markers.
    """
    text = file_path.read_text(encoding="utf-8")
    regions = _scan_markers(text)
    existing = {r[0]: r for r in regions}
    if block_id not in existing:
        return False

    lines = text.splitlines(keepends=True)
    _, begin_idx, end_idx = existing[block_id]

    # Remove the block lines plus the preceding blank separator line
    start = begin_idx
    if start > 0 and lines[start - 1].strip() == "":
        start -= 1

    new_lines = lines[:start] + lines[end_idx + 1:]
    file_path.write_text("".join(new_lines), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------

def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def _read_template(rel: str) -> str:
    return (_templates_dir() / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Full init flow (T016)
# ---------------------------------------------------------------------------

def run(root: Path, non_interactive: bool = False) -> None:
    """
    Execute the full `specops init` flow.

    Steps per cli-contract.md:
    1. Git check (offer init if absent; --non-interactive declines)
    2. Speckit check
    3. Resolve prompt targets (manifest-driven, fail closed)
    4. specops.json create/merge
    5. Install review.md per integration
    6. Inject directive blocks into plan/implement prompts
    """
    import typer  # local import to keep initializer usable without Typer

    # Step 1: Git check
    if not gitops.is_git_repo(root):
        if non_interactive:
            typer.echo(
                "Not a Git repository. Pass --non-interactive to skip the git init offer.", err=True
            )
            raise typer.Exit(1)
        answer = typer.confirm("Not a Git repository. Initialize one now?", default=True)
        if not answer:
            typer.echo("Aborted: Git repository required for SpecOps.", err=True)
            raise typer.Exit(1)
        result = subprocess.run(["git", "init", str(root)], capture_output=True, text=True)
        if result.returncode != 0:
            typer.echo(f"git init failed: {result.stderr}", err=True)
            raise typer.Exit(1)
        typer.echo("Git repository initialized.")

    # Step 2: Speckit check
    if not speckit.has_speckit(root):
        typer.echo(
            "Speckit not detected (.specify/templates/ missing). "
            "Run Speckit initialization first.",
            err=True,
        )
        raise typer.Exit(1)

    # Step 3: Resolve prompt targets (fail closed)
    try:
        targets = speckit.resolve_prompt_targets(root)
    except speckit.ManifestResolutionError as exc:
        typer.echo(f"Manifest resolution failed: {exc}", err=True)
        raise typer.Exit(1) from None

    # Step 4: specops.json
    _cfg, created = config.create_or_merge(root)
    config_status = "created" if created else "updated"
    typer.echo(f"  specops.json: {config_status}")

    # Steps 5 & 6: per integration — install review command and inject blocks
    plan_content = _read_template("directives/plan.md").strip()
    implement_content = _read_template("directives/implement.md").strip()
    review_content = _read_template("review.md")

    for target in targets:
        sep = target["separator"]
        plan_path: Path = target["plan_path"]
        impl_path: Path = target["implement_path"]
        # Step 5: install review.md
        review_path = speckit.derive_review_path(plan_path, root, sep)
        _install_review(review_path, review_content, sep)
        typer.echo(f"  {review_path.relative_to(root)}: installed review command")

        # Step 6: inject directive blocks
        plan_status = inject_block(plan_path, "plan", plan_content)
        typer.echo(f"  {plan_path.relative_to(root)}: plan directive {plan_status}")

        impl_status = inject_block(impl_path, "implement", implement_content)
        typer.echo(f"  {impl_path.relative_to(root)}: implement directive {impl_status}")

    typer.echo("specops init: done.")


def _install_review(review_path: Path, content: str, sep: str) -> None:
    """Install the review prompt file, wrapping with skills-mode frontmatter when needed."""
    review_path.parent.mkdir(parents=True, exist_ok=True)
    if review_path.name == "SKILL.md":
        frontmatter = "---\ndescription: SpecOps token-optimized review command\n---\n\n"
        full_content = frontmatter + content
    else:
        full_content = content
    review_path.write_text(full_content, encoding="utf-8")
