"""Stable CLI outcome contract (Feature 007, FR-021..FR-024).

The `specops` workflow composes native Spec Kit `gate`/`if`/`switch` steps that
branch on the *class* of a SpecOps gate's outcome. This module is the single
source of truth for that contract:

- **Exit codes** are unchanged from :mod:`specops.errors` — `0` ok, `1` a blocking
  gate result or review REJECTED, `2` an infrastructure / data / usage error — and
  documented here so they cannot drift.
- **`--json`** renders a stable object the workflow's conditions read, so a review
  REJECTED (corrective loop) and a reconcile divergence (fix env / rebaseline) are
  distinguishable even though both exit `1`.

A hard crash of an *integration* lifecycle command is out of scope for this
contract: it is a Spec Kit engine abort (execution failure) recovered via
`specify workflow resume`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, ClassVar

# --- Exit codes (mirror specops.errors) ------------------------------------
EXIT_OK = 0
EXIT_BLOCKED = 1  # blocking gate result / review REJECTED  (SpecopsError)
EXIT_ERROR = 2  # infrastructure / data / usage error       (LedgerParseError)

# --- Outcome status --------------------------------------------------------
OK = "ok"
BLOCKED = "blocked"
ERROR = "error"

# --- Outcome class (the workflow branches on this) -------------------------
PASS = "pass"
GATE_REJECTION = "gate-rejection"
INFRA_ERROR = "infra-error"

_STATUS_FOR_CLASS = {PASS: OK, GATE_REJECTION: BLOCKED, INFRA_ERROR: ERROR}
_EXIT_FOR_CLASS = {PASS: EXIT_OK, GATE_REJECTION: EXIT_BLOCKED, INFRA_ERROR: EXIT_ERROR}


@dataclass
class CommandResult:
    """A rendered-agnostic command outcome consumed by the CLI layer.

    The shared base for every ``specops`` command result. A subclass sets the
    ``_CLASS_MAP`` ClassVar to map its module-local statuses to an outcome class; the
    ``cls``/``exit_code`` derivation then lives in exactly one place.
    """

    command: str
    status: str
    human: str
    extra: dict[str, Any] = field(default_factory=dict)

    _CLASS_MAP: ClassVar[dict[str, str]] = {}

    @property
    def cls(self) -> str:
        return self._CLASS_MAP[self.status]

    @property
    def exit_code(self) -> int:
        return exit_for(self.cls)


def status_for(cls: str) -> str:
    """Return the outcome status (`ok`/`blocked`/`error`) for an outcome class."""
    return _STATUS_FOR_CLASS[cls]


def exit_for(cls: str) -> int:
    """Return the exit code (`0`/`1`/`2`) for an outcome class (Principle VI)."""
    return _EXIT_FOR_CLASS[cls]


def render(command: str, cls: str, **extra: Any) -> str:
    """Render the stable outcome JSON for *command* with outcome *cls*.

    `outcome` and `class` are always present and consistent (G1). Optional keys
    (`verdict`, `diverged_dimension`, `gates`, `remedy`) are included only when a
    non-None value is supplied.
    """
    obj: dict[str, Any] = {
        "command": command,
        "outcome": status_for(cls),
        "class": cls,
    }
    for key, value in extra.items():
        if value is not None:
            obj[key] = value
    return json.dumps(obj)
