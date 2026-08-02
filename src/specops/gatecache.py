"""Ephemeral gate-run cache (Feature 024).

The deterministic gate suite (``specops preflight``) records a **passing** command-gate
run so an identical later run can reuse it instead of re-executing (the terminal gate
reusing the soft gate's result). Unlike task evidence, a gate run is ephemeral,
tree-scoped, reproducible local state — not durable cross-clone audit history — so it is
stored **outside the working tree**, inside the git directory:

    <git-dir>/specops/gate-cache/<feature>.yaml

Living in ``.git`` means the cache never appears in ``git status``/``git diff``, never
dirties the working tree (so the ``working-tree`` gate is unaffected), never perturbs the
:func:`specops.gitops.worktree_digest` it is keyed by, and is invisible to the tests'
``snapshot_tree`` — keeping ``preflight`` byte-for-byte read-only on the committed repo
(Principle IV holds unchanged). A cold or deleted cache is harmless: the gate simply
re-executes. Records are :class:`specops.records.EvidenceRecord` dicts; supersession and
id derivation are handled by :mod:`specops.evidence` — this module only (de)serializes the
list.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import cast

import yaml

from specops import gitops
from specops.errors import SpecopsError
from specops.records import EvidenceRecord

CACHE_DIRNAME = "gate-cache"

# Bound the ephemeral cache so a long-lived feature with many edit/preflight cycles
# does not accumulate one record per distinct tree state forever. Each retained record
# is one (gate × tree-state) pass; the most recent are kept. Eviction only costs a
# re-run of an old state — never correctness.
MAX_RECORDS = 64


def cache_path(repo: gitops.Repository, feature_dir: Path) -> Path:
    """The cache file for *feature_dir* inside *repo*'s git directory."""
    return gitops.git_dir(repo) / "specops" / CACHE_DIRNAME / f"{feature_dir.name}.yaml"


def load(repo: gitops.Repository, feature_dir: Path) -> list[EvidenceRecord]:
    """Return the cached gate-run records, or ``[]`` when the cache is absent/unreadable.

    Only mapping elements are returned — a malformed cache (scalars, partial write, hand
    edit) degrades to a cold cache (re-run) rather than crashing a later write-back."""
    try:
        path = cache_path(repo, feature_dir)
        if not path.is_file():
            return []
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, SpecopsError):
        return []
    if not isinstance(data, list):
        return []
    return [cast(EvidenceRecord, r) for r in data if isinstance(r, dict)]


def persist(
    repo: gitops.Repository, feature_dir: Path, records: list[EvidenceRecord]
) -> None:
    """Best-effort atomic write of *records* to the git-dir cache (creating parent dirs).

    Never touches the working tree; keeps only the most recent :data:`MAX_RECORDS`. Any
    I/O failure (read-only ``.git``, full disk, missing permission) is swallowed — the
    gates already ran and passed, so a failed cache write must never turn success into a
    crash (the cache is a pure optimization; the next run simply re-executes)."""
    try:
        path = cache_path(repo, feature_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            yaml.safe_dump(
                list(records)[-MAX_RECORDS:], default_flow_style=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
        os.replace(tmp, path)
    except (OSError, SpecopsError):
        return
