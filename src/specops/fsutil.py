"""Shared filesystem primitives.

Single definition site (#25) for the durable temp-then-rename write that
`ledger`, `extension`, and `initializer` previously implemented independently
(or, in initializer's case, lacked entirely — a crash mid-`write_text` could
truncate a host-owned prompt file).
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from specops.errors import SpecopsError


def atomic_write(path: Path, content: str) -> None:
    """Write *content* (UTF-8) to *path* atomically and durably.

    Unique temp file in the target directory (same filesystem, so the rename is
    atomic) → write + flush + fsync through the same writable handle (Windows
    rejects fsync on a read-only one, #37) → ``os.replace`` → best-effort fsync
    of the containing directory (FR-022). An interrupted write leaves the
    previous file (if any) intact and never promotes a partial temp file; the
    temp file is removed on failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    try:
        dir_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass  # directory fsync is best-effort (not supported on all platforms)


_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}")


def render_template(text: str, mapping: dict[str, str]) -> str:
    """Render a ``{{key}}`` scaffold template, asserting placeholder completeness
    (Feature 019 US4, FR-010).

    Every mapping key replaces its ``{{key}}`` tokens; extra mapping keys are
    ignored (additive templates never break older code). Any ``{{...}}`` residue
    left after substitution is template drift and raises :class:`SpecopsError`
    naming the unfilled placeholder(s) — a scaffold is never written with silent
    residue. (No current template legitimately emits literal ``{{``.)
    """
    for key, value in mapping.items():
        text = text.replace("{{" + key + "}}", value)
    residue = sorted({m.group(0) for m in _PLACEHOLDER_RE.finditer(text)})
    if residue:
        raise SpecopsError(
            "Template rendering left unfilled placeholder(s): " + ", ".join(residue)
        )
    return text
