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
    assert "additionalDirectories" not in data["permissions"]
    assert data["permissions"]["allow"] == ["Bash(obsidian:*)"]


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


def test_add_vault_subcommand(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VAULT", raising=False)
    monkeypatch.delenv("ADHD_PLANNER_VAULTS", raising=False)
    assert cli.main(["--yes", "add-vault", "work", "--path", str(tmp_path / "w"), "--folder", "~/work"]) == 0
    data = json.loads((tmp_path / ".config" / "adhd-planner" / "vaults.json").read_text())
    assert data["vaults"]["work"] == {"path": "~/w", "folders": ["~/work"]}


def test_timezone_subcommand(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VAULT", raising=False)
    monkeypatch.delenv("ADHD_PLANNER_VAULTS", raising=False)
    assert cli.main(["--yes", "timezone", "America/Mexico_City"]) == 0
    data = json.loads((tmp_path / ".config" / "adhd-planner" / "vaults.json").read_text())
    assert data["timezone"] == "America/Mexico_City"


def test_timezone_subcommand_names_the_vault_it_creates(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VAULT", raising=False)
    monkeypatch.delenv("ADHD_PLANNER_VAULTS", raising=False)
    assert cli.main(["--yes", "timezone", "America/Mexico_City", "--existing-name", "vail"]) == 0
    data = json.loads((tmp_path / ".config" / "adhd-planner" / "vaults.json").read_text())
    assert data["default"] == "vail" and list(data["vaults"]) == ["vail"]


class _Scripted:
    """Stands in for questionary: each prompt pops the next answer, keyed by the prompt's text."""

    def __init__(self, answers):
        self.answers = answers
        self.asked = []

    def _prompt(self, message, *_, **__):
        self.asked.append(message)
        answer = self.answers[message].pop(0)
        return type("Q", (), {"ask": lambda _self: answer})()

    select = text = path = confirm = checkbox = _prompt


def _run_menu(monkeypatch, answers):
    import sys
    fake = _Scripted(answers)
    monkeypatch.setitem(sys.modules, "questionary", fake)
    assert cli._menu(cli._parser().parse_args(["--yes"])) == 0
    return fake


def test_menu_timezone_names_the_vault_it_creates(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VAULT", raising=False)
    monkeypatch.delenv("ADHD_PLANNER_VAULTS", raising=False)
    _run_menu(monkeypatch, {
        "planner-setup": ["Timezone", "Quit"],
        "IANA zone (e.g. America/Mexico_City)": ["America/Mexico_City"],
        "Name for this machine's vault (kebab-case)": ["vail"],
    })
    data = json.loads((tmp_path / ".config" / "adhd-planner" / "vaults.json").read_text())
    assert data["default"] == "vail" and list(data["vaults"]) == ["vail"]


def test_menu_add_vault_names_the_vault_it_creates(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VAULT", raising=False)
    monkeypatch.delenv("ADHD_PLANNER_VAULTS", raising=False)
    _run_menu(monkeypatch, {
        "planner-setup": ["Add another vault", "Quit"],
        "Name (kebab-case, e.g. work)": ["work"],
        "Vault path": [str(tmp_path / "w")],
        "Folders whose sessions use it (comma-separated, optional)": [""],
        "Name for this machine's vault (kebab-case)": ["vail"],
    })
    data = json.loads((tmp_path / ".config" / "adhd-planner" / "vaults.json").read_text())
    assert data["default"] == "vail" and set(data["vaults"]) == {"vail", "work"}


def test_menu_does_not_ask_the_name_once_vaults_json_exists(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VAULT", raising=False)
    monkeypatch.delenv("ADHD_PLANNER_VAULTS", raising=False)
    registry = tmp_path / ".config" / "adhd-planner" / "vaults.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({"default": "vail", "vaults": {"vail": {"path": "~/v"}}}))
    fake = _run_menu(monkeypatch, {
        "planner-setup": ["Timezone", "Quit"],
        "IANA zone (e.g. America/Mexico_City)": ["America/Mexico_City"],
    })
    assert "Name for this machine's vault (kebab-case)" not in fake.asked
    assert json.loads(registry.read_text())["timezone"] == "America/Mexico_City"


def test_menu_asks_the_name_when_vaults_json_has_no_vaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("VAULT", raising=False)
    monkeypatch.delenv("ADHD_PLANNER_VAULTS", raising=False)
    registry = tmp_path / ".config" / "adhd-planner" / "vaults.json"
    registry.parent.mkdir(parents=True)
    registry.write_text("{}")
    _run_menu(monkeypatch, {
        "planner-setup": ["Timezone", "Quit"],
        "IANA zone (e.g. America/Mexico_City)": ["America/Mexico_City"],
        "Name for this machine's vault (kebab-case)": ["vail"],
    })
    assert list(json.loads(registry.read_text())["vaults"]) == ["vail"]
