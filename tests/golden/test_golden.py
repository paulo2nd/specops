"""Golden replay: every command family's output is byte-frozen (SC-001, SC-006).

Default mode diffs the live capture against the committed golden file and fails on
any difference. ``pytest tests/golden --golden-record`` (re)writes the golden files
— used on the baseline commit (T005) and, scoped, when a sanctioned delta lands
(lane envelope at T011; the two invalid-input convergences at T027).

Runs exclusively against fixture repos built under ``tmp_path`` — never against this
repository (No Self-Application).
"""
from __future__ import annotations

import pytest

from tests.golden.harness import SCENARIOS, Scenario, capture


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.key)
def test_golden(scenario: Scenario, tmp_path, golden_record: bool) -> None:
    from tests.golden.harness import init_repo

    root = tmp_path / "repo"
    root.mkdir()
    init_repo(root)
    actual = capture(scenario, root)

    path = scenario.capture_path
    if golden_record:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        pytest.skip(f"recorded {scenario.key}")

    assert path.is_file(), (
        f"no golden capture for {scenario.key}; run "
        f"`pytest tests/golden --golden-record` on the baseline first"
    )
    expected = path.read_text(encoding="utf-8")
    assert actual == expected, (
        f"golden drift for {scenario.key}:\n--- expected ---\n{expected}\n"
        f"--- actual ---\n{actual}"
    )
