"""Speckit layout detection, feature-dir resolution, and structural token parsing."""
from __future__ import annotations

import json
import re
from pathlib import Path

from specops.errors import SpecopsError

# ---------------------------------------------------------------------------
# Detection & feature-dir resolution (R1)
# ---------------------------------------------------------------------------

_TASK_ID_RE = re.compile(r"^\s*-\s*\[[ xX]\]\s*(T\d+)\b", re.MULTILINE)
_SC_DEF_RE = re.compile(r"-\s*\*\*(SC-\d+)\*\*:", re.MULTILINE)
_COVERAGE_TAG_RE = re.compile(r"\[(SC-\d+(?:,SC-\d+)*)\]")
_ACTION_SUFFIX_RE = re.compile(r"\((create|modify|remove)(?:\s+OR\s+(?:extend|modify))?\)")


def has_speckit(root: Path) -> bool:
    """Return True when *root* contains a Speckit installation (.specify/templates/)."""
    return (root / ".specify" / "templates").is_dir()


def resolve_feature_dir(root: Path) -> Path | None:
    """
    Return the active feature directory.

    Reads .specify/feature.json > feature_directory.
    Fallback: newest specs/NNN-* directory by name (lexicographic).
    Returns None when neither source yields a valid directory.
    """
    feature_json = root / ".specify" / "feature.json"
    if feature_json.is_file():
        try:
            data = json.loads(feature_json.read_text())
            rel = data.get("feature_directory", "")
            if rel:
                candidate = (root / rel).resolve()
                if candidate.is_dir():
                    return candidate
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: newest specs/NNN-* directory (numeric prefix sort, tie-break full name)
    specs_dir = root / "specs"
    if specs_dir.is_dir():
        def _numeric_key(d: Path) -> tuple[int, str]:
            m = re.match(r"(\d+)", d.name)
            return (int(m.group(1)) if m else 0, d.name)

        candidates = sorted(
            [d for d in specs_dir.iterdir() if d.is_dir() and re.match(r"\d+", d.name)],
            key=_numeric_key,
            reverse=True,
        )
        if candidates:
            return candidates[0]

    return None


# ---------------------------------------------------------------------------
# Task-ID / SC-ID / coverage-tag extraction (R5, R6)
# ---------------------------------------------------------------------------

def extract_task_ids(tasks_md_text: str) -> list[str]:
    """Return task IDs (e.g. T001) found in tasks.md checklist lines, in order."""
    return _TASK_ID_RE.findall(tasks_md_text)


def extract_sc_ids(spec_text: str) -> list[str]:
    """Return SC IDs (e.g. SC-001) from spec Success Criteria bullets."""
    return _SC_DEF_RE.findall(spec_text)


def extract_coverage_tags(task_line: str) -> list[str]:
    """Return SC IDs referenced in coverage tags on a single task line."""
    ids: list[str] = []
    for match in _COVERAGE_TAG_RE.finditer(task_line):
        ids.extend(match.group(1).split(","))
    return ids


def extract_action_suffixes(plan_text: str) -> list[tuple[str, str]]:
    """
    Return (path_declaration, action) pairs from plan.md path declarations.

    Scans for lines like ``src/foo.py (create)`` and returns the suffix verb.
    """
    results: list[tuple[str, str]] = []
    for line in plan_text.splitlines():
        m = _ACTION_SUFFIX_RE.search(line)
        if m:
            results.append((line.strip(), m.group(1)))
    return results


_PATH_BEFORE_ACTION_RE = re.compile(
    r"(`[^`]+`|[\w./\-]+\.[\w./\-]+)\s+\((?:create|modify|remove)"
)
_BACKTICK_PATH_RE = re.compile(r"`([^`]+)`\s+\(")


def parse_plan_path_action(line: str) -> tuple[str, str] | None:
    """
    Extract (path, action) from a plan.md path-suffix declaration line.

    Returns None when the line has no recognizable path-action pair.
    """
    m_action = _ACTION_SUFFIX_RE.search(line)
    if not m_action:
        return None
    action = m_action.group(1).lower()

    m_path = _PATH_BEFORE_ACTION_RE.search(line)
    if not m_path:
        m_path = _BACKTICK_PATH_RE.search(line)
    if not m_path:
        return None

    raw_path = m_path.group(1).strip("`").strip()
    return (raw_path, action)


_CONTEXT_DECL_RE = re.compile(
    r"^\s*(?:[-*]\s*)?\*{0,2}SpecOps-Contexts\*{0,2}\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_CTX_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")


def parse_plan_context_ids(plan_text: str) -> list[str]:
    """Return the context IDs declared in a plan's ``**SpecOps-Contexts**:`` line.

    Recognizes an optional list-bullet and optional bold markers, e.g.
    ``**SpecOps-Contexts**: api, api-auth, config``. IDs are comma-separated,
    trimmed, validated against the context-id grammar, and de-duplicated
    preserving first-seen order. Returns [] when no declaration line is present
    (Feature 009, FR-002/FR-003).
    """
    ids: list[str] = []
    seen: set[str] = set()
    for m in _CONTEXT_DECL_RE.finditer(plan_text):
        for raw in m.group(1).split(","):
            cid = raw.strip().strip("`")
            if cid and _CTX_ID_RE.match(cid) and cid not in seen:
                seen.add(cid)
                ids.append(cid)
    return ids


# ---------------------------------------------------------------------------
# Manifest-driven prompt-target resolution (R2)
# ---------------------------------------------------------------------------

class ManifestResolutionError(SpecopsError):
    """Raised when prompt targets cannot be resolved from Speckit manifests."""


def resolve_prompt_targets(root: Path) -> list[dict]:
    """
    Resolve plan/implement prompt file paths for every installed integration.

    Returns a list of dicts:
      {
        "integration": str,
        "separator": str,
        "plan_path": Path,
        "implement_path": Path,
        "specify_path": Path | None,
        "tasks_path": Path | None,
      }

    plan_path/implement_path are mandatory (fail-closed). specify_path/tasks_path
    are best-effort: resolved when the manifest lists them and the file exists,
    otherwise None — this keeps partial Speckit layouts working (graceful
    degradation) while full layouts get every stage wired.

    Raises ManifestResolutionError (fail-closed, R2) when:
    - integration.json is missing
    - an integration lacks a manifest
    - a manifest lacks plan/implement entries
    - a listed plan/implement file is absent on disk
    """
    integration_json = root / ".specify" / "integration.json"
    if not integration_json.is_file():
        raise ManifestResolutionError(
            f"Missing {integration_json} — run Speckit initialization first."
        )

    try:
        integration_data = json.loads(integration_json.read_text())
    except json.JSONDecodeError as exc:
        raise ManifestResolutionError(
            f"Cannot parse {integration_json}: {exc}"
        ) from exc

    installed: list[str] = integration_data.get("installed_integrations", [])
    settings: dict = integration_data.get("integration_settings", {})

    results = []
    for agent in installed:
        sep = settings.get(agent, {}).get("invoke_separator", ".")
        manifest_path = root / ".specify" / "integrations" / f"{agent}.manifest.json"
        if not manifest_path.is_file():
            raise ManifestResolutionError(
                f"Missing manifest for integration '{agent}': {manifest_path}"
            )
        try:
            manifest = json.loads(manifest_path.read_text())
        except json.JSONDecodeError as exc:
            raise ManifestResolutionError(
                f"Cannot parse {manifest_path}: {exc}"
            ) from exc

        files: dict = manifest.get("files", {})
        plan_path = _find_prompt_file(root, files, agent, sep, "plan")
        impl_path = _find_prompt_file(root, files, agent, sep, "implement")
        specify_path = _find_optional_prompt_file(root, files, agent, sep, "specify")
        tasks_path = _find_optional_prompt_file(root, files, agent, sep, "tasks")
        results.append(
            {
                "integration": agent,
                "separator": sep,
                "plan_path": plan_path,
                "implement_path": impl_path,
                "specify_path": specify_path,
                "tasks_path": tasks_path,
            }
        )

    return results


def _matches_role(rel: str, stem: str) -> bool:
    """
    True when manifest path *rel* is the prompt file for *stem*.

    Matches on an exact path component (``.../speckit-tasks/SKILL.md``) or a
    filename that is ``stem`` optionally followed by suffixes
    (``speckit.tasks.md``, ``speckit.tasks.prompt.md``). Exact-component
    matching — never a substring — so ``speckit-tasks`` does NOT match
    ``speckit-taskstoissues``.
    """
    p = Path(rel)
    if stem in p.parts:
        return True
    name = p.name
    return name == stem or name.startswith(f"{stem}.")


def _find_prompt_file(root: Path, files: dict, agent: str, sep: str, role: str) -> Path:
    """
    Locate the prompt file for *role* inside *files* (fail-closed).

    Matches an exact ``speckit{sep}{role}`` path component or filename
    (handles SKILL.md wrappers, .prompt.md variants, etc.).
    """
    stem = f"speckit{sep}{role}"
    matches = [rel for rel in files if _matches_role(rel, stem)]
    if not matches:
        raise ManifestResolutionError(
            f"Integration '{agent}': no '{stem}' entry found in manifest files."
        )
    rel = matches[0]
    abs_path = root / rel
    if not abs_path.is_file():
        raise ManifestResolutionError(
            f"Integration '{agent}': manifest lists '{rel}' but file does not exist."
        )
    return abs_path


def _find_optional_prompt_file(
    root: Path, files: dict, agent: str, sep: str, role: str
) -> Path | None:
    """
    Best-effort variant of :func:`_find_prompt_file` for optional stages.

    Returns the resolved path when the manifest lists a matching
    ``speckit{sep}{role}`` entry (exact component/filename, never substring) and
    the file exists; returns None otherwise (no raise). Used for the specify and
    tasks prompts so partial Speckit layouts stay supported.
    """
    stem = f"speckit{sep}{role}"
    matches = [rel for rel in files if _matches_role(rel, stem)]
    if not matches:
        return None
    abs_path = root / matches[0]
    return abs_path if abs_path.is_file() else None


def derive_review_path(plan_path: Path, root: Path, sep: str) -> Path:
    """
    Derive the /specops.review installation path from the plan-prompt path.

    Pattern: replace ``speckit{sep}plan`` stem with ``specops{sep}review``
    in the path, preserving the wrapper convention (SKILL.md, etc.).
    """
    rel = plan_path.relative_to(root)
    new_rel = Path(str(rel).replace(f"speckit{sep}plan", f"specops{sep}review"))
    return root / new_rel


# ---------------------------------------------------------------------------
# Native extension surfaces (Feature 005)
# ---------------------------------------------------------------------------

def extensions_yml_path(root: Path) -> Path:
    """Return the path to the repository's native extension manifest.

    The file is SpecOps-authored and host-read; it may not exist yet.
    """
    return root / ".specify" / "extensions.yml"


def review_command_targets(root: Path) -> list[dict]:
    """
    Resolve the ``/specops-review`` command install path for every integration.

    Reuses :func:`resolve_prompt_targets` (which iterates
    ``installed_integrations`` and fails closed) and
    :func:`derive_review_path`. Returns a list of dicts:

      ``{"integration": str, "separator": str, "review_path": Path}``

    Raises :class:`ManifestResolutionError` (fail-closed) when integrations or
    their manifests cannot be resolved.
    """
    targets = resolve_prompt_targets(root)
    results: list[dict] = []
    for target in targets:
        sep = target["separator"]
        review_path = derive_review_path(target["plan_path"], root, sep)
        results.append(
            {
                "integration": target["integration"],
                "separator": sep,
                "review_path": review_path,
            }
        )
    return results


def host_prompt_paths(root: Path) -> list[Path]:
    """Return the resolved host prompt files across all installed integrations.

    Used by state detection to scan for legacy SpecOps marker blocks. Includes
    the mandatory plan/implement prompts plus optional specify/tasks prompts
    when present. Returns an empty list when integrations cannot be resolved
    (detection then reports no legacy signal rather than raising).
    """
    try:
        targets = resolve_prompt_targets(root)
    except ManifestResolutionError:
        return []
    paths: list[Path] = []
    for target in targets:
        for key in ("plan_path", "implement_path", "specify_path", "tasks_path"):
            p = target.get(key)
            if p is not None:
                paths.append(p)
    return paths
