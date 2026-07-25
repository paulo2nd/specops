# Quickstart: Validating Internal Hardening

**Purpose**: runnable scenarios proving the consolidation happened and nothing user-visible changed. All commands run from the repo root, inside the `specops` conda env (`conda run -n specops …`). Everything operates on test fixtures — never run `specops` against this repository (No Self-Application).

## Prerequisites

```bash
conda run -n specops pip install -e ".[dev]"
git rev-parse HEAD   # note the baseline commit before any refactor lands
```

## 1. Golden capture (behavior freeze — SC-001, SC-006)

On the **baseline** commit, record the capture; after each story, re-diff:

```bash
conda run -n specops pytest tests/ -q                      # suite green before capture
# capture harness added by this feature (see contracts/cli-output.md):
conda run -n specops pytest tests/golden -q --golden-record   # baseline: record triples
# ... implement a story ...
conda run -n specops pytest tests/golden -q                   # replay: diff against recorded
```

**Expected**: replay passes with zero diffs, except (a) lane `--json` gaining `output_version` + `status`, and (b) the two enumerated invalid-ledger convergences — both asserted explicitly by the harness, not waived.

## 2. Cross-module privacy scan (SC-002)

```bash
python3 - <<'EOF'
import re, pathlib
src = pathlib.Path("src/specops"); mods = {p.stem for p in src.glob("*.py")}
bad = [(p.name, i, m.group(0))
       for p in sorted(src.glob("*.py"))
       for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
       for m in re.finditer(r'\b([a-z_][a-z0-9_]*)\.(_[A-Za-z_][A-Za-z0-9_]*)\b', line)
       if m.group(1) in mods and m.group(1) != p.stem and not m.group(2).startswith("__")]
print(f"{len(bad)} cross-module private references"); [print(" ", *b) for b in bad]
EOF
```

**Expected**: `0 cross-module private references` (baseline: 39).

## 3. Single-definition scan (SC-003)

```bash
grep -rn "def _emit" src/specops/cli.py                    # expect: _emit (+ _emit_sarif only)
grep -rn "class TraceResult\|class HandoffResult" src/     # expect: subclass one-liners only, no duplicated bodies
grep -rn "def _git(" tests/                                # expect: exactly 1 hit (conftest.py)
grep -rn "def _make_ledger" tests/                         # expect: 0 hits
grep -rn "_FINDING_RE\|EVIDENCE_CLASSES" src/specops/ --include="*.py" -l
# expect: findings.py / evidence.py as sole definition homes (consumers import, never redefine)
```

## 4. Ledger diagnostic convergence (SC-004)

```bash
conda run -n specops pytest tests/ -q -k "ledger and (parse or corrupt or invalid)"
```

**Expected**: the tests added by this feature assert `status show`, `status report`, and `reconcile` emit the identical `load_raw` diagnostic with exit code 2 on the same corrupted fixture; the non-mapping-task fixture renders (filtered) in both `show` and `report`.

## 5. Suite health and speed (SC-005)

```bash
time conda run -n specops pytest tests/ -q                          # compare against baseline timing
conda run -n specops pytest tests/ -q -m subprocess                 # smoke set: real binary, real streams
conda run -n specops pytest tests/ -q --cov=specops --cov-fail-under=85
conda run -n specops ruff check . && conda run -n specops mypy src/
```

**Expected**: integration portion ≥30% faster than the baseline `time` (record both in the PR description); the `subprocess`-marked smoke set exists, is small (~one command per family), and passes; coverage floor and lint/type gates green.

## 6. Round-trip guarantee (FR-009)

```bash
conda run -n specops pytest tests/ -q -k "round_trip and finding"
```

**Expected**: render→parse round-trip test over representative findings (with and without `line`) passes from the co-located pair in `findings.py`.

## References

- Behavior freeze details: [contracts/cli-output.md](./contracts/cli-output.md)
- Name mapping and obligations: [contracts/internal-api.md](./contracts/internal-api.md)
- Shapes and grammars: [data-model.md](./data-model.md)
