"""CLI ↔ native-extension version compatibility gate (FR-016).

The native extension registers hooks/commands that call the installed ``specops``
CLI at runtime. Install/migrate MUST verify the invoking CLI is present and new
enough to drive the manifest schema before writing anything (fail-closed, R7).
"""
from __future__ import annotations

import importlib.metadata
from dataclasses import dataclass

PACKAGE_NAME = "speckit-specops"

# The first CLI release that understands the native `.specify/extensions.yml`
# schema. Kept in sync with pyproject version floor (research R7).
MIN_CLI_VERSION = "0.3.0"


@dataclass(frozen=True)
class CompatResult:
    """Outcome of the CLI-compatibility check."""

    satisfied: bool
    installed: str | None
    required: str

    def reason(self) -> str:
        """Human-readable explanation for a failed check."""
        if self.installed is None:
            return (
                f"SpecOps CLI ('{PACKAGE_NAME}') is not installed; the native "
                f"extension requires >= {self.required}."
            )
        return (
            f"SpecOps CLI {self.installed} is older than the required "
            f">= {self.required} for the native extension."
        )


def installed_version() -> str | None:
    """Return the installed CLI version, or None when the package is absent."""
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        return None


def _parse(version: str) -> tuple[int, ...]:
    """Parse a dotted version into an int tuple, ignoring any pre-release suffix.

    ``"0.3.0"`` -> ``(0, 3, 0)``; ``"0.3.0.dev1"``/``"0.3.0rc1"`` -> ``(0, 3, 0)``.
    Non-numeric leading components degrade to 0 so a malformed version never
    crashes the gate (it simply compares low).
    """
    parts: list[int] = []
    for chunk in version.split("."):
        num = ""
        for ch in chunk:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts)


def _satisfies(installed: str, minimum: str) -> bool:
    a, b = _parse(installed), _parse(minimum)
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))  # pad so '0.3' == '0.3.0' (not "older")
    b += (0,) * (width - len(b))
    return a >= b


def check(minimum: str = MIN_CLI_VERSION) -> CompatResult:
    """Verify the installed CLI satisfies the ``minimum`` version floor."""
    installed = installed_version()
    if installed is None:
        return CompatResult(satisfied=False, installed=None, required=minimum)
    return CompatResult(
        satisfied=_satisfies(installed, minimum),
        installed=installed,
        required=minimum,
    )
