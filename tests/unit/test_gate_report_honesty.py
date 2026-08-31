"""A cached gate result must not read as a fresh verdict (#73).

`PASS` is a claim about the code; a cached entry is only a claim about the cache.
The two were rendered identically, and the machine surface already told them apart
(`disposition`) while the human surface did not — so an operator (or an agent) had
no cue that a suite taking ~9 minutes had returned in 1.2s without running.

These tests pin the human rendering. The `status` field and the exit codes are
deliberately unchanged: a cached pass IS a pass (identical tree, recorded run), and
both are frozen surfaces (docs/stability.md).
"""
from __future__ import annotations

from specops.review import GateReport, GateResult, _elapsed_suffix


def _gate(name: str, **kw: object) -> GateResult:
    return GateResult(name, kw.pop("status", "PASS"), **kw)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Elapsed formatting
# ---------------------------------------------------------------------------

def test_elapsed_suffix_scales_with_magnitude() -> None:
    assert _elapsed_suffix(None) == ""
    assert _elapsed_suffix(240) == " (240ms)"
    assert _elapsed_suffix(1200) == " (1.2s)"
    assert _elapsed_suffix(552_000) == " (9m 12s)"


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_cached_gate_does_not_render_as_pass() -> None:
    """The whole bug in one assertion: the cheap claim must look different."""
    report = GateReport([_gate("test", disposition="cached")])
    line = report.render().splitlines()[0]
    assert "CACHED" in line
    assert "PASS" not in line


def test_executed_gate_renders_pass_with_its_wall_clock() -> None:
    report = GateReport([_gate("test", disposition="required", duration_ms=552_000)])
    line = report.render().splitlines()[0]
    assert "PASS" in line
    assert "(9m 12s)" in line


def test_cached_and_executed_are_distinguishable_at_a_glance() -> None:
    """A real run and a cached run, back to back on an unchanged tree, were
    indistinguishable from the output — only wall clock separated them."""
    report = GateReport([
        _gate("lint", disposition="cached"),
        _gate("test", disposition="required", duration_ms=1200),
    ])
    lint, test = report.render().splitlines()[:2]
    assert lint != test
    assert "CACHED" in lint and "(" not in lint.split("CACHED")[1]
    assert "PASS (1.2s)" in test


def test_failed_gate_keeps_fail_and_reports_how_long_it_took() -> None:
    report = GateReport([
        _gate("test", status="FAIL", disposition="failed", duration_ms=8_000)
    ])
    line = report.render().splitlines()[0]
    assert "FAIL" in line and "(8.0s)" in line


def test_skipped_gate_is_unchanged() -> None:
    report = GateReport([_gate("lint", status="SKIPPED", detail=["out of scope"])])
    assert "SKIPPED (out of scope)" in report.render()


# ---------------------------------------------------------------------------
# Summary line
# ---------------------------------------------------------------------------

def test_summary_states_executed_versus_reused() -> None:
    report = GateReport([
        _gate("a", disposition="cached"),
        _gate("b", disposition="cached"),
        _gate("c", disposition="required", duration_ms=60_000),
        _gate("d", status="SKIPPED", detail=["out of scope"]),
    ])
    summary = report.summary()
    assert "4 total" in summary
    assert "1 executed (1m 0s)" in summary
    assert "2 reused from cache" in summary
    assert "1 skipped" in summary


def test_summary_makes_a_fully_cached_suite_obvious() -> None:
    """The five-green-lines case that read as a full suite run for six sessions."""
    report = GateReport([_gate(f"g{i}", disposition="cached") for i in range(5)])
    summary = report.summary()
    assert "0 executed" in summary
    assert "5 reused from cache" in summary


def test_summary_is_appended_to_the_report() -> None:
    report = GateReport([_gate("test", disposition="required", duration_ms=10)])
    assert report.render().splitlines()[-1].startswith("[gates] ")


# ---------------------------------------------------------------------------
# The machine surface is deliberately untouched
# ---------------------------------------------------------------------------

def test_cached_status_field_stays_pass() -> None:
    """`status` and the exit codes are frozen (docs/stability.md), and a cached pass
    IS a pass — identical tree, recorded run. Only the human wording changes."""
    result = _gate("test", disposition="cached")
    assert result.status == "PASS"
    assert GateReport([result]).passed is True
