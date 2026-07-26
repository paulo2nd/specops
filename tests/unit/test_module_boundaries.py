"""Module boundaries are explicit contracts (Feature 018 US2, SC-002).

After the promotion sweep, no module in ``src/specops/`` may reach across a module
boundary to an underscore-prefixed name of another module: every cross-module
consumer imports a documented public name (contracts/internal-api.md). This scan is
the enforcement gate — it fails while any cross-module private reference remains
(baseline: 38 at the branch tip).

Same-module private use, dunders (``__init__`` …), and a module's own privates are
allowed; only ``other_module._private`` is a defect.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "specops"
_REF = re.compile(r"\b([a-z_][a-z0-9_]*)\.(_[A-Za-z_][A-Za-z0-9_]*)\b")


def _cross_module_private_refs() -> list[tuple[str, int, str]]:
    modules = {p.stem for p in SRC.glob("*.py")}
    bad: list[tuple[str, int, str]] = []
    for p in sorted(SRC.glob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            for m in _REF.finditer(line):
                qualifier, attr = m.group(1), m.group(2)
                if qualifier in modules and qualifier != p.stem and not attr.startswith("__"):
                    bad.append((p.name, i, m.group(0)))
    return bad


def test_no_cross_module_private_references() -> None:
    bad = _cross_module_private_refs()
    detail = "\n".join(f"  {name}:{line} {ref}" for name, line, ref in bad)
    assert not bad, f"{len(bad)} cross-module private reference(s) remain:\n{detail}"
