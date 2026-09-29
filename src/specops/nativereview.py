"""Native code review per integration (Feature 028).

Holds the built-in map from a Spec Kit integration id to that tool's native
code-review command, and renders the ``/specops-review`` Step 3a paragraph for one
integration. Both install paths (``specops init`` and ``specops extension
install|update|enable``) call :func:`render_review`, so the review command is
sourced identically on each (Principle IV).

The map only lists reviewers that are built in, invocable by the agent itself
mid-session, and targetable to the round's ``reviewed_range`` — see
``specs/028-native-code-review/research.md`` R1 for the per-integration evidence.
Adding an entry means updating that research and ``tests/unit/test_nativereview.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from specops import fsutil

_TEMPLATE = Path(__file__).parent / "templates" / "review.md"


@dataclass(frozen=True)
class Entry:
    """One integration's native reviewer (data-model Entity 1)."""

    command: str
    mechanism: str
    invocation: str  # the exact call; ``{effort}`` is filled at render time
    efforts: tuple[str, ...]
    default_effort: str
    caution: str = ""


BUILTIN: dict[str, Entry] = {
    "claude": Entry(
        command="/code-review",
        mechanism="the Skill tool",
        invocation='Skill(skill: "code-review", args: "{effort} <from>...<head>")',
        # ``ultra`` is a user-launched, separately billed cloud review (research R2).
        efforts=("low", "medium", "high", "xhigh", "max"),
        default_effort="high",
        caution=(
            "Always pass the level explicitly (with no level, `/code-review` reuses the "
            "last level the user typed), and never pass `ultra`, `--fix`, `--comment` "
            "or `--post`."
        ),
    ),
}

_LEGACY = (
    "If your environment provides a native code-review capability (e.g. the "
    "`/code-review` skill in Claude Code, or an equivalent review command in your "
    "integration), **invoke it scoped to the effective diff** and carry its confirmed "
    "findings into Step 4. The native reviewer complements your own pass — it never "
    "replaces it, and it never records the verdict: every finding you accept must "
    "become a structured finding (Step 4). Findings emitted as JSON/SARIF by an "
    "external tool can be imported wholesale with `specops handoff finding "
    "import-json` / `import-sarif` instead of re-entered by hand. If no native "
    "capability exists, perform the code review yourself directly on the diff."
)

_FINDINGS = (
    "Carry every confirmed finding into Step 4 as a structured finding: record defects "
    "that gate approval individually with `specops handoff finding add --severity "
    "blocking …`; JSON/SARIF output may be bulk-imported with `specops handoff finding "
    "import-json` / `import-sarif` (imported findings are always advisory). The native "
    "reviewer complements your own review pass — it never replaces it, and it never "
    "records the verdict."
)


def _required(command: str, invoke: str, subagent: str) -> str:
    """The mandatory-native paragraph shared by built-in and overridden reviewers."""
    return (
        f"**Native code review (mandatory).** {invoke} Wait for its report before "
        "continuing.\n\n"
        f"If you delegate this review to a subagent, that subagent must {subagent}. A "
        "subagent without it cannot run the native reviewer — that run counts as "
        "**native review not run**; never substitute a manual pass silently.\n\n"
        f"{_FINDINGS}\n\n"
        "If the native reviewer did not run — the invocation mechanism was unavailable, "
        "the invocation was refused or blocked, the tool errored, or you skipped it "
        "deliberately — record it and continue with your own review:\n\n"
        "```\n"
        'specops handoff finding add --severity advisory --rule "native-review-not-run" \\\n'
        f'  --file . --action "Native review not run: {command} (<reason>)"\n'
        "```"
    )


def _builtin(entry: Entry, effort: str) -> str:
    call = entry.invocation.format(effort=effort)
    invoke = (
        f"This integration's native reviewer is `{entry.command}`. Invoke it through "
        f"{entry.mechanism} before your own pass: `{call}`, where `<from>..<head>` is the "
        "`reviewed_range` printed by `specops handoff record-scope` (write it with three "
        f"dots). {entry.caution}".rstrip()
    )
    return _required(entry.command, invoke, f"have {entry.mechanism}")


def step_3a(root: Path, integration: str) -> str:
    """Render the Step 3a native-review paragraph for *integration*."""
    entry = BUILTIN.get(integration)
    if entry is None:
        return _LEGACY
    return _builtin(entry, entry.default_effort)


def render_review(root: Path, integration: str) -> str:
    """Return the full ``/specops-review`` command text for *integration*."""
    text = _TEMPLATE.read_text(encoding="utf-8")
    return fsutil.render_template(text, {"native_review": step_3a(root, integration)})
