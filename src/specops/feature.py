"""Feature-identity operations: repointing and renaming (Feature 026).

The active feature is selected by `.specify/feature.json` and, at higher precedence,
Spec Kit's `SPECIFY_FEATURE_DIRECTORY` override (see :mod:`specops.speckit`). Neither
had a command that *writes* it, so starting or renumbering a feature meant hand-editing
the very files the ledger exists to make trustworthy — the contradiction this module
removes (#75).

Both commands record; neither validates intent. A repoint states what it moved and
what it left behind; a rename carries identity across the directory, the ledger, the
branch reference and the pointer without touching a single recorded fact.

Imports :mod:`specops.ledger` and :mod:`specops.speckit`, never :mod:`specops.status`
— the same one-way direction the rest of the package follows.
"""
from __future__ import annotations

__all__: list[str] = []
