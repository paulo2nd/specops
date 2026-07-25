# Data Model: Internal Hardening

**Date**: 2026-07-25 · **Inputs**: [spec.md](./spec.md) · [research.md](./research.md)

No persisted schema changes: the ledger stays at **v7**, `lane.yaml`, `specops.json`, and all serialized formats are untouched. The entities below are *in-memory shapes and grammars* whose definition sites are being consolidated; "fields" describe the contract each single owner must preserve.

## CommandResult (canonical, `outcome.py`)

The uniform outcome of a CLI invocation. Already canonical for contextmap/doctor/gateprofiles; trace and handoff join it (D1).

| Field | Type | Notes |
|---|---|---|
| `command` | str | fully-qualified subcommand name (e.g. `handoff finding add`) |
| `status` | str | module-local status token |
| `human` | str | human-mode text (byte-frozen by FR-003) |
| `extra` | mapping | family-specific JSON payload fields |
| `_CLASS_MAP` | ClassVar mapping | status → outcome class; each subclass carries exactly its family's map (moved unchanged from the module-level `_CLASS_FOR_STATUS`) |
| `cls` (derived) | str | `_CLASS_MAP[status]` |
| `exit_code` (derived) | int | `outcome.exit_for(cls)` — the Principle VI gate value, unchanged |

**Validation rules**: every status a family can produce MUST have a `_CLASS_MAP` entry (existing behavior — `KeyError` here is a programming error, not a runtime path). Subclasses add no fields.

## Output envelope (JSON mode, emitted by the unified `_emit`)

| Field | Type | Notes |
|---|---|---|
| `output_version` | str | the family module's `OUTPUT_VERSION` constant, passed by the caller |
| `command` | str | from the result |
| `status` | str | from the result |
| *payload* | — | the result's `extra` fields, spread at top level exactly as today |

**State transition (the one sanctioned delta)**: lane JSON currently omits `output_version` and `status`; after unification it includes both. Additive only — no field is removed or renamed in any family. Human mode is out of scope for the envelope (plain lines, unchanged).

## FindingRecord (base shape, factory in `findings.py`)

Single factory `new_finding(...)` produces the base shape stored in the ledger's findings list (serialized form unchanged — same keys, same defaults as the three current construction sites, whose common subset is authoritative):

| Field | Type | Notes |
|---|---|---|
| `id` | str | stable `R<round>-F<NN>` |
| `severity` | str | `blocking` \| `advisory` |
| `rule` | str | violated rule label |
| `file` | str | normalized repo-relative path |
| `line` | int \| null | optional location |
| `action` | str | concise corrective action |
| `status` | str | lifecycle: `OPEN → FIXED → VERIFIED` (+ `DISMISSED`); transitions owned by handoff commands, unchanged |
| `expected_evidence`, `closure_criteria` | str | per-finding closure contract |
| bookkeeping fields | — | remaining keys of the current literal (task/commit/evidence linkage), defaults identical to today |

**Layered extensions** (import paths only, via factory kwargs): `imported`, `producer`, `reviewed_digest`. The base shape MUST NOT differ between authoring, import-preview, and import-apply paths (FR-008).

## Finding line (grammar, co-located in `findings.py`)

Textual projection used by revision rendering and import parsing:

```
<file>[:<line>] - <action>
```

**Validation rule**: `parse_finding_line(format_finding_line(f))` is lossless for every valid finding (FR-009, round-trip test). Parse regex and renderer live side by side; `trace` and `handoff` consume, never redefine.

## Evidence string (grammar, owned by `evidence.py`)

```
<CLASS>:<summary>[; <CLASS>:<summary> ...]
```

- `CLASS` ∈ the existing `EVIDENCE_CLASSES` set (moved, not changed).
- `evidence.validate_string` (promoted from `status._validate_evidence`) and the existing `evidence.parse_legacy_string` are the only validation/parsing entry points; task-close (`status`) and finding-close (`handoff`) consume identically (FR-007).

## Ledger document (read contract)

Unchanged v7 schema. The consolidation is about *access*:

- `ledger.load_raw` is the single loading routine — existence, YAML parse, and mapping-shape diagnostics (`LedgerParseError`, exit 2) live only there (FR-005, SC-004).
- `status.compact_status` is the single snapshot/counting logic; `cmd_show` renders from it, adopting its tolerant filtering of non-mapping task entries (FR-006).
- Write-side helpers promoted to public names (`status.load_for_write`, `status.finalize`, `ledger.ledger_path`) keep their exact semantics — promotion is a rename plus a documented contract, never a behavior change.

## Relationships

```
outcome.CommandResult ◄─ subclass ── contextmap / doctor / gateprofiles (existing)
                      ◄─ subclass ── trace / handoff (this feature)
cli._emit ── consumes ──► CommandResult + OUTPUT_VERSION (all five families)
findings.new_finding ── produces ──► FindingRecord (stored in ledger, schema unchanged)
findings.parse/format ◄─ consumed by ── handoff (render/import), trace (classification)
evidence.validate_string ◄─ consumed by ── status (task close), handoff (finding close)
ledger.load_raw ◄─ sole reader ── status.cmd_show / status report / reconcile
```
