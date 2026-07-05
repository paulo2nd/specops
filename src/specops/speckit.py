"""Speckit layout detection, feature-dir resolution, and structural token parsing (R1, R2, R5, R6)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

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


def resolve_feature_dir(root: Path) -> Optional[Path]:
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

    # Fallback: newest specs/NNN-* directory
    specs_dir = root / "specs"
    if specs_dir.is_dir():
        candidates = sorted(
            [d for d in specs_dir.iterdir() if d.is_dir() and re.match(r"\d+", d.name)],
            key=lambda d: d.name,
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


# ---------------------------------------------------------------------------
# Manifest-driven prompt-target resolution (R2)
# ---------------------------------------------------------------------------

class ManifestResolutionError(Exception):
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
      }

    Raises ManifestResolutionError (fail-closed, R2) when:
    - integration.json is missing
    - an integration lacks a manifest
    - a manifest lacks plan/implement entries
    - a listed file is absent on disk
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
        results.append(
            {
                "integration": agent,
                "separator": sep,
                "plan_path": plan_path,
                "implement_path": impl_path,
            }
        )

    return results


def _find_prompt_file(root: Path, files: dict, agent: str, sep: str, role: str) -> Path:
    """
    Locate the prompt file for *role* ('plan' or 'implement') inside *files*.

    Matches entries whose path contains the ``speckit{sep}{role}`` stem
    (handles SKILL.md wrappers, .prompt.md variants, etc.).
    """
    stem = f"speckit{sep}{role}"
    matches = [rel for rel in files if stem in rel]
    if not matches:
        raise ManifestResolutionError(
            f"Integration '{agent}': no '{stem}' entry found in manifest files."
        )
    if len(matches) > 1:
        # prefer exact stem match to avoid ambiguity
        exact = [m for m in matches if Path(m).stem == stem or stem in Path(m).parts]
        matches = exact if exact else matches

    rel = matches[0]
    abs_path = root / rel
    if not abs_path.is_file():
        raise ManifestResolutionError(
            f"Integration '{agent}': manifest lists '{rel}' but file does not exist."
        )
    return abs_path


def derive_review_path(plan_path: Path, root: Path, sep: str) -> Path:
    """
    Derive the /specops.review installation path from the plan-prompt path.

    Pattern: replace ``speckit{sep}plan`` stem with ``specops{sep}review``
    in the path, preserving the wrapper convention (SKILL.md, etc.).
    """
    rel = plan_path.relative_to(root)
    new_rel = Path(str(rel).replace(f"speckit{sep}plan", f"specops{sep}review"))
    return root / new_rel
