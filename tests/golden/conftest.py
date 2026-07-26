"""Golden-capture harness config (Feature 018).

The ``--golden-record`` option is declared in the tests-root ``tests/conftest.py``
so it survives a full ``pytest tests/`` run; this module only exposes it as a
fixture for the golden tests.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def golden_record(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--golden-record"))
