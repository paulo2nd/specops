"""Integration tests for the native extension lifecycle (Feature 005, US1)."""
from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from specops import compat, extension
from specops.cli import app

runner = CliRunner()


def _host_hashes(root: Path) -> dict[str, str]:
    """SHA256 of every host-owned speckit prompt file (never the SpecOps ones)."""
    out: dict[str, str] = {}
    for p in sorted(root.glob(".claude/skills/speckit-*/SKILL.md")):
        out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def _manifest(root: Path) -> dict:
    return yaml.safe_load((root / ".specify" / "extensions.yml").read_text())


@pytest.fixture()
def compat_ok(monkeypatch):
    """Pin the CLI-compat gate to satisfied, independent of the ambient install."""
    monkeypatch.setattr(compat, "installed_version", lambda: compat.MIN_CLI_VERSION)


# --- T010: clean install registers hooks + command, zero host modification ---

def test_install_registers_and_leaves_host_untouched(fake_speckit_repo, compat_ok):
    root = fake_speckit_repo
    before = _host_hashes(root)

    assert extension.install(root) == "created"

    data = _manifest(root)
    assert set(data["hooks"]) == {
        "after_specify", "before_plan", "after_tasks", "after_implement"
    }
    assert any(c["id"] == "specops-review" for c in data["commands"])
    assert (root / ".claude" / "skills" / "specops-review" / "SKILL.md").is_file()
    # zero host-owned files modified (SC-001)
    assert _host_hashes(root) == before


# --- T011: idempotent, semantic no-op on re-run ---

def test_install_is_idempotent(fake_speckit_repo, compat_ok):
    root = fake_speckit_repo
    assert extension.install(root) == "created"
    assert extension.install(root) == "unchanged"

    data = _manifest(root)
    for entries in data["hooks"].values():
        specops = [e for e in entries if e["extension"] == "specops"]
        assert len(specops) == 1  # no duplicate hook entries
    specops_cmds = [c for c in data["commands"] if c["extension"] == "specops"]
    assert len(specops_cmds) == 1  # no duplicate command registration


# --- T012: works offline ---

def test_install_offline(fake_speckit_repo, compat_ok, monkeypatch):
    def _no_network(*args, **kwargs):
        raise RuntimeError("network disabled")

    monkeypatch.setattr(socket, "socket", _no_network)
    assert extension.install(fake_speckit_repo) == "created"


# --- T013: one command registration per installed integration ---

def test_install_registers_every_integration(fake_speckit_repo, compat_ok):
    root = fake_speckit_repo
    # Add a second integration 'gemini' (separator '-', different command dir).
    integ = json.loads((root / ".specify" / "integration.json").read_text())
    integ["installed_integrations"].append("gemini")
    integ["integration_settings"]["gemini"] = {"invoke_separator": "-"}
    (root / ".specify" / "integration.json").write_text(json.dumps(integ))

    gdir = root / ".gemini" / "commands"
    gdir.mkdir(parents=True)
    gfiles = {}
    for role in ("specify", "plan", "tasks", "implement"):
        fp = gdir / f"speckit-{role}.md"
        fp.write_text(f"# gemini {role}\n")
        gfiles[str(fp.relative_to(root))] = "-"
    (root / ".specify" / "integrations" / "gemini.manifest.json").write_text(
        json.dumps({"integration": "gemini", "files": gfiles})
    )

    extension.install(root)

    data = _manifest(root)
    integrations = {c["integration"] for c in data["commands"] if c["extension"] == "specops"}
    assert integrations == {"claude", "gemini"}  # SC-006
    # hooks written once, integration-neutral
    assert len(data["hooks"]["before_plan"]) == 1
    assert (root / ".gemini" / "commands" / "specops-review.md").is_file()


# --- T014: fail-closed on missing/incompatible CLI, nothing written ---

def test_install_refuses_when_cli_older(fake_speckit_repo, monkeypatch):
    root = fake_speckit_repo
    monkeypatch.setattr(compat, "installed_version", lambda: "0.2.0")
    with pytest.raises(extension.ExtensionError) as exc:
        extension.install(root)
    assert "older" in str(exc.value)
    assert not (root / ".specify" / "extensions.yml").exists()
    assert not (root / ".claude" / "skills" / "specops-review").exists()


def test_install_refuses_when_cli_missing(fake_speckit_repo, monkeypatch):
    root = fake_speckit_repo
    monkeypatch.setattr(compat, "installed_version", lambda: None)
    with pytest.raises(extension.ExtensionError):
        extension.install(root)
    assert not (root / ".specify" / "extensions.yml").exists()


# --- CLI surface wiring (T008 status, T017 install) ---

def test_cli_extension_install_and_status(fake_speckit_repo, compat_ok, monkeypatch):
    root = fake_speckit_repo
    monkeypatch.chdir(root)

    res_install = runner.invoke(app, ["extension", "install"])
    assert res_install.exit_code == 0, res_install.output
    assert "extension install: created" in res_install.output

    res_status = runner.invoke(app, ["extension", "status"])
    assert res_status.exit_code == 0, res_status.output
    assert "installation: native" in res_status.output
