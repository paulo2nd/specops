"""Gate profiles: ordered, context-aware verification-gate definitions (Feature 012).

A stack-neutral, versioned configuration (`.specify/specops/gate-profiles.yaml`,
sibling of the context map) that declares an **ordered** set of gates, each with a
command, a single applicability predicate, a timeout, and a required-status. This
module owns parsing, read-only validation (FR-014), deterministic selection
(FR-002/FR-003), fail-closed suite resolution for the review pipeline, and synthesis
of the implicit default profile from ``specops.json`` when no config exists (FR-005).

It is stack-neutral (Principle V): the command strings stay in configuration, path
patterns are validated syntactically only (no filesystem access), and risk matches by
named-key presence/equality — never an ordinal scale.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from specops import config, contextmap, outcome
from specops.errors import LedgerParseError, SpecopsError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROFILES_RELPATH = Path(".specify") / "specops" / "gate-profiles.yaml"
OUTPUT_VERSION = 1
# Documented default timeout (seconds) for an AUTHORED profile that omits `timeout`.
# The synthesized default profile uses None (unbounded) so an upgraded repository's
# lint/test runs are not newly killed (FR-005 — behaves exactly as before).
DEFAULT_TIMEOUT = 600

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

# ---------------------------------------------------------------------------
# Declarative field tables (Feature 019 US4, FR-011): the single source of the
# profile/predicate field knowledge — key set, expected type, presence
# convention, and the validator's type-defect wording — consumed by BOTH the
# lenient parser (fallback on mismatch) and the validator (defect on mismatch),
# so a field added to one side can never be forgotten by the other. Checks that
# are not per-field shape checks (duplicate names, unknown-context references,
# path-pattern classification, timeout positivity) remain explicit code.
# ---------------------------------------------------------------------------

# applies.<key> → (presence convention, expected type, validator wording).
# "present" flags a key that exists with ANY non-conforming value (even null);
# "notnone" tolerates an explicit null (historical validate behavior).
_APPLIES_FIELDS: dict[str, tuple[str, type, str]] = {
    "always": ("present", bool, "a boolean"),
    "contexts": ("notnone", list, "a list"),
    "paths": ("notnone", list, "a list"),
    "risk": ("present", dict, "a mapping"),
    "gate_ref": ("notnone", str, "a string"),
}
_VALID_APPLIES_KEYS = set(_APPLIES_FIELDS)

# profile.<key> → (expected type, lenient-parse default). ``name`` is handled
# apart (a profile without a usable name is dropped by parse / labeled by validate).
_PROFILE_FIELDS: dict[str, tuple[type, Any]] = {
    "command": (str, ""),
    "timeout": (int, DEFAULT_TIMEOUT),
    "required": (bool, True),
}


def _lenient_applies(raw: dict, key: str) -> Any | None:
    """Lenient parse of ``applies.<key>``: the table-typed value, or None on mismatch."""
    _presence, expected, _word = _APPLIES_FIELDS[key]
    val = raw.get(key)
    return val if isinstance(val, expected) else None


def _lenient_profile(raw: dict, key: str) -> Any:
    """Lenient parse of a profile field: the table-typed value, or its default."""
    expected, default = _PROFILE_FIELDS[key]
    val = raw.get(key, default)
    if expected is int and isinstance(val, bool):
        return default  # bool is an int subclass; never a valid timeout
    return val if isinstance(val, expected) else default


def _applies_type_defect(applies: dict, key: str, name: str) -> str | None:
    """The validator's table-driven type check for ``applies.<key>`` (or None)."""
    presence, expected, word = _APPLIES_FIELDS[key]
    val = applies.get(key)
    present = (key in applies) if presence == "present" else (val is not None)
    if present and not isinstance(val, expected):
        return f"{name}: `applies.{key}` must be {word}."
    return None


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
    timeout: int | None = DEFAULT_TIMEOUT  # None = unbounded (the synthesized default)
    required: bool = True


@dataclass(frozen=True)
class SelectedGate:
    """A declared gate paired with its selection decision + machine-readable reason."""

    profile: GateProfile
    selected: bool
    reason: str


class GateCommandResult(outcome.CommandResult):
    """A gate command's outcome — the shared :class:`outcome.CommandResult` with this
    module's status→class map."""

    _CLASS_MAP = _CLASS_FOR_STATUS


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
    ctx_raw = _lenient_applies(raw, "contexts")
    contexts = tuple(str(c) for c in ctx_raw) if ctx_raw is not None else ()
    path_raw = _lenient_applies(raw, "paths")
    paths = tuple(str(p) for p in path_raw) if path_raw is not None else ()
    risk_raw = _lenient_applies(raw, "risk")
    risk: tuple[tuple[str, Any], ...] = ()
    if risk_raw is not None:
        risk = tuple((str(k), v) for k, v in risk_raw.items())
    gate_ref_raw = _lenient_applies(raw, "gate_ref")
    gate_ref = str(gate_ref_raw) if gate_ref_raw is not None else None
    # Deliberately looser than the table (historical): any truthy value enables.
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
    return GateProfile(
        name=name,
        command=_lenient_profile(raw, "command"),
        applies=_parse_predicate(raw.get("applies")),
        timeout=_lenient_profile(raw, "timeout"),
        required=_lenient_profile(raw, "required"),
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
    # timeout=None (unbounded): the pre-Feature-012 lint/test gates had no timeout, so
    # an upgraded repo whose suite legitimately runs long is not newly killed (FR-005).
    return [
        GateProfile(name="lint", command=str(cfg.get("lint_command") or ""),
                    applies=always, timeout=None, required=True),
        GateProfile(name="test", command=str(cfg.get("test_command") or ""),
                    applies=always, timeout=None, required=True),
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


def resolve_suite(root: Path) -> list[GateProfile]:
    """Return the authoritative gate set, failing closed on an INVALID *present* config.

    A malformed `gate-profiles.yaml` MUST NOT silently fall back to the default suite —
    that would skip declared required gates and yield a false pass. When a config file is
    present and invalid, this raises SpecopsError so `specops preflight` rejects (exit 1)
    instead of degrading. An absent file, or a valid empty `profiles` list, yields the
    default profile. This is the fail-closed resolution used by the review pipeline;
    `gate list`/`gate validate` remain lenient inspection surfaces.
    """
    result = validate(root)
    if result.status == S_INVALID:
        raise SpecopsError(
            "Invalid gate-profiles.yaml — refusing to fall back to the default suite:\n"
            + result.human
        )
    return profiles_for(root)


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
        if any(contextmap.matches(glob, path) for path in changed_paths):
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


def affected_for(root: Path, changed_paths: list[str]) -> list[dict[str, Any]]:
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
    # Per-key type checks are table-driven (_APPLIES_FIELDS) so parse and validate
    # can never disagree on a field's expected shape (FR-011).
    if (d := _applies_type_defect(applies, "always", name)) is not None:
        diags.append(d)
    # `contexts` MUST be a list — a scalar would otherwise crash/garble the loop below
    # and (in the parser) silently collapse the predicate to always=True.
    contexts = applies.get("contexts")
    if (d := _applies_type_defect(applies, "contexts", name)) is not None:
        diags.append(d)
        contexts = None
    # `risk` MUST be a mapping (named-key -> value); a list/scalar would be dropped by
    # the parser and silently widen the gate to always-run.
    if (d := _applies_type_defect(applies, "risk", name)) is not None:
        diags.append(d)
    paths = applies.get("paths")
    if paths is not None:
        if (d := _applies_type_defect(applies, "paths", name)) is not None:
            diags.append(d)
        else:
            for pat in paths:
                code = contextmap.classify_pattern(pat)
                if code:
                    diags.append(f"{name}: {code} in `applies.paths`: {pat!r}.")
    if known_ids is not None and isinstance(contexts, list):
        for c in contexts:
            if isinstance(c, str) and c not in known_ids:
                diags.append(f"{name}: `applies.contexts` references unknown context {c!r}.")
    # gate_ref points at a context's declared gate id; it need not be a context id,
    # so we do not treat it as dangling here (a gate id lives in the map's `gates`).
    if (d := _applies_type_defect(applies, "gate_ref", name)) is not None:
        diags.append(d)


def cmd_list(root: Path, changed_paths: list[str]) -> GateCommandResult:
    """Resolve + display the selected suite for the given effective diff (read-only)."""
    profiles, raw = parse(root)
    used_default = not profiles
    gates = profiles if profiles else default_profile(root)
    affected = affected_for(root, changed_paths)
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
    "profiles_path", "parse", "default_profile", "profiles_for", "resolve_suite",
    "select_gates", "validate", "cmd_list",
]
