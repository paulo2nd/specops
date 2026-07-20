"""SpecOps error hierarchy (contracts/errors.md)."""
from __future__ import annotations


class SpecopsError(Exception):
    """Blocking failure (precondition, validation, gate). Exit code 1."""

    exit_code: int = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class LedgerParseError(SpecopsError):
    """Unexpected/parse error (corrupt ledger YAML, invalid structure). Exit code 2."""

    exit_code: int = 2


class StaleLedgerError(SpecopsError):
    """A write was attempted against a ledger revision that has since advanced.

    Signals a lost-update conflict (Ledger v2, FR-013/FR-015): the caller must
    re-read the current ledger and retry. Exit code 1 (blocking, recoverable).
    """

    exit_code: int = 1
