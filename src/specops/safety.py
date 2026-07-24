"""specops safety-core: hybrid detection for the lightweight lane (Feature 013).

Four categories are DETECTED deterministically from the effective diff by generic,
domain-agnostic path/pattern heuristics. Two categories — ``root-cause`` and
``public-contract`` — are *not* generically diff-detectable (a semantic judgment, and
a language-specific public API surface); they are enforced by always-on human
attestation in :mod:`specops.lane`, not here (analysis C1).

The built-in default patterns are a **non-removable floor**: ``specops.json`` overrides
(``lane.safety.<category>``) only *add* globs, they never remove the floor, so a repo
cannot silently disable the safety core by omitting or trimming config (Design
Philosophy — minimal non-pierceable core; Principle V — generic + configurable).
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass

# --- Detected categories (this module) -------------------------------------
MIGRATION = "migration"
SECRET = "secret"
DEPENDENCY = "dependency"
DESTRUCTIVE = "destructive"
DETECTED_CATEGORIES = (MIGRATION, SECRET, DEPENDENCY, DESTRUCTIVE)

# --- Attested categories (enforced in specops.lane, never detected here) ----
ROOT_CAUSE = "root-cause"
PUBLIC_CONTRACT = "public-contract"
ATTESTED_CATEGORIES = (ROOT_CAUSE, PUBLIC_CONTRACT)

# Generic, stack-agnostic default signals — the non-removable floor (research R5).
_DEFAULT_PATTERNS: dict[str, list[str]] = {
    MIGRATION: [
        "*/migrations/*", "migrations/*", "*.sql", "*/alembic/*", "alembic/*",
        "*/migrate/*", "*schema.rb", "*schema.prisma",
    ],
    SECRET: [
        ".env", ".env.*", "*.env", "*.env.*", "*secret*", "*secrets*",
        "*.pem", "*.key", "*id_rsa*", "*.p12", "*.pfx", "*credentials*",
    ],
    DEPENDENCY: [
        "requirements*.txt", "pyproject.toml", "Pipfile", "Pipfile.lock",
        "poetry.lock", "package.json", "package-lock.json", "yarn.lock",
        "pnpm-lock.yaml", "go.mod", "go.sum", "Cargo.toml", "Cargo.lock",
        "Gemfile", "Gemfile.lock", "*.gemspec", "composer.json", "composer.lock",
        "*.csproj", "*.lock",
    ],
}

# Categories whose default patterns can be augmented via config overrides.
_PATTERN_CATEGORIES = (MIGRATION, SECRET, DEPENDENCY)


@dataclass(frozen=True)
class Detection:
    """One flagged path in a diff-detectable category."""

    category: str
    path: str
    status: str  # git single-letter status (A|M|D|…)


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _matches(path: str, patterns: list[str]) -> bool:
    base = _basename(path)
    return any(fnmatch.fnmatch(path, p) or fnmatch.fnmatch(base, p) for p in patterns)


def _patterns_for(category: str, overrides: dict[str, list[str]] | None) -> list[str]:
    """Return the non-removable floor for *category* plus any override additions."""
    floor = list(_DEFAULT_PATTERNS.get(category, ()))
    extra = list((overrides or {}).get(category, ()) or ())
    return floor + extra


def detect(
    diff_status: list[tuple[str, str]],
    overrides: dict[str, list[str]] | None = None,
) -> list[Detection]:
    """Return the flagged detections for an effective diff.

    *diff_status* is a list of ``(status, path)`` pairs (as from
    :func:`specops.gitops.effective_diff_status`). *overrides* maps a detectable
    category to *additional* globs (never fewer than the floor). Detection is a pure
    function of its inputs — no I/O — so it is deterministic and unit-testable.

    ``destructive`` is flagged on any deletion (git status ``D``): a file removal is
    less trivially reversible, so the lane fails closed and asks a human.
    """
    detections: list[Detection] = []
    seen: set[tuple[str, str]] = set()
    for status, path in diff_status:
        for category in _PATTERN_CATEGORIES:
            if _matches(path, _patterns_for(category, overrides)):
                key = (category, path)
                if key not in seen:
                    seen.add(key)
                    detections.append(Detection(category, path, status))
        if status == "D":
            key = (DESTRUCTIVE, path)
            if key not in seen:
                seen.add(key)
                detections.append(Detection(DESTRUCTIVE, path, status))
    return detections


def categories(detections: list[Detection]) -> list[str]:
    """Return the deduplicated, deterministically ordered set of flagged categories."""
    present = {d.category for d in detections}
    return [c for c in DETECTED_CATEGORIES if c in present]
