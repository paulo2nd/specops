"""Gate profiles: ordered, context-aware verification-gate definitions (Feature 012).

A stack-neutral, versioned configuration (`.specify/specops/gate-profiles.yaml`,
sibling of the context map) that declares an **ordered** set of gates, each with a
command, a single applicability predicate, a timeout, a required-status, failure
semantics, and an optional artifact to digest. This module owns parsing, read-only
validation (FR-014), deterministic selection (FR-002/FR-003), and synthesis of the
implicit default profile from ``specops.json`` when no config exists (FR-005).

It is stack-neutral (Principle V): the command strings stay in configuration, path
patterns are validated syntactically only (no filesystem access), and risk matches by
named-key presence/equality — never an ordinal scale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from specops import config, contextmap, outcome
from specops.errors import LedgerParseError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROFILES_RELPATH = Path(".specify") / "specops" / "gate-profiles.yaml"
OUTPUT_VERSION = 1
DEFAULT_TIMEOUT = 600  # seconds; the documented stack-neutral constant (FR-001)

# Selection reasons — the closed set (FR-003).
R_ALWAYS = "always"
R_CONTEXT = "matched-context"
R_GATE_REF = "matched-gate-ref"
R_PATH = "matched-path"
R_RISK = "matched-risk-key"
R_OUT = "out-of-scope"

# Command-result statuses.
S_LIST_OK = "list_ok"
S_VALID = "valid"
S_NO_CONFIG = "no_config"  # no file (or empty list) → default profile in effect
S_INVALID = "invalid_config"
S_USAGE_ERROR = "usage_error"

_CLASS_FOR_STATUS = {
    S_LIST_OK: outcome.PASS,
    S_VALID: outcome.PASS,
    S_NO_CONFIG: outcome.PASS,
    S_INVALID: outcome.GATE_REJECTION,
    S_USAGE_ERROR: outcome.INFRA_ERROR,
}

_VALID_ON_NONZERO = {"block", "advise"}
_VALID_APPLIES_KEYS = {"always", "contexts", "paths", "risk", "gate_ref"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ApplicabilityPredicate:
    """The single deterministic condition that decides whether a gate applies."""

    always: bool = False
    contexts: tuple[str, ...] = ()
    paths: tuple[str, ...] = ()
    risk: tuple[tuple[str, Any], ...] = ()  # (key, value|None) pairs; None = presence-only
    gate_ref: str | None = None


@dataclass(frozen=True)
class GateProfile:
    """One ordered gate entry."""

    name: str
    command: str
    applies: ApplicabilityPredicate
    timeout: int = DEFAULT_TIMEOUT
    required: bool = True
    on_nonzero: str = "block"
    artifact: str | None = None


@dataclass(frozen=True)
class SelectedGate:
    """A declared gate paired with its selection decision + machine-readable reason."""

    profile: GateProfile
    selected: bool
    reason: str


@dataclass
class GateCommandResult:
    """Rendered-agnostic command outcome (mirrors contextmap.CommandResult)."""

    command: str
    status: str
    human: str
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def cls(self) -> str:
        return _CLASS_FOR_STATUS[self.status]

    @property
    def exit_code(self) -> int:
        return outcome.exit_for(self.cls)


# ---------------------------------------------------------------------------
# Paths & loading
# ---------------------------------------------------------------------------


def profiles_path(root: Path) -> Path:
    return root / PROFILES_RELPATH


def _load_raw(root: Path) -> dict[str, Any] | None:
    """Return the parsed YAML mapping, or None when the file is absent.

    Raises LedgerParseError (exit 2) on unreadable / non-mapping YAML.
    """
    path = profiles_path(root)
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LedgerParseError(f"Cannot parse {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise LedgerParseError(f"{path}: top-level document must be a mapping.")
    return data


# ---------------------------------------------------------------------------
# Parsing (lenient; validation reports defects separately)
# ---------------------------------------------------------------------------


def _norm(value: Any) -> Any:
    """Normalize a value to a stable, hashable form for risk equality/aggregation."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def _parse_predicate(raw: Any) -> ApplicabilityPredicate:
    if not isinstance(raw, dict):
        return ApplicabilityPredicate(always=True)
    ctx_raw = raw.get("contexts")
    contexts = tuple(str(c) for c in ctx_raw) if isinstance(ctx_raw, list) else ()
    path_raw = raw.get("paths")
    paths = tuple(str(p) for p in path_raw) if isinstance(path_raw, list) else ()
    risk_raw = raw.get("risk")
    risk: tuple[tuple[str, Any], ...] = ()
    if isinstance(risk_raw, dict):
        risk = tuple((str(k), v) for k, v in risk_raw.items())
    gate_ref = raw.get("gate_ref")
    gate_ref = str(gate_ref) if isinstance(gate_ref, str) else None
    always = bool(raw.get("always", False))
    # An empty predicate means "always" (a gate with no scoping runs unconditionally).
    if not always and not contexts and not paths and not risk and gate_ref is None:
        always = True
    return ApplicabilityPredicate(
        always=always, contexts=contexts, paths=paths, risk=risk, gate_ref=gate_ref
    )


def _parse_profile(raw: Any) -> GateProfile | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("name"), str) or not raw["name"]:
        return None
    name = raw["name"]
    cmd_raw = raw.get("command")
    command = cmd_raw if isinstance(cmd_raw, str) else ""
    timeout = raw.get("timeout", DEFAULT_TIMEOUT)
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        timeout = DEFAULT_TIMEOUT
    required = raw.get("required", True)
    required = required if isinstance(required, bool) else True
    on_nonzero = raw.get("on_nonzero")
    if on_nonzero not in _VALID_ON_NONZERO:
        on_nonzero = "block" if required else "advise"
    artifact = raw.get("artifact")
    artifact = artifact if isinstance(artifact, str) else None
    return GateProfile(
        name=name, command=command, applies=_parse_predicate(raw.get("applies")),
        timeout=timeout, required=required, on_nonzero=on_nonzero, artifact=artifact,
    )


def parse(root: Path) -> tuple[list[GateProfile] | None, dict[str, Any] | None]:
    """Return (profiles, raw). ``profiles`` is None when no config file exists.

    An empty ``profiles`` list yields ``[]`` (distinct from None) so the caller can
    apply the FR-005 default in both the absent and empty cases.
    """
    raw = _load_raw(root)
    if raw is None:
        return None, None
    entries = raw.get("profiles") or []
    if not isinstance(entries, list):
        return [], raw
    profiles = [p for p in (_parse_profile(e) for e in entries) if p is not None]
    return profiles, raw


# ---------------------------------------------------------------------------
# Default profile synthesis (FR-005)
# ---------------------------------------------------------------------------


def default_profile(root: Path) -> list[GateProfile]:
    """Synthesize the implicit default profile from specops.json (FR-005, R11).

    Preserves the ``lint``/``test`` gate names **and layout** so consumers of the
    existing names see no regression: both gates are always present in the canonical
    ``lint`` → ``test`` order, and an empty command resolves to SKIPPED downstream
    (exactly today's ``_command_gate`` behavior — an empty command is a benign skip,
    not a blocking failure).
    """
    try:
        cfg = config.load(root)
    except config.ConfigError:
        cfg = {}
    always = ApplicabilityPredicate(always=True)
    return [
        GateProfile(name="lint", command=str(cfg.get("lint_command") or ""),
                    applies=always, timeout=DEFAULT_TIMEOUT, required=True, on_nonzero="block"),
        GateProfile(name="test", command=str(cfg.get("test_command") or ""),
                    applies=always, timeout=DEFAULT_TIMEOUT, required=True, on_nonzero="block"),
    ]


def profiles_for(root: Path) -> list[GateProfile]:
    """Return the authoritative ordered gate set: parsed config, or the default.

    An absent file **or** an empty ``profiles`` list both fall back to the default
    (never zero gates — FR-005).
    """
    profiles, _raw = parse(root)
    if not profiles:  # None (absent) or [] (empty) → default
        return default_profile(root)
    return profiles


# ---------------------------------------------------------------------------
# Deterministic selection (FR-002 / FR-003)
# ---------------------------------------------------------------------------


def _risk_index(affected: list[dict[str, Any]]) -> dict[str, set[Any]]:
    """Aggregate affected contexts' risk mappings into key → set(hashable values)."""
    index: dict[str, set[Any]] = {}
    for a in affected:
        for k, v in (a.get("risk") or {}).items():
            index.setdefault(str(k), set()).add(_norm(v))
    return index


def _match(
    p: GateProfile, changed_paths: list[str], ctx_ids: set[str],
    gate_refs: set[str], risk_index: dict[str, set[Any]],
) -> tuple[bool, str]:
    ap = p.applies
    if ap.always:
        return True, R_ALWAYS
    for c in ap.contexts:
        if c in ctx_ids:
            return True, f"{R_CONTEXT}:{c}"
    # A resolved context's `gates` list is honored as an implicit match for the gate
    # it names (FR-002); an explicit gate_ref lets a profile match a *different* id.
    for ref in (p.name, ap.gate_ref):
        if ref is not None and ref in gate_refs:
            return True, f"{R_GATE_REF}:{ref}"
    for glob in ap.paths:
        if any(contextmap._matches(glob, path) for path in changed_paths):
            return True, f"{R_PATH}:{glob}"
    for key, value in ap.risk:
        if key in risk_index and (value is None or _norm(value) in risk_index[key]):
            return True, f"{R_RISK}:{key}"
    return False, R_OUT


def select_gates(
    profiles: list[GateProfile], changed_paths: list[str], affected: list[dict[str, Any]]
) -> list[SelectedGate]:
    """Pure, deterministic selection over the given inputs (FR-003).

    ``affected`` is the Feature 009 ``context impact`` list — each item a mapping with
    ``context_id``, ``gates`` (list), and ``risk`` (mapping). Selection preserves the
    profiles' declared order (FR-021).
    """
    ctx_ids = {a.get("context_id") for a in affected if a.get("context_id")}
    gate_refs: set[str] = set()
    for a in affected:
        gate_refs |= {str(g) for g in (a.get("gates") or [])}
    risk_index = _risk_index(affected)
    results: list[SelectedGate] = []
    for p in profiles:
        selected, reason = _match(p, changed_paths, ctx_ids, gate_refs, risk_index)  # type: ignore[arg-type]
        results.append(SelectedGate(p, selected, reason))
    return results


def _affected_for(root: Path, changed_paths: list[str]) -> list[dict[str, Any]]:
    """Resolve affected contexts (with gates/risk) for the changed paths.

    Degrades to an empty list when no map is present or it is unresolvable — so
    ``always``/``paths`` predicates still select (roadmap Rule 5).
    """
    if not changed_paths:
        return []
    result = contextmap.cmd_impact(root, paths=changed_paths)
    impact = result.extra.get("impact") if isinstance(result.extra, dict) else None
    if not isinstance(impact, dict):
        return []
    affected = impact.get("affected")
    return affected if isinstance(affected, list) else []


# ---------------------------------------------------------------------------
# Read-only commands (FR-014 / FR-015)
# ---------------------------------------------------------------------------


def _validate_output_version(raw: dict[str, Any], diags: list[str]) -> None:
    ov = raw.get("output_version")
    if ov is None:
        return  # absent ⇒ assume current (a new file SHOULD set it, but not a defect)
    if not isinstance(ov, int) or isinstance(ov, bool) or ov != OUTPUT_VERSION:
        diags.append(f"unsupported output_version {ov!r} (expected {OUTPUT_VERSION})")


def _known_context_ids(root: Path) -> set[str] | None:
    """Return the map's context ids, or None when no resolvable map exists."""
    vr = contextmap.validate(root)
    if vr.contexts is None:
        return None
    return {c.id for c in vr.contexts}


def validate(root: Path) -> GateCommandResult:
    """Validate the gate-profile config; report every defect in one pass (FR-014)."""
    try:
        raw = _load_raw(root)
    except LedgerParseError as exc:
        return GateCommandResult("gate-validate", S_USAGE_ERROR, exc.message)
    if raw is None:
        return GateCommandResult(
            "gate-validate", S_NO_CONFIG,
            "gate-validate: no gate-profiles.yaml — default profile (lint/test) in effect.",
            {"profiles": 0},
        )

    diags: list[str] = []
    _validate_output_version(raw, diags)

    entries = raw.get("profiles")
    if entries is None:
        entries = []
    if not isinstance(entries, list):
        diags.append("`profiles` must be a list.")
        entries = []

    known_ids = _known_context_ids(root)
    seen: set[str] = set()
    for i, entry in enumerate(entries):
        label = f"profile[{i}]"
        if not isinstance(entry, dict):
            diags.append(f"{label}: must be a mapping.")
            continue
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            diags.append(f"{label}: missing or empty `name`.")
            name = label
        elif name in seen:
            diags.append(f"{label}: duplicate gate name {name!r}.")
        else:
            seen.add(name)
        cmd = entry.get("command")
        if not isinstance(cmd, str) or not cmd:
            diags.append(f"{name}: missing or empty `command`.")
        timeout = entry.get("timeout", DEFAULT_TIMEOUT)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout <= 0:
            diags.append(f"{name}: `timeout` must be a positive integer of seconds.")
        if "required" in entry and not isinstance(entry["required"], bool):
            diags.append(f"{name}: `required` must be a boolean.")
        if "on_nonzero" in entry and entry["on_nonzero"] not in _VALID_ON_NONZERO:
            diags.append(f"{name}: `on_nonzero` must be 'block' or 'advise'.")
        _validate_applies(entry.get("applies"), name, known_ids, diags)

    if diags:
        human = "gate-validate: {n} defect(s):\n{lines}".format(
            n=len(diags), lines="\n".join(f"  - {d}" for d in diags)
        )
        return GateCommandResult("gate-validate", S_INVALID, human, {"defects": diags})
    return GateCommandResult(
        "gate-validate", S_VALID,
        f"gate-validate: {len(entries)} profile(s) valid.", {"profiles": len(entries)},
    )


def _validate_applies(
    applies: Any, name: str, known_ids: set[str] | None, diags: list[str]
) -> None:
    if applies is None:
        return
    if not isinstance(applies, dict):
        diags.append(f"{name}: `applies` must be a mapping.")
        return
    unknown = set(applies) - _VALID_APPLIES_KEYS
    if unknown:
        diags.append(f"{name}: unknown `applies` key(s): {', '.join(sorted(unknown))}.")
    paths = applies.get("paths")
    if paths is not None:
        if not isinstance(paths, list):
            diags.append(f"{name}: `applies.paths` must be a list.")
        else:
            for pat in paths:
                code = contextmap._classify_pattern(pat)
                if code:
                    diags.append(f"{name}: {code} in `applies.paths`: {pat!r}.")
    if known_ids is not None:
        for c in applies.get("contexts") or []:
            if isinstance(c, str) and c not in known_ids:
                diags.append(f"{name}: `applies.contexts` references unknown context {c!r}.")
        ref = applies.get("gate_ref")
        # gate_ref points at a context's declared gate id; it need not be a context id,
        # so we do not treat it as dangling here (a gate id lives in the map's `gates`).
        if ref is not None and not isinstance(ref, str):
            diags.append(f"{name}: `applies.gate_ref` must be a string.")


def cmd_list(root: Path, changed_paths: list[str]) -> GateCommandResult:
    """Resolve + display the selected suite for the given effective diff (read-only)."""
    profiles, raw = parse(root)
    used_default = not profiles
    gates = profiles if profiles else default_profile(root)
    affected = _affected_for(root, changed_paths)
    selection = select_gates(gates, changed_paths, affected)

    rows = [
        {"name": s.profile.name, "selected": s.selected, "reason": s.reason,
         "required": s.profile.required}
        for s in selection
    ]
    n_sel = sum(1 for s in selection if s.selected)
    origin = "default profile (lint/test)" if used_default else f"{len(gates)} declared profile(s)"
    lines = [f"gate-list: {n_sel}/{len(gates)} selected from {origin}:"]
    for s in selection:
        mark = "[x]" if s.selected else "[ ]"
        req = "required" if s.profile.required else "optional"
        lines.append(f"  {mark} {s.profile.name} ({req}) — {s.reason}")
    status = S_NO_CONFIG if used_default else S_LIST_OK
    extra = {
        "selection": rows,
        "changed_paths": sorted(changed_paths),
        "default_profile": used_default,
    }
    return GateCommandResult("gate-list", status, "\n".join(lines), extra)


__all__ = [
    "PROFILES_RELPATH", "OUTPUT_VERSION", "DEFAULT_TIMEOUT",
    "ApplicabilityPredicate", "GateProfile", "SelectedGate", "GateCommandResult",
    "profiles_path", "parse", "default_profile", "profiles_for",
    "select_gates", "validate", "cmd_list",
]
