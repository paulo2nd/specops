"""Golden-capture harness for Feature 018 (behavior freeze — research.md D8).

The consolidation of Feature 008–013's command-result, emit, ledger-loading, and
grammar code must be **byte-identical** in CLI output (contracts/cli-output.md),
with exactly one sanctioned delta (lane ``--json`` gaining ``output_version`` +
``status``) and two enumerated invalid-input convergences.

Existing assertion tests sample *fields*; they cannot prove the full byte stream
is unchanged — which is precisely how the lane envelope divergence survived. This
harness records the full ``(stdout, stderr, exit_code)`` triple for a
representative scenario per command family, in human and ``--json`` modes, against
fixture repos only (never this repository — No Self-Application).

Volatile tokens (the fixture's absolute path, git SHAs, timestamps, content
digests, the package version) are scrubbed to stable placeholders so a capture
recorded in one process replays deterministically in another.
"""
from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from specops import contextmap, gateprofiles, ledger
from tests.conftest import git, make_cycle, make_finding, make_task, make_trace_ledger

CAPTURES_DIR = Path(__file__).parent / "captures"


# ---------------------------------------------------------------------------
# Scrubbing volatile tokens
# ---------------------------------------------------------------------------

_ANSI = re.compile(r"\x1b\[[0-9;]*m")
_ISO_TS = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?"
)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_HEX = re.compile(r"\b[0-9a-f]{7,}\b")
_VER = re.compile(r"\b\d+\.\d+\.\d+(?:[.-][0-9A-Za-z.]+)?\b")


def scrub(text: str, root: Path) -> str:
    """Replace fixture-run-specific tokens with stable placeholders.

    Order matters: the fixture's absolute path is a literal substring that may
    itself contain hex (macOS ``/private/tmp/...`` scratch dirs use hex ids), so it
    is removed first; timestamps before bare dates; version triples before hex so a
    ``1.2.3`` is not partially eaten.
    """
    text = _ANSI.sub("", text)  # defence-in-depth: never let stray colour cause drift
    # Normalise both the real and symlink-resolved forms of the fixture path.
    for base in {str(root), str(root.resolve())}:
        text = text.replace(base, "<ROOT>")
    text = _ISO_TS.sub("<TS>", text)
    text = _VER.sub("<VER>", text)
    text = _DATE.sub("<DATE>", text)
    text = _HEX.sub("<HEX>", text)
    return text


# ---------------------------------------------------------------------------
# Scenario model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Scenario:
    """One captured command invocation against a freshly-built fixture repo."""

    family: str
    name: str
    args: tuple[str, ...]
    build: Callable[[Path], None]
    setup: tuple[tuple[str, ...], ...] = field(default=())

    @property
    def key(self) -> str:
        return f"{self.family}/{self.name}"

    @property
    def capture_path(self) -> Path:
        return CAPTURES_DIR / self.family / f"{self.name}.txt"


def run_specops(root: Path, args: tuple[str, ...]) -> subprocess.CompletedProcess:
    """Invoke the installed ``specops`` binary in *root* (real streams/exit code).

    The environment is normalised so a capture recorded on one host replays byte-for-byte
    on another: UTF-8 I/O, and Rich/Click colour + terminal width pinned off/fixed so a
    Typer error panel (or any styled output) renders identically in CI and locally.
    """
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    env["COLUMNS"] = "80"
    env.pop("FORCE_COLOR", None)
    return subprocess.run(
        ["specops", *args], cwd=root, capture_output=True, text=True, env=env
    )


def capture(scenario: Scenario, root: Path) -> str:
    """Build the fixture, run any setup commands, then capture the scrubbed triple."""
    scenario.build(root)
    for pre in scenario.setup:
        run_specops(root, pre)
    proc = run_specops(root, scenario.args)
    body = (
        f"$ specops {' '.join(scenario.args)}\n"
        f"--- exit_code ---\n{proc.returncode}\n"
        f"--- stdout ---\n{scrub(proc.stdout, root)}\n"
        f"--- stderr ---\n{scrub(proc.stderr, root)}\n"
    )
    return body


# ---------------------------------------------------------------------------
# Fixture builders (fresh repos; module-level helpers reused from tests.conftest)
# ---------------------------------------------------------------------------


def init_repo(root: Path) -> None:
    """Initialise a git repo with a deterministic identity and one commit."""
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test")
    git(root, "checkout", "-b", "main")
    (root / "README.md").write_text("# fixture\n")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "initial")


def _feature(root: Path, name: str = "001-demo") -> Path:
    (root / ".specify" / "templates").mkdir(parents=True, exist_ok=True)
    import json

    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": f"specs/{name}"})
    )
    fd = root / "specs" / name
    fd.mkdir(parents=True, exist_ok=True)
    return fd


# --- context ---------------------------------------------------------------

_VALID_MAP = {
    "schema_version": 1,
    "contexts": [
        {"id": "api", "match": ["src/api/**"],
         "reads": {"base": ["src/api"], "plan": ["docs/api.md", "src/api"]},
         "dependencies": ["config"], "gates": ["contract-tests"], "risk": {"tier": "high"}},
        {"id": "config", "match": ["src/config/**"], "reads": {"base": ["src/config"]}},
    ],
}


def _write_map(root: Path, data: object) -> None:
    (root / ".specify" / "specops").mkdir(parents=True, exist_ok=True)
    p = contextmap.map_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = data if isinstance(data, str) else yaml.dump(data)
    p.write_text(text, encoding="utf-8")


def build_context_valid(root: Path) -> None:
    _feature(root)
    _write_map(root, _VALID_MAP)


def build_context_invalid(root: Path) -> None:
    _feature(root)
    # Duplicate id + unknown dependency → multiple diagnostics in one pass.
    _write_map(root, {
        "schema_version": 1,
        "contexts": [
            {"id": "api", "match": ["src/api/**"], "reads": {"base": ["src/api"]},
             "dependencies": ["ghost"]},
            {"id": "api", "match": ["src/api2/**"], "reads": {"base": ["src/api2"]}},
        ],
    })


def build_context_empty(root: Path) -> None:
    """A repo with the layout but no map — `context init` creates one."""
    _feature(root)
    (root / ".specify" / "specops").mkdir(parents=True, exist_ok=True)


# --- trace -----------------------------------------------------------------


def _trace_build(root: Path, *, plan_paths=(), spec_scs=("SC-001",), tasks_md_tasks=(),
                 tasks=None, review_cycles=None, acks=None, changed=None) -> None:
    fd = _feature(root)
    spec = "\n".join(f"- **{sc}**: measurable outcome." for sc in spec_scs)
    (fd / "spec.md").write_text("# Spec\n\n## Success Criteria\n\n" + spec + "\n")
    (fd / "plan.md").write_text(
        "# Plan\n\n" + "\n".join(f"- `{p}` (create)" for p in plan_paths) + "\n")
    (fd / "tasks.md").write_text("# Tasks\n\n" + "\n".join(tasks_md_tasks) + "\n")
    git(root, "add", "-A")
    git(root, "commit", "-m", "scaffolding")
    baseline = git(root, "rev-parse", "HEAD")
    led = make_trace_ledger(
        feature="001-demo", branch="main", baseline=baseline,
        tasks=tasks, review_cycles=review_cycles, acknowledgements=acks,
    )
    (fd / "status.yaml").write_text(yaml.dump(led))
    for path, content in (changed or {}).items():
        fp = root / path
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
    if changed:
        git(root, "add", "-A")
        git(root, "commit", "-m", "work")


def build_trace_classify(root: Path) -> None:
    _trace_build(root, plan_paths=["src/planned.py"],
                 changed={"src/planned.py": "x\n", "src/surprise.py": "y\n"})


def build_trace_validate(root: Path) -> None:
    _trace_build(root, plan_paths=[], changed={"src/surprise.py": "y\n"})


def build_trace_report(root: Path) -> None:
    _trace_build(root, spec_scs=["SC-001"], plan_paths=[],
                 tasks_md_tasks=["- [ ] T001 [US1] do it [SC-001]"],
                 tasks=[make_task("T001", commits=["a" * 40])])


# --- handoff ---------------------------------------------------------------


def _handoff_build(root: Path, *, tasks=None, review_cycles=None, phase="REVIEW",
                   spec_scs=("SC-001",)) -> None:
    fd = _feature(root)
    (fd / "spec.md").write_text(
        "# Spec\n\n## Success Criteria\n\n"
        + "\n".join(f"- **{sc}**: measurable." for sc in spec_scs) + "\n")
    (fd / "plan.md").write_text("# Plan\n")
    (fd / "tasks.md").write_text("# Tasks\n")
    git(root, "add", "-A")
    git(root, "commit", "-m", "scaffolding")
    baseline = git(root, "rev-parse", "HEAD")
    led = make_trace_ledger(
        feature="001-demo", branch="main", baseline=baseline, tasks=tasks,
        review_cycles=review_cycles if review_cycles is not None else [make_cycle()],
        phase=phase,
    )
    led["schema_version"] = ledger.CURRENT_SCHEMA
    (fd / "status.yaml").write_text(yaml.dump(led))


def build_handoff_report_clean(root: Path) -> None:
    _handoff_build(root, review_cycles=[make_cycle(findings=[
        make_finding("R1-F01", severity="advisory", state="OPEN"),
    ])])


def build_handoff_validate_blocked(root: Path) -> None:
    _handoff_build(root, review_cycles=[make_cycle(findings=[
        make_finding("R1-F01", severity="blocking", state="OPEN"),
    ])])


# --- gate ------------------------------------------------------------------


def _gate_build(root: Path) -> None:
    fd = _feature(root)
    (root / ".specify" / "specops").mkdir(parents=True, exist_ok=True)
    gateprofiles.profiles_path(root).write_text(
        "output_version: 1\n"
        "profiles:\n"
        "  - name: smoke\n"
        "    command: git --version\n"
        "    applies: {always: true}\n"
        "    timeout: 60\n"
    )
    (fd / "spec.md").write_text("# Spec\n")
    git(root, "add", "-A")
    git(root, "commit", "-m", "scaffold")
    baseline = git(root, "rev-parse", "HEAD")
    led = make_trace_ledger(feature="001-demo", branch="main", baseline=baseline,
                            phase="IMPLEMENT")
    led["schema_version"] = ledger.CURRENT_SCHEMA
    (fd / "status.yaml").write_text(yaml.dump(led))


def build_gate(root: Path) -> None:
    _gate_build(root)


# --- lane (THE sanctioned-delta family) ------------------------------------


def _lane_build(root: Path) -> None:
    import json

    (root / ".specify").mkdir(exist_ok=True)
    (root / ".specify" / "feature.json").write_text(
        json.dumps({"feature_directory": "specs/013-lane"})
    )
    (root / "specs" / "013-lane").mkdir(parents=True)
    (root / "specops.json").write_text(
        json.dumps({"test_command": "true", "lint_command": ""})
    )


LANE_ELIGIBLE = ("--answers", "small,reversible,no-high-risk-category")


def build_lane(root: Path) -> None:
    _lane_build(root)


# --- report / status / reconcile (doctor + ledger convergence) -------------


def _report_build(root: Path) -> None:
    import json

    (root / ".specify" / "templates").mkdir(parents=True)
    (root / ".specify" / "integrations").mkdir(parents=True)
    (root / ".specify" / "integration.json").write_text(
        json.dumps({"installed_integrations": ["claude"],
                    "integration_settings": {"claude": {"invoke_separator": "-"}}})
    )
    fd = _feature(root)
    (fd / "spec.md").write_text("# Spec\n")
    git(root, "add", "-A")
    git(root, "commit", "-m", "scaffold")
    baseline = git(root, "rev-parse", "HEAD")
    led = make_trace_ledger(feature="001-demo", branch="main", baseline=baseline,
                            phase="IMPLEMENT",
                            tasks=[make_task("T001", status="DONE")])
    led["schema_version"] = ledger.CURRENT_SCHEMA
    (fd / "status.yaml").write_text(yaml.dump(led))


def build_report(root: Path) -> None:
    _report_build(root)


def build_status_show(root: Path) -> None:
    _report_build(root)


def build_reconcile(root: Path) -> None:
    _report_build(root)


def _corrupt_build(root: Path) -> None:
    """A feature repo whose ledger is unparsable YAML (invalid-input convergence)."""
    _report_build(root)
    (root / "specs" / "001-demo" / "status.yaml").write_text(":\n  - [broken")


def build_status_show_corrupt(root: Path) -> None:
    _corrupt_build(root)


def build_report_corrupt(root: Path) -> None:
    _corrupt_build(root)


def build_reconcile_corrupt(root: Path) -> None:
    _corrupt_build(root)


# ---------------------------------------------------------------------------
# The scenario registry
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [
    # context (Feature 008)
    Scenario("context", "init_human", ("context", "init"), build_context_empty),
    Scenario("context", "validate_human", ("context", "validate"), build_context_valid),
    Scenario("context", "validate_json", ("context", "validate", "--json"), build_context_valid),
    Scenario("context", "validate_invalid_human", ("context", "validate"), build_context_invalid),
    Scenario("context", "validate_invalid_json",
             ("context", "validate", "--json"), build_context_invalid),
    Scenario("context", "resolve_json",
             ("context", "resolve", "--path", "src/api/x.py", "--json"), build_context_valid),
    # trace (Feature 010)
    Scenario("trace", "classify_human", ("trace", "classify"), build_trace_classify),
    Scenario("trace", "classify_json", ("trace", "classify", "--json"), build_trace_classify),
    Scenario("trace", "validate_human", ("trace", "validate"), build_trace_validate),
    Scenario("trace", "validate_json", ("trace", "validate", "--json"), build_trace_validate),
    Scenario("trace", "report_json", ("trace", "report", "--json"), build_trace_report),
    # handoff (Feature 011)
    Scenario("handoff", "report_human", ("handoff", "report"), build_handoff_report_clean),
    Scenario("handoff", "report_json", ("handoff", "report", "--json"), build_handoff_report_clean),
    Scenario("handoff", "validate_human",
             ("handoff", "validate"), build_handoff_validate_blocked),
    Scenario("handoff", "validate_json",
             ("handoff", "validate", "--json"), build_handoff_validate_blocked),
    # gate (Feature 012)
    Scenario("gate", "list_human", ("gate", "list"), build_gate),
    Scenario("gate", "list_json", ("gate", "list", "--json"), build_gate),
    Scenario("gate", "validate_json", ("gate", "validate", "--json"), build_gate),
    # lane (Feature 013) — the sanctioned-delta family
    Scenario("lane", "start_human", ("lane", "start", *LANE_ELIGIBLE), build_lane),
    Scenario("lane", "start_json", ("lane", "start", *LANE_ELIGIBLE, "--json"), build_lane),
    Scenario("lane", "status_json", ("lane", "status", "--json"), build_lane,
             setup=(("lane", "start", *LANE_ELIGIBLE),)),
    Scenario("lane", "check_json", ("lane", "check", "--json"), build_lane,
             setup=(("lane", "start", *LANE_ELIGIBLE),)),
    # report / status / reconcile (Feature 014 + ledger convergence)
    Scenario("report", "report_human", ("report",), build_report),
    Scenario("report", "report_json", ("report", "--json"), build_report),
    Scenario("status", "show_human", ("status", "show"), build_status_show),
    Scenario("reconcile", "reconcile_json", ("reconcile", "--json"), build_reconcile),
    # invalid-input convergences (D4) — re-recorded at T027 when they converge
    Scenario("status", "show_corrupt_human", ("status", "show"), build_status_show_corrupt),
    Scenario("report", "report_corrupt_json", ("report", "--json"), build_report_corrupt),
    Scenario("reconcile", "reconcile_corrupt_human", ("reconcile",), build_reconcile_corrupt),
]
