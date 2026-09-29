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
from typing import Any

from specops import config, fsutil

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


def _none(integration: str) -> str:
    return (
        f"**Native code review.** This integration (`{integration}`) has no native "
        "code-review command known to SpecOps — perform the code review yourself directly "
        "on the diff. A project can declare one in `specops.json` → `native_review`."
    )


def _override(command: str) -> str:
    invoke = (
        f"This project's native reviewer for this integration is `{command}` (configured "
        "in `specops.json`). Invoke it with your integration's own mechanism (tool, skill "
        "or shell) before your own pass, scoped to the round's `reviewed_range` from "
        "`specops handoff record-scope`."
    )
    return _required(command, invoke, "be able to invoke it")


def _fail(key: str, problem: str) -> config.ConfigError:
    return config.ConfigError(f"{config.CONFIG_FILENAME}: native_review{key} {problem}")


def _project_entry(root: Path, integration: str) -> dict[str, Any] | None:
    """Return this integration's validated ``native_review`` override, if any.

    ``specops.json`` is optional here (a first install has none yet). Only the
    integration being rendered is validated, so an entry for an integration that is
    not installed never breaks an install (data-model Entity 2).
    """
    if not config.config_path(root).is_file():
        return None
    block = config.load(root).get("native_review")
    if block is None:
        return None
    if not isinstance(block, dict):
        raise _fail("", "must be an object keyed by integration id")
    entry = block.get(integration)
    key = f".{integration}"
    if entry is None:
        return None
    if not isinstance(entry, dict):
        raise _fail(key, "must be an object with optional 'command' and 'effort'")
    unknown = sorted(set(entry) - {"command", "effort"})
    if unknown:
        raise _fail(key, f"has unknown key(s) {', '.join(unknown)} (allowed: command, effort)")
    command = entry.get("command")
    if command is not None and (not isinstance(command, str) or not command.strip()):
        raise _fail(f"{key}.command", "must be a non-empty string or null")
    return entry


def step_3a(root: Path, integration: str) -> str:
    """Render the Step 3a native-review paragraph for *integration*.

    Raises :class:`config.ConfigError` on an invalid ``native_review`` override.
    """
    project = _project_entry(root, integration) or {}
    # A project `command` (string or null) replaces the built-in entry outright.
    resolved = project["command"] if "command" in project else BUILTIN.get(integration)
    if "effort" in project and not isinstance(resolved, Entry):
        raise _fail(
            f".{integration}.effort",
            "only applies to a built-in reviewer; put arguments in 'command'",
        )
    if resolved is None:
        return _none(integration)
    if isinstance(resolved, str):
        return _override(resolved)
    effort = project.get("effort", resolved.default_effort)
    if effort not in resolved.efforts:
        raise _fail(
            f".{integration}.effort", f"must be one of {', '.join(resolved.efforts)}"
        )
    return _builtin(resolved, effort)


def render_review(root: Path, integration: str) -> str:
    """Return the full ``/specops-review`` command text for *integration*."""
    text = _TEMPLATE.read_text(encoding="utf-8")
    return fsutil.render_template(text, {"native_review": step_3a(root, integration)})
