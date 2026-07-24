"""Context Map Core (Feature 008).

Owns the on-disk contract of `.specify/specops/context-map.yaml`: schema
versioning, five-state classification, one-pass validation, deterministic
gitignore-style glob matching + a total most-specific-wins specificity
comparator, cycle-safe transitive dependency expansion, and the reason trace.

The command layer in :mod:`specops.cli` calls the ``cmd_*`` functions here and
renders their :class:`CommandResult` via :mod:`specops.outcome`. Only
``cmd_init`` writes; ``validate``/``resolve``/``explain`` never mutate state.

Determinism (SC-001): resolution performs no filesystem walk and emits no
timestamps; every ordering is Unicode-codepoint based (locale-independent).
"""
from __future__ import annotations

import hashlib
import json as _json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from specops import ledger, outcome, speckit

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAP_RELPATH = Path(".specify") / "specops" / "context-map.yaml"
_TEMPLATE = Path(__file__).resolve().parent / "templates" / "specops" / "context-map.yaml"

CURRENT_SCHEMA = 1
OLDEST_SUPPORTED = 1

OUTPUT_VERSION = 1

# Lifecycle phases a read set may key on (plus the phase-agnostic `base`).
PHASES = ("specify", "plan", "tasks", "implement", "review")

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_GATE_RE = re.compile(r"^\S+$")

# Version classification (mirrors ledger.classify semantics).
VERSION_CURRENT = "current"
VERSION_TOO_NEW = "too_new"
VERSION_UNSUPPORTED = "unsupported"

# Statuses (the fine-grained `status` field; see contracts/context-cli.md).
S_NO_MAP = "no_map_present"
S_MALFORMED = "malformed"
S_SCHEMA_INVALID = "schema_invalid"
S_UNSUPPORTED_VERSION = "unsupported_version"
S_EMPTY_VALID = "empty_valid"
S_VALID = "valid"
S_RESOLVED = "resolved"
S_NO_MATCH = "no_matching_context"
S_AMBIGUOUS = "ambiguous_ownership"
S_CREATED = "created"
S_ALREADY_EXISTS = "already_exists"
S_USAGE_ERROR = "usage_error"

# Feature 009 — consumption statuses (plan-check / impact / stale).
S_PLAN_CHECK_OK = "plan_check_ok"
S_MISSING_DECLARATION = "missing_declaration"
S_UNKNOWN_DECLARED_CONTEXT = "unknown_declared_context"
S_UNDECLARED_OWNER = "undeclared_owner"
S_IMPACT_OK = "impact_ok"
S_UNBOUNDED_EXPANSION = "unbounded_expansion"
S_STALE_OK = "stale_ok"
S_STALE_FOUND = "stale_found"

# outcome class per status → drives the exit code (0/1/2).
_CLASS_FOR_STATUS = {
    S_NO_MAP: outcome.PASS,
    S_EMPTY_VALID: outcome.PASS,
    S_VALID: outcome.PASS,
    S_RESOLVED: outcome.PASS,
    S_NO_MATCH: outcome.PASS,
    S_CREATED: outcome.PASS,
    S_ALREADY_EXISTS: outcome.PASS,
    S_PLAN_CHECK_OK: outcome.PASS,
    S_IMPACT_OK: outcome.PASS,
    S_STALE_OK: outcome.PASS,
    S_MALFORMED: outcome.GATE_REJECTION,
    S_SCHEMA_INVALID: outcome.GATE_REJECTION,
    S_UNSUPPORTED_VERSION: outcome.GATE_REJECTION,
    S_AMBIGUOUS: outcome.GATE_REJECTION,
    S_MISSING_DECLARATION: outcome.GATE_REJECTION,
    S_UNKNOWN_DECLARED_CONTEXT: outcome.GATE_REJECTION,
    S_UNDECLARED_OWNER: outcome.GATE_REJECTION,
    S_UNBOUNDED_EXPANSION: outcome.GATE_REJECTION,
    S_STALE_FOUND: outcome.GATE_REJECTION,
    S_USAGE_ERROR: outcome.INFRA_ERROR,
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class Context:
    """A named region of the repository (see data-model.md)."""

    id: str
    match: list[str]
    reads: dict[str, list[str]]
    ownership: Any
    dependencies: list[str]
    gates: list[str]
    risk: dict[str, Any]
    decl_index: int


# A specificity tuple and a scored match candidate (context, pattern, specificity).
Specificity = tuple[int, int, int]
Candidate = tuple["Context", str, "Specificity"]


@dataclass
class ValidateResult:
    """Outcome of loading + validating a map."""

    status: str
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    contexts: list[Context] | None = None


class CommandResult(outcome.CommandResult):
    """A context command's outcome — the shared :class:`outcome.CommandResult` with this
    module's status→class map."""

    _CLASS_MAP = _CLASS_FOR_STATUS


def _diag(code: str, message: str, *, context_id: str | None = None,
          field_name: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {"code": code, "message": message}
    if context_id is not None:
        d["context_id"] = context_id
    if field_name is not None:
        d["field"] = field_name
    return d


# ---------------------------------------------------------------------------
# Paths & version
# ---------------------------------------------------------------------------


def map_path(root: Path) -> Path:
    return root / MAP_RELPATH


def classify(version: Any) -> str:
    """Classify a declared schema version relative to the supported range."""
    if not isinstance(version, int) or isinstance(version, bool):
        return VERSION_UNSUPPORTED
    if version > CURRENT_SCHEMA:
        return VERSION_TOO_NEW
    if version < OLDEST_SUPPORTED:
        return VERSION_UNSUPPORTED
    return VERSION_CURRENT


def migrate_to_current(data: dict[str, Any]) -> dict[str, Any]:
    """Forward-migrate a parsed map to the current schema.

    Identity scaffold for v1 (no prior shape exists). Present so a future v2 adds
    a real migration here without reshaping callers. Only a `current`-version map
    is passed in; unsupported versions are rejected before this point.
    """
    return data


# ---------------------------------------------------------------------------
# Glob matching + specificity (R5)
# ---------------------------------------------------------------------------


def _classify_pattern(pat: Any) -> str | None:
    """Return a defect code for an unsafe/invalid glob, or None when acceptable."""
    if not isinstance(pat, str) or pat == "":
        return "invalid_path_pattern"
    if "\\" in pat:
        return "invalid_path_pattern"
    # Absolute POSIX path, or a Windows drive-qualified path (`C:\`, `C:/`) — a
    # bare ':' inside a segment (e.g. a legitimate POSIX `a:b/**`) is not flagged.
    if pat.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", pat):
        return "unsafe_path_traversal"
    if ".." in pat.split("/"):
        return "unsafe_path_traversal"
    return None


@lru_cache(maxsize=4096)
def _translate_glob(pattern: str) -> re.Pattern[str]:
    """Translate a gitignore-style glob into an anchored regex over a posix path.

    Cached: the same pattern is compiled once and reused across every path it is
    tested against (so e.g. `context stale` is O(patterns + patterns*files) match
    work, not O(patterns*files) regex compilations).
    """
    i, n = 0, len(pattern)
    out: list[str] = []
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                j = i + 2
                if j < n and pattern[j] == "/":
                    out.append("(?:.*/)?")  # `**/` → zero or more segments
                    i = j + 1
                else:
                    out.append(".*")  # trailing/bare `**`
                    i = j
            else:
                out.append("[^/]*")  # `*` stays within a segment
                i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "/":
            out.append("/")
            i += 1
        else:
            out.append(re.escape(c))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def _specificity(pattern: str) -> Specificity:
    """Specificity key where a *larger* tuple is more specific (FR-008).

    (literal_prefix_len, -wildcard_token_count, segment_count).
    """
    m = re.search(r"[*?]", pattern)
    literal_prefix = len(pattern) if m is None else m.start()
    wildcards = len(re.findall(r"\*\*|\*|\?", pattern))
    segments = len([s for s in pattern.split("/") if s != ""])
    return (literal_prefix, -wildcards, segments)


def _matches(pattern: str, path: str) -> bool:
    try:
        return _translate_glob(pattern).match(path) is not None
    except re.error:
        return False


# ---------------------------------------------------------------------------
# Load + validate (R3, R8)
# ---------------------------------------------------------------------------


def _parse_context(raw: Any, index: int, diags: list[dict[str, Any]]) -> Context | None:
    if not isinstance(raw, dict):
        diags.append(_diag("schema_invalid", f"context #{index} is not a mapping",
                            field_name="contexts"))
        return None
    # Best-effort parse: always return a Context when the entry is a mapping so
    # cross-context checks (duplicate id, dangling dep, cycle) still run for it,
    # while every field defect is recorded (one-pass aggregation).
    cid = raw.get("id")
    ctx_id = cid if isinstance(cid, str) else f"#{index}"
    if not isinstance(cid, str) or not _ID_RE.match(cid):
        diags.append(_diag("schema_invalid", f"invalid or missing context id: {cid!r}",
                            context_id=ctx_id, field_name="id"))

    match_raw = raw.get("match")
    match: list[str] = []
    if not isinstance(match_raw, list) or not match_raw:
        diags.append(_diag("schema_invalid", "`match` must be a non-empty list",
                            context_id=ctx_id, field_name="match"))
    else:
        for pat in match_raw:
            code = _classify_pattern(pat)
            if code is not None:
                diags.append(_diag(code, f"pattern {pat!r} is {code.replace('_', ' ')}",
                                   context_id=ctx_id, field_name="match"))
            else:
                match.append(pat)

    reads_raw = raw.get("reads")
    if reads_raw is None:
        reads_raw = {}
    reads: dict[str, list[str]] = {}
    if not isinstance(reads_raw, dict):
        diags.append(_diag("schema_invalid", "`reads` must be a mapping",
                            context_id=ctx_id, field_name="reads"))
    else:
        for key, value in reads_raw.items():
            if key != "base" and key not in PHASES:
                diags.append(_diag("schema_invalid", f"unknown read-set key {key!r}",
                                   context_id=ctx_id, field_name="reads"))
                continue
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                diags.append(_diag("schema_invalid", f"read set {key!r} must be a list of strings",
                                   context_id=ctx_id, field_name="reads"))
                continue
            reads[key] = list(value)

    deps_raw = raw.get("dependencies")
    if deps_raw is None:
        deps_raw = []
    deps: list[str] = []
    if not isinstance(deps_raw, list) or not all(isinstance(d, str) for d in deps_raw):
        diags.append(_diag("schema_invalid", "`dependencies` must be a list of context ids",
                            context_id=ctx_id, field_name="dependencies"))
    else:
        deps = list(deps_raw)

    gates_raw = raw.get("gates")
    if gates_raw is None:
        gates_raw = []
    gates: list[str] = []
    if not isinstance(gates_raw, list) or not all(
        isinstance(g, str) and _GATE_RE.match(g) for g in gates_raw
    ):
        diags.append(_diag("schema_invalid", "`gates` must be a list of well-formed identifiers",
                            context_id=ctx_id, field_name="gates"))
    else:
        gates = list(gates_raw)

    risk_raw = raw.get("risk")
    if risk_raw is None:
        risk_raw = {}
    if not isinstance(risk_raw, dict) or not all(isinstance(k, str) for k in risk_raw):
        diags.append(_diag("schema_invalid", "`risk` must be a string-keyed mapping",
                            context_id=ctx_id, field_name="risk"))
        risk_raw = {}

    return Context(id=ctx_id, match=match, reads=reads, ownership=raw.get("ownership"),
                   dependencies=deps, gates=gates, risk=dict(risk_raw), decl_index=index)


def _check_cross_context(contexts: list[Context], diags: list[dict[str, Any]]) -> None:
    by_id: dict[str, Context] = {}
    for ctx in contexts:
        if ctx.id in by_id:
            diags.append(_diag("duplicate_context_id", f"context id {ctx.id!r} is declared twice",
                               context_id=ctx.id, field_name="id"))
        else:
            by_id[ctx.id] = ctx

    for ctx in contexts:
        for dep in ctx.dependencies:
            if dep not in by_id:
                diags.append(_diag("dangling_dependency",
                                   f"context {ctx.id!r} depends on unknown context {dep!r}",
                                   context_id=ctx.id, field_name="dependencies"))

    _check_ambiguous(contexts, diags)

    cyc = _find_cycle(by_id)
    if cyc is not None:
        diags.append(_diag("dependency_cycle",
                           "dependency cycle: " + " -> ".join(cyc),
                           field_name="dependencies"))


def _witness(pattern: str) -> str:
    """A concrete repo path the pattern matches (`*`/`**`/`?` → a literal token).

    Used only as a *sound* overlap probe: if the witness of one pattern matches a
    second pattern, the two genuinely overlap. A non-match is inconclusive (the
    residual case is still caught fail-closed at resolve time), so this never
    yields a false ambiguity.
    """
    out: list[str] = []
    i, n = 0, len(pattern)
    while i < n:
        c = pattern[i]
        if c == "*":
            if i + 1 < n and pattern[i + 1] == "*":
                j = i + 2
                if j < n and pattern[j] == "/":
                    out.append("x/")
                    i = j + 1
                else:
                    out.append("x")
                    i = j
            else:
                out.append("x")
                i += 1
        elif c == "?":
            out.append("x")
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _check_ambiguous(contexts: list[Context], diags: list[dict[str, Any]]) -> None:
    """Flag two distinct contexts whose patterns tie on specificity AND overlap.

    Detects both the identical-pattern case and different patterns of equal
    specificity that a concrete path could hit simultaneously (the tie `resolve`
    would reject), so `validate` no longer certifies a map `resolve` then rejects.
    """
    scored: list[tuple[str, str, Specificity]] = [
        (ctx.id, pat, _specificity(pat)) for ctx in contexts for pat in ctx.match
    ]
    reported: set[tuple[str, str]] = set()
    for i in range(len(scored)):
        cid_a, pat_a, spec_a = scored[i]
        for j in range(i + 1, len(scored)):
            cid_b, pat_b, spec_b = scored[j]
            if cid_a == cid_b or spec_a != spec_b:
                continue
            if _matches(pat_b, _witness(pat_a)) or _matches(pat_a, _witness(pat_b)):
                key = tuple(sorted((cid_a, cid_b)))
                if key in reported:
                    continue
                reported.add(key)  # type: ignore[arg-type]
                diags.append(_diag(
                    "ambiguous_ownership",
                    f"contexts {cid_a!r} ({pat_a!r}) and {cid_b!r} ({pat_b!r}) "
                    f"claim overlapping paths at equal specificity",
                    field_name="match",
                ))


def _find_cycle(by_id: dict[str, Context]) -> list[str] | None:
    """Return the participating ids of the first cycle (stable order), or None."""
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[str, int] = {cid: WHITE for cid in by_id}

    def visit(cid: str, stack: list[str]) -> list[str] | None:
        color[cid] = GREY
        stack.append(cid)
        for dep in by_id[cid].dependencies:
            if dep not in by_id:
                continue
            if color[dep] == GREY:
                return stack[stack.index(dep):] + [dep]
            if color[dep] == WHITE:
                found = visit(dep, stack)
                if found is not None:
                    return found
        stack.pop()
        color[cid] = BLACK
        return None

    for cid in by_id:  # deterministic: declaration order preserved by dict
        if color[cid] == WHITE:
            found = visit(cid, [])
            if found is not None:
                return found
    return None


def validate(root: Path) -> ValidateResult:
    """Load and validate the map into one of the discriminated states (R3)."""
    p = map_path(root)
    if not p.exists():
        return ValidateResult(S_NO_MAP)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (yaml.YAMLError, UnicodeDecodeError, OSError) as exc:
        return ValidateResult(S_MALFORMED, [_diag("malformed", f"unreadable map: {exc}")])
    if not isinstance(raw, dict):
        return ValidateResult(S_MALFORMED, [_diag("malformed", "map root is not a mapping")])

    kind = classify(raw.get("schema_version"))
    if kind != VERSION_CURRENT:
        return ValidateResult(S_UNSUPPORTED_VERSION, [_diag(
            "unsupported_schema_version",
            f"schema_version {raw.get('schema_version')!r} is {kind} "
            f"(supported: {OLDEST_SUPPORTED}..{CURRENT_SCHEMA})",
            field_name="schema_version",
        )])
    raw = migrate_to_current(raw)  # no-op for v1; the forward-migration seam

    contexts_raw = raw.get("contexts")
    if contexts_raw is None:
        contexts_raw = []
    if not isinstance(contexts_raw, list):
        return ValidateResult(S_SCHEMA_INVALID,
                              [_diag("schema_invalid", "`contexts` must be a list",
                                     field_name="contexts")])

    diags: list[dict[str, Any]] = []
    contexts: list[Context] = []
    for idx, raw_ctx in enumerate(contexts_raw):
        parsed = _parse_context(raw_ctx, idx, diags)
        if parsed is not None:
            contexts.append(parsed)
    _check_cross_context(contexts, diags)

    if diags:
        return ValidateResult(S_SCHEMA_INVALID, diags)
    if not contexts:
        return ValidateResult(S_EMPTY_VALID, contexts=[])
    return ValidateResult(S_VALID, contexts=contexts)


# ---------------------------------------------------------------------------
# Resolution + expansion (R6)
# ---------------------------------------------------------------------------


def _read_set_for(ctx: Context, phase: str | None) -> tuple[list[str], str]:
    """Return (read_set, source) with base/empty fallback (FR-009)."""
    if phase is not None and phase in ctx.reads:
        return list(ctx.reads[phase]), "phase"
    if "base" in ctx.reads:
        return list(ctx.reads["base"]), "base"
    return [], "empty"


def _candidates_for_path(contexts: list[Context], path: str) -> list[Candidate]:
    """Best matching (context, pattern, specificity) per context, most-specific first."""
    best: list[Candidate] = []
    for ctx in contexts:
        matched = [(pat, _specificity(pat)) for pat in ctx.match if _matches(pat, path)]
        if not matched:
            continue
        pat, spec = max(matched, key=lambda t: (t[1], t[0]))
        best.append((ctx, pat, spec))
    # Sort most-specific first; codepoint tie-break on the pattern for total order.
    best.sort(key=lambda t: (t[2], t[1]), reverse=True)
    return best


def _build_expanded(root_ctx: Context, by_id: dict[str, Context],
                    phase: str | None) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Cycle-safe DFS expansion → (expanded_read_set, dependency_edges)."""
    expanded: list[dict[str, str]] = []
    edges: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    visited: set[str] = set()

    def visit(ctx: Context, via: str) -> None:
        if ctx.id in visited:
            return
        visited.add(ctx.id)
        reads, _src = _read_set_for(ctx, phase)
        for pth in reads:
            if pth not in seen_paths:
                seen_paths.add(pth)
                expanded.append({"path": pth, "via": via})
        for dep_id in ctx.dependencies:
            dep = by_id.get(dep_id)
            if dep is None:
                continue
            edges.append({"from": ctx.id, "to": dep_id})
            visit(dep, f"{ctx.id}->{dep_id}")

    visit(root_ctx, root_ctx.id)
    return expanded, edges


def _deciding_dimension(cands: list[Candidate]) -> str:
    if len(cands) == 1:
        return "only_candidate"
    a, b = cands[0][2], cands[1][2]
    if a == b:
        return "ambiguous"
    names = ("literal_prefix", "wildcards", "segments")
    for i in range(3):
        if a[i] != b[i]:
            return names[i]
    return "ambiguous"


def _collect_edges(root_ctx: Context, by_id: dict[str, Context]) -> list[dict[str, str]]:
    """Cycle-safe DFS over dependencies → edges only (no read-set expansion)."""
    edges: list[dict[str, str]] = []
    visited: set[str] = set()

    def visit(ctx: Context) -> None:
        if ctx.id in visited:
            return
        visited.add(ctx.id)
        for dep_id in ctx.dependencies:
            dep = by_id.get(dep_id)
            if dep is None:
                continue
            edges.append({"from": ctx.id, "to": dep_id})
            visit(dep)

    visit(root_ctx)
    return edges


def _resolve(contexts: list[Context], by_id: dict[str, Context], *,
             path: str | None, ctx_id: str | None,
             phase: str | None) -> tuple[Context | None, str, list[Candidate]]:
    """Select the governing context. Returns (context|None, status, candidates)."""
    if ctx_id is not None:
        ctx = by_id.get(ctx_id)
        if ctx is None:
            return None, S_NO_MATCH, []
        return ctx, S_RESOLVED, [(ctx, ctx.match[0] if ctx.match else "", (0, 0, 0))]
    assert path is not None
    cands = _candidates_for_path(contexts, path)
    if not cands:
        return None, S_NO_MATCH, []
    if len(cands) >= 2 and cands[0][2] == cands[1][2]:
        return None, S_AMBIGUOUS, cands
    return cands[0][0], S_RESOLVED, cands


# ---------------------------------------------------------------------------
# Command functions (called by the CLI layer)
# ---------------------------------------------------------------------------


def _invalid_map_result(command: str, vr: ValidateResult) -> CommandResult:
    """Map a non-resolvable validate state onto a command result."""
    if vr.status == S_NO_MAP:
        return CommandResult(command, S_NO_MAP, "context: no map present")
    n = len(vr.diagnostics)
    human = f"{command}: {vr.status} ({n} issue{'s' if n != 1 else ''})\n" + "\n".join(
        f"  - [{d['code']}] {d['message']}" for d in vr.diagnostics
    )
    return CommandResult(command, vr.status, human, {"diagnostics": vr.diagnostics})


def cmd_init(root: Path) -> CommandResult:
    """Create the starter map when absent; idempotent, atomic (FR-003)."""
    if not (root / ".specify").is_dir():
        return CommandResult("init", S_USAGE_ERROR,
                             "context init: not a Spec Kit repository (.specify/ missing)")
    p = map_path(root)
    if p.exists():
        return CommandResult("init", S_ALREADY_EXISTS,
                             f"context init: map already exists at {p}", {"path": str(p)})
    try:
        template = _TEMPLATE.read_text(encoding="utf-8")
    except OSError as exc:
        return CommandResult("init", S_USAGE_ERROR,
                             f"context init: bundled template unavailable ({exc})")
    p.parent.mkdir(parents=True, exist_ok=True)
    ledger.atomic_write(p, template)
    return CommandResult("init", S_CREATED, f"context init: created {p}", {"path": str(p)})


def cmd_validate(root: Path) -> CommandResult:
    """Validate the map; report all defects in one pass (FR-004/FR-005)."""
    vr = validate(root)
    if vr.status in (S_MALFORMED, S_SCHEMA_INVALID, S_UNSUPPORTED_VERSION, S_NO_MAP):
        return _invalid_map_result("validate", vr)
    count = len(vr.contexts or [])
    plural = "s" if count != 1 else ""
    human = f"validate: {vr.status} ({count} context{plural}, schema v{CURRENT_SCHEMA})"
    return CommandResult("validate", vr.status, human,
                         {"context_count": count, "schema_version": CURRENT_SCHEMA})


# Map states from which a path/id can be resolved (everything else fails closed).
_RESOLVABLE = (S_VALID, S_EMPTY_VALID)


def _input_error(command: str, path: str | None, ctx_id: str | None,
                 phase: str | None) -> CommandResult | None:
    """Validate the resolve/explain input contract: one selector, a known phase."""
    if (path is None) == (ctx_id is None):
        return CommandResult(command, S_USAGE_ERROR,
                             f"context {command}: provide exactly one of --path or --id")
    if phase is not None and phase not in PHASES:
        return CommandResult(command, S_USAGE_ERROR,
                             f"context {command}: unknown phase {phase!r} "
                             f"(valid: {', '.join(PHASES)})")
    return None


def cmd_resolve(root: Path, *, path: str | None, ctx_id: str | None,
                phase: str | None) -> CommandResult:
    err = _input_error("resolve", path, ctx_id, phase)
    if err is not None:
        return err
    vr = validate(root)
    if vr.status not in _RESOLVABLE:
        return _invalid_map_result("resolve", vr)
    contexts = vr.contexts or []
    by_id = {c.id: c for c in contexts}
    ctx, status, _cands = _resolve(contexts, by_id, path=path, ctx_id=ctx_id, phase=phase)
    if status == S_AMBIGUOUS:
        return CommandResult("resolve", S_AMBIGUOUS,
                             f"resolve: ambiguous ownership for path {path!r}")
    if ctx is None:
        return CommandResult("resolve", S_NO_MATCH, "resolve: no matching context")
    read_set, source = _read_set_for(ctx, phase)
    expanded, edges = _build_expanded(ctx, by_id, phase)
    package = {
        "context_id": ctx.id,
        "phase": phase,
        "read_set": read_set,
        "read_set_source": source,
        "dependencies": list(ctx.dependencies),
        "expanded_read_set": expanded,
        "gates": list(ctx.gates),
        "risk": dict(ctx.risk),
    }
    return CommandResult("resolve", S_RESOLVED, f"resolve: {ctx.id}", {"package": package})


def cmd_explain(root: Path, *, path: str | None, ctx_id: str | None,
                phase: str | None) -> CommandResult:
    err = _input_error("explain", path, ctx_id, phase)
    if err is not None:
        return err
    vr = validate(root)
    if vr.status not in _RESOLVABLE:
        return _invalid_map_result("explain", vr)
    contexts = vr.contexts or []
    by_id = {c.id: c for c in contexts}
    ctx, status, cands = _resolve(contexts, by_id, path=path, ctx_id=ctx_id, phase=phase)
    if status == S_AMBIGUOUS:
        return CommandResult("explain", S_AMBIGUOUS,
                             f"explain: ambiguous ownership for path {path!r}")
    if ctx is None:
        return CommandResult("explain", S_NO_MATCH, "explain: no matching context",
                             {"trace": {"input": _input_of(path, ctx_id), "candidates": []}})
    _reads, source = _read_set_for(ctx, phase)
    edges = _collect_edges(ctx, by_id)
    trace = {
        "input": _input_of(path, ctx_id),
        "candidates": [
            {"context_id": c.id, "pattern": pat,
             "specificity": {"literal_prefix": spec[0], "wildcards": -spec[1],
                             "segments": spec[2]}}
            for (c, pat, spec) in cands
        ],
        "selected": {"context_id": ctx.id,
                     "deciding_dimension": _deciding_dimension(cands) if path is not None
                     else "by_id"},
        "read_set_source": source,
        "dependency_edges": edges,
        "gates": list(ctx.gates),
    }
    return CommandResult("explain", S_RESOLVED, f"explain: {ctx.id}", {"trace": trace})


def _input_of(path: str | None, ctx_id: str | None) -> dict[str, str]:
    return {"path": path} if path is not None else {"id": ctx_id or ""}


# ---------------------------------------------------------------------------
# Feature 009 — Context-Aware Planning and Impact (consumption layer)
# ---------------------------------------------------------------------------


def _digest_contexts(contexts: list[Context]) -> str:
    """Deterministic sha256 over the canonicalized parsed map (R1).

    Invariant to comment/whitespace/key-order in the source file: only the map's
    *meaning* (ids, patterns, read sets, edges, gates, risk) changes the digest.
    """
    canon = [
        {
            "id": c.id,
            "match": sorted(c.match),
            "reads": {k: sorted(v) for k, v in sorted(c.reads.items())},
            "dependencies": sorted(c.dependencies),
            "gates": sorted(c.gates),
            "risk": {k: c.risk[k] for k in sorted(c.risk)},
        }
        for c in sorted(contexts, key=lambda c: c.id)
    ]
    blob = _json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def map_digest(root: Path) -> str | None:
    """Return the deterministic digest of a resolvable map, else None (R1).

    None means the map is absent OR unresolvable (malformed/invalid/unsupported);
    callers that must distinguish those use :func:`validate` or
    :func:`provenance_for`.
    """
    vr = validate(root)
    if vr.status not in _RESOLVABLE:
        return None
    return _digest_contexts(vr.contexts or [])


def _reverse_adjacency(contexts: list[Context]) -> dict[str, list[str]]:
    """Map each context id → the ids that declare a dependency *on* it (R2)."""
    dependents: dict[str, list[str]] = {}
    for ctx in contexts:
        for dep in ctx.dependencies:
            dependents.setdefault(dep, []).append(ctx.id)
    return dependents


def _is_catch_all(pattern: str) -> bool:
    """True only for a whole-tree wildcard (every segment is ``*`` or ``**``) (R3).

    A pattern with any literal segment — e.g. ``**/config.yaml`` or ``**/*.py`` —
    is a specific selector, not a catch-all, and must not trigger the
    unbounded-expansion guard.
    """
    segs = [s for s in pattern.split("/") if s]
    return bool(segs) and all(s in ("*", "**") for s in segs)


def _owner_of(contexts: list[Context], path: str) -> tuple[Context | None, str | None]:
    """Return (owner, pattern) for *path*'s most-specific **unambiguous** owner.

    Returns (None, None) when *path* matches no context, or when the top two
    candidates tie on specificity (a residual ambiguity `validate`'s witness
    probe may miss) — impact/provenance never silently guess an owner, matching
    the fail-safe stance of `_resolve`/`cmd_plan_check`.
    """
    cands = _candidates_for_path(contexts, path)
    if not cands:
        return None, None
    if len(cands) >= 2 and cands[0][2] == cands[1][2]:
        return None, None
    return cands[0][0], cands[0][1]


def _owning_context_ids(contexts: list[Context], changed_paths: list[str]) -> list[str]:
    """Return the sorted ids of the contexts that directly **own** *changed_paths*.

    This is what a task/review record's provenance captures — the contexts the
    diff actually touches — NOT the reverse-dependent expansion `cmd_impact`
    surfaces for review scoping (which would over-report contexts the change did
    not modify).
    """
    ids: set[str] = set()
    for path in set(changed_paths):
        owner, _pat = _owner_of(contexts, path)
        if owner is not None:
            ids.add(owner.id)
    return sorted(ids)


def _affected(contexts: list[Context], changed_paths: list[str]) -> dict[str, Any]:
    """Reverse-edge impact core, cycle-safe (R2/R3).

    Returns {"affected": {id: {"via", "reason"}}, "unowned": [...],
    "unbounded": path|None}. Every affected context is attributed to exactly one
    closed-set edge (`ownership`/`dependency`); `policy` is enforced-but-empty
    against the current schema.
    """
    affected: dict[str, dict[str, str]] = {}
    unowned: list[str] = []
    for path in sorted(set(changed_paths)):
        owner, pat = _owner_of(contexts, path)
        if owner is None:
            unowned.append(path)
            continue
        if pat is not None and _is_catch_all(pat):
            return {"affected": {}, "unowned": unowned, "unbounded": path}
        affected.setdefault(owner.id, {"via": "ownership", "reason": f"owns {path}"})

    dependents = _reverse_adjacency(contexts)
    seen: set[str] = set()
    for start in list(affected):
        stack = [start]
        while stack:
            cid = stack.pop()
            if cid in seen:
                continue
            seen.add(cid)
            for dependent in sorted(dependents.get(cid, [])):
                if dependent not in affected:
                    affected[dependent] = {"via": "dependency",
                                           "reason": f"dependency: {dependent} -> {cid}"}
                stack.append(dependent)
    return {"affected": affected, "unowned": unowned, "unbounded": None}


def cmd_impact(root: Path, *, paths: list[str]) -> CommandResult:
    """Report contexts affected by *paths*, expanded over reverse edges (FR-006)."""
    vr = validate(root)
    if vr.status == S_NO_MAP:
        return CommandResult("impact", S_NO_MAP, "context impact: no map present",
                             {"impact": {"changed_paths": sorted(set(paths)),
                                         "unowned_paths": [], "affected": [], "bounded": True}})
    if vr.status not in _RESOLVABLE:
        return _invalid_map_result("impact", vr)
    contexts = vr.contexts or []
    by_id = {c.id: c for c in contexts}
    result = _affected(contexts, paths)
    if result["unbounded"] is not None:
        pth = result["unbounded"]
        return CommandResult("impact", S_UNBOUNDED_EXPANSION,
                             f"impact: path {pth!r} resolves to a catch-all owner; "
                             "expansion would be unbounded", {"unbounded_path": pth})
    affected = [
        {"context_id": cid, "via": info["via"], "reason": info["reason"],
         "gates": list(by_id[cid].gates), "risk": dict(by_id[cid].risk)}
        for cid, info in sorted(result["affected"].items())
    ]
    impact = {
        "changed_paths": sorted(set(paths)),
        "unowned_paths": sorted(result["unowned"]),
        "affected": affected,
        "bounded": True,
    }
    return CommandResult("impact", S_IMPACT_OK,
                         f"impact: {len(affected)} affected context(s)", {"impact": impact})


def provenance_for(root: Path, changed_paths: list[str]) -> dict[str, Any]:
    """Compute the ledger context-provenance record for *changed_paths* (R6).

    `{map: none}` (absent), `{map: invalid}` (present but unresolvable), or
    `{map: present, digest, context_ids, output_version}` (resolvable). Never
    raises — recording provenance must not fail the underlying ledger op.
    """
    vr = validate(root)
    if vr.status == S_NO_MAP:
        return {"map": "none"}
    if vr.status not in _RESOLVABLE:
        return {"map": "invalid"}
    contexts = vr.contexts or []
    return {
        "map": "present",
        "digest": _digest_contexts(contexts),
        "context_ids": _owning_context_ids(contexts, changed_paths),
        "output_version": OUTPUT_VERSION,
    }


def cmd_stale(root: Path, tracked_files: list[str]) -> CommandResult:
    """Report context-map patterns matching zero *tracked_files* (FR-011).

    *tracked_files* is the Git-tracked path list (index/worktree); symlinks are
    listed by their own path (not followed) so results are deterministic.
    """
    vr = validate(root)
    if vr.status == S_NO_MAP:
        return CommandResult("stale", S_NO_MAP, "context stale: no map present", {"stale": []})
    if vr.status not in _RESOLVABLE:
        return _invalid_map_result("stale", vr)
    contexts = vr.contexts or []
    tracked = set(tracked_files)
    stale: list[dict[str, str]] = []
    for ctx in contexts:
        for pat in ctx.match:
            if not any(_matches(pat, f) for f in tracked):
                stale.append({"context_id": ctx.id, "pattern": pat})
    stale.sort(key=lambda s: (s["context_id"], s["pattern"]))
    if stale:
        human = f"stale: {len(stale)} stale reference(s)\n" + "\n".join(
            f"  - {s['context_id']}: {s['pattern']}" for s in stale
        )
        return CommandResult("stale", S_STALE_FOUND, human, {"stale": stale})
    return CommandResult("stale", S_STALE_OK, "stale: no stale references", {"stale": []})


def cmd_plan_check(root: Path, *, plan_text: str, phase: str | None = None) -> CommandResult:
    """Validate a plan's declared context topology against the map (FR-002/003/004).

    Existence-agnostic: never inspects the filesystem for declared paths.
    """
    phase = phase or "plan"
    if phase not in PHASES:
        return CommandResult("plan-check", S_USAGE_ERROR,
                             f"context plan-check: unknown phase {phase!r} "
                             f"(valid: {', '.join(PHASES)})")
    vr = validate(root)
    if vr.status == S_NO_MAP:
        return CommandResult("plan-check", S_NO_MAP,
                             "context plan-check: no map present (no declaration required)")
    if vr.status not in _RESOLVABLE:
        return _invalid_map_result("plan-check", vr)
    contexts = vr.contexts or []
    by_id = {c.id: c for c in contexts}

    declared_ids = speckit.parse_plan_context_ids(plan_text)
    if not declared_ids:
        return CommandResult("plan-check", S_MISSING_DECLARATION,
                             "context plan-check: a map is present but the plan declares no "
                             "context IDs (add a '**SpecOps-Contexts**: ...' line)")
    unknown = [cid for cid in declared_ids if cid not in by_id]
    if unknown:
        return CommandResult("plan-check", S_UNKNOWN_DECLARED_CONTEXT,
                             f"context plan-check: unknown declared context(s): "
                             f"{', '.join(unknown)}", {"unknown_context_ids": unknown})

    declared_set = set(declared_ids)
    declared_paths = [
        pa[0] for line in plan_text.splitlines()
        if (pa := speckit.parse_plan_path_action(line)) is not None
    ]
    unowned: list[str] = []
    undeclared: list[dict[str, str]] = []
    for path in declared_paths:
        cands = _candidates_for_path(contexts, path)
        if not cands:
            unowned.append(path)
            continue
        if len(cands) >= 2 and cands[0][2] == cands[1][2]:
            return CommandResult("plan-check", S_AMBIGUOUS,
                                 f"context plan-check: ambiguous ownership for declared "
                                 f"path {path!r}")
        owner = cands[0][0].id
        if owner not in declared_set:
            undeclared.append({"path": path, "context_id": owner})
    if undeclared:
        msg = "; ".join(f"{u['path']} owned by undeclared context {u['context_id']}"
                        for u in undeclared)
        return CommandResult("plan-check", S_UNDECLARED_OWNER,
                             f"context plan-check: {msg}",
                             {"undeclared_owners": undeclared, "unowned_paths": sorted(unowned)})

    read_sets = {}
    for cid in declared_ids:
        rs, src = _read_set_for(by_id[cid], phase)
        read_sets[cid] = {"read_set": rs, "read_set_source": src}
    extra = {
        "declared_context_ids": list(declared_ids),
        "unowned_paths": sorted(unowned),
        "phase": phase,
        "read_sets": read_sets,
    }
    return CommandResult("plan-check", S_PLAN_CHECK_OK,
                         f"plan-check: ok ({len(declared_ids)} declared context(s), phase {phase})",
                         extra)
