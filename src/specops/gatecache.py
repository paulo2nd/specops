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

import yaml

from specops import gitops
from specops.records import EvidenceRecord

CACHE_DIRNAME = "gate-cache"


def cache_path(repo: gitops.Repository, feature_dir: Path) -> Path:
    """The cache file for *feature_dir* inside *repo*'s git directory."""
    return gitops.git_dir(repo) / "specops" / CACHE_DIRNAME / f"{feature_dir.name}.yaml"


def load(repo: gitops.Repository, feature_dir: Path) -> list[EvidenceRecord]:
    """Return the cached gate-run records, or ``[]`` when the cache is absent/unreadable."""
    path = cache_path(repo, feature_dir)
    if not path.is_file():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return []
    return data if isinstance(data, list) else []


def persist(
    repo: gitops.Repository, feature_dir: Path, records: list[EvidenceRecord]
) -> None:
    """Atomically write *records* to the git-dir cache (creating parent dirs).

    Never touches the working tree. A ``.tmp`` sidecar is written then ``os.replace``d
    so a concurrent reader never sees a partial file."""
    path = cache_path(repo, feature_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(list(records), default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    os.replace(tmp, path)
