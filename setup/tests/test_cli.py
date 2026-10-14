import json

import pytest

from planner_setup import cli


def test_status_subcommand_runs(tmp_path, monkeypatch, fake_claude, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["status"]) == 0
    assert "marketplace adhd-planner" in capsys.readouterr().out


def test_settings_subcommand_with_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert cli.main(["--yes", "settings", "--vault", str(tmp_path / "v"), "--permissions"]) == 0
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert data["permissions"]["additionalDirectories"] == [str(tmp_path / "v")]


def test_install_defaults_to_all_plugins(tmp_path, monkeypatch, fake_claude):
    monkeypatch.setenv("HOME", str(tmp_path))
    cli.main(["--yes", "install"])
    installs = [c[2] for c in fake_claude.calls() if c[:2] == ["plugin", "install"]]
    assert installs == ["planner@adhd-planner", "tasks@adhd-planner", "task-track@adhd-planner"]


def test_unknown_plugin_is_rejected(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(SystemExit) as e:
        cli.main(["install", "--plugins", "nope"])
    assert e.value.code == 2
    assert "invalid choice: 'nope'" in capsys.readouterr().err


def test_invalid_settings_json_aborts_with_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{bad")
    try:
        cli.main(["--yes", "settings", "--vault", "/v"])
        raise AssertionError("expected SystemExit")
    except SystemExit as e:
        assert "settings.json is not valid JSON" in str(e.code)


def test_relative_vault_is_stored_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    assert cli.main(["--yes", "settings", "--vault", "v"]) == 0
    data = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    assert data["pluginConfigs"]["tasks@adhd-planner"]["options"]["vaultPath"] == str(tmp_path / "v")
