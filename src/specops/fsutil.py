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

    Every ``{{key}}`` token in the template is replaced by ``mapping[key]``; extra
    mapping keys are ignored (additive templates never break older code). A
    ``{{...}}`` token whose key is absent from the mapping is template drift and
    raises :class:`SpecopsError` naming the unfilled placeholder(s) — a scaffold is
    never written with a silent unresolved placeholder.

    Substitution is a single left-to-right pass: a replacement *value* is inserted
    literally and never re-scanned, so a value that itself contains ``{{...}}``
    (e.g. a branch or feature name like ``fix/{{ts}}``) is neither re-substituted
    nor mistaken for template drift. Drift is judged on the template's own
    placeholders, not on the rendered output.
    """
    missing: set[str] = set()

    def _fill(match: re.Match[str]) -> str:
        token = match.group(0)
        key = token[2:-2]  # strip the surrounding ``{{`` / ``}}``
        if key in mapping:
            return mapping[key]
        missing.add(token)
        return token

    rendered = _PLACEHOLDER_RE.sub(_fill, text)
    if missing:
        raise SpecopsError(
            "Template rendering left unfilled placeholder(s): "
            + ", ".join(sorted(missing))
        )
    return rendered
