"""Unit tests for the review round cap config read (Feature 025, FR-007)."""
from __future__ import annotations

from specops import config


def test_default_cap_is_ten() -> None:
    assert config.DEFAULT_REVIEW_ROUND_CAP == 10
    assert config.review_round_cap({}) == 10
    assert config._DEFAULTS["review_round_cap"] == 10


def test_configured_positive_int_respected() -> None:
    assert config.review_round_cap({"review_round_cap": 3}) == 3
    assert config.review_round_cap({"review_round_cap": 25}) == 25


def test_invalid_values_fall_back_to_default() -> None:
    for bad in (0, -1, -10, "5", 3.5, None, [], {}, True, False):
        assert config.review_round_cap({"review_round_cap": bad}) == 10
