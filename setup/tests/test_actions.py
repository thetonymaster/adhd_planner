import json
from dataclasses import replace
from pathlib import Path

from planner_setup import actions, paths


def text(ctx):
    return "\n".join(ctx.lines)


def test_vault_path_resolution(tmp_path):
    assert paths.vault({}, tmp_path) == tmp_path / "vault"
    assert paths.vault({"VAULT": "~/notes"}, tmp_path) == tmp_path / "notes"


def test_marketplace_source_prefers_checkout(tmp_path):
    assert paths.marketplace_source(tmp_path) == "thetonymaster/adhd_planner"
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text('{"name": "adhd-planner"}')
    assert paths.marketplace_source(tmp_path) == str(tmp_path)


def test_examples_dir_has_the_starter():
    assert (paths.examples() / "vault-starter" / "Tasks" / "set-up-vault.md").is_file()


def test_status_reports_everything_missing(ctx, fake_claude):
    assert actions.status(ctx) == 0
    out = text(ctx)
    assert "marketplace adhd-planner: not added" in out
    for p in ("planner", "tasks", "task-track"):
        assert f"{p}: not installed" in out
    assert "vault: " in out and "missing" in out


def test_status_reads_installed_state(ctx, fake_claude):
    fake_claude.reply("plugin_marketplace_list", out=json.dumps([{"name": "adhd-planner"}]))
    fake_claude.reply("plugin_list", out=json.dumps([
        {"id": "tasks@adhd-planner", "enabled": True},
        {"id": "planner@adhd-planner", "enabled": False}]))
    actions.status(ctx)
    out = text(ctx)
    assert "marketplace adhd-planner: added" in out
    assert "tasks: enabled" in out and "planner: installed, disabled" in out


def test_install_adds_marketplace_then_plugins(ctx, fake_claude):
    assert actions.install(ctx, ["planner", "tasks"]) == 0
    calls = fake_claude.calls()
    assert ["plugin", "marketplace", "add", "thetonymaster/adhd_planner"] in calls
    assert ["plugin", "install", "planner@adhd-planner"] in calls
    assert ["plugin", "install", "tasks@adhd-planner"] in calls
    assert ["plugin", "install", "task-track@adhd-planner"] not in calls


def test_install_skips_what_is_already_there(ctx, fake_claude):
    fake_claude.reply("plugin_marketplace_list", out=json.dumps([{"name": "adhd-planner"}]))
    fake_claude.reply("plugin_list", out=json.dumps([{"id": "tasks@adhd-planner", "enabled": True}]))
    actions.install(ctx, ["tasks"])
    assert not any(c[:2] == ["plugin", "install"] or c[:3] == ["plugin", "marketplace", "add"]
                   for c in fake_claude.calls())


def test_install_surfaces_claude_stderr_and_stops(ctx, fake_claude):
    fake_claude.reply("plugin_marketplace_add_thetonymaster_adhd_planner", err="auth required", code=1)
    assert actions.install(ctx, ["planner"]) == 1
    assert "auth required" in text(ctx)
    assert ["plugin", "install", "planner@adhd-planner"] not in fake_claude.calls()


def test_install_without_claude_says_so(ctx, monkeypatch):
    monkeypatch.setenv("PATH", "/nonexistent")
    assert actions.install(ctx, ["planner"]) == 1
    assert "claude: not found on PATH" in text(ctx)


def test_configure_writes_settings_with_backup(ctx):
    settings = ctx.home / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"model": "opus"}')
    assert actions.configure(ctx, ctx.home / "vault", permissions=True) == 0
    data = json.loads(settings.read_text())
    assert data["model"] == "opus"
    assert data["pluginConfigs"]["tasks@adhd-planner"]["options"]["vaultPath"] == str(ctx.home / "vault")
    assert list((ctx.home / ".claude" / "backups").glob("*/.claude/settings.json"))


def test_configure_dry_run_writes_nothing(ctx):
    c = replace(ctx, dry_run=True)
    c.lines = ctx.lines
    actions.configure(c, ctx.home / "vault", permissions=False)
    assert not (ctx.home / ".claude" / "settings.json").exists()
    assert "would change" in text(ctx).lower()


def test_configure_declined_writes_nothing(ctx):
    c = replace(ctx, yes=False, confirm=lambda _q: False)
    c.lines = ctx.lines
    assert actions.configure(c, ctx.home / "vault", permissions=False) == 1
    assert not (ctx.home / ".claude" / "settings.json").exists()


def test_configure_twice_makes_one_backup_at_most(ctx):
    actions.configure(ctx, ctx.home / "vault", permissions=False)
    actions.configure(ctx, ctx.home / "vault", permissions=False)
    assert "nothing to change" in text(ctx).lower()
    assert not (ctx.home / ".claude" / "backups").exists()  # first write had no file to back up


def test_seed_vault_copies_once(ctx):
    v = ctx.home / "vault"
    assert actions.seed_vault(ctx, v) == 0
    assert (v / "Tasks" / "set-up-vault.md").is_file()
    assert (v / ".claude" / "CLAUDE.md").is_file() and not (v / "_claude").exists()
    (v / "Tasks" / "set-up-vault.md").write_text("mine")
    assert actions.seed_vault(ctx, v) == 0
    assert (v / "Tasks" / "set-up-vault.md").read_text() == "mine"
    assert "already exists" in text(ctx)


def test_claude_md_never_overwrites(ctx):
    target = ctx.home / ".claude" / "CLAUDE.md"
    assert actions.claude_md(ctx) == 0 and target.read_text().startswith("> Example")
    target.write_text("Q's own")
    actions.claude_md(ctx)
    assert target.read_text() == "Q's own"
    assert "kept your" in text(ctx)


def test_cowork_prints_the_steps(ctx):
    actions.cowork(ctx)
    assert "thetonymaster/adhd_planner" in text(ctx)


def test_status_expands_tilde_vault_and_dirs(ctx):
    (ctx.home / "vault").mkdir()
    settings = ctx.home / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps({
        "pluginConfigs": {"tasks@adhd-planner": {"options": {"vaultPath": "~/vault"}}},
        "permissions": {"additionalDirectories": ["~/vault/"]}}))
    actions.status(ctx)
    out = text(ctx)
    assert f"vault: {ctx.home / 'vault'} (exists; from settings)" in out
    assert "vault in additionalDirectories: yes (not needed; edits there may skip the tasks hook's write rules: consider removing it)" in out


def test_status_with_wrong_typed_settings_names_the_key(ctx):
    for bad in ({"pluginConfigs": []}, {"pluginConfigs": {"tasks@adhd-planner": {"options": None}}},
                {"permissions": "x"}):
        ctx.settings_path.parent.mkdir(parents=True, exist_ok=True)
        ctx.settings_path.write_text(json.dumps(bad))
        try:
            actions.status(ctx)
        except SystemExit as err:
            assert "expected a" in str(err) and "nothing was changed" in str(err)
        else:
            raise AssertionError(f"status accepted {bad}")


def test_claude_timeout_is_a_failed_result(monkeypatch):
    import subprocess
    from planner_setup import claude_cli

    def hang(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=300)
    monkeypatch.setattr(subprocess, "run", hang)
    r = claude_cli.run("plugin", "list")
    assert r.code != 0 and "timed out" in r.err


def vaults_json(ctx):
    return ctx.home / ".config" / "adhd-planner" / "vaults.json"


def test_add_vault_creates_the_file_with_the_current_vault_as_default(ctx):
    work = ctx.home / "work-vault"
    (work / "Tasks").mkdir(parents=True)
    assert actions.add_vault(ctx, "work", work, ["~/acme"]) == 0
    assert json.loads(vaults_json(ctx).read_text()) == {
        "default": "personal",
        "vaults": {"personal": {"path": "~/vault"}, "work": {"path": "~/work-vault", "folders": ["~/acme"]}},
    }


def test_add_vault_merges_and_keeps_every_existing_entry(ctx):
    vaults_json(ctx).parent.mkdir(parents=True)
    vaults_json(ctx).write_text(json.dumps({"default": "home", "vaults": {"home": {"path": "~/vault"}, "side": {"path": "/s"}}}))
    assert actions.add_vault(ctx, "work", ctx.home / "w", []) == 0
    data = json.loads(vaults_json(ctx).read_text())
    assert data["default"] == "home"
    assert list(data["vaults"]) == ["home", "side", "work"]
    assert data["vaults"]["work"] == {"path": "~/w"}


def test_add_vault_refuses_a_taken_or_bad_name_and_changes_nothing(ctx):
    assert actions.add_vault(ctx, "Work", ctx.home / "w", []) == 2
    assert not vaults_json(ctx).exists()
    assert actions.add_vault(ctx, "personal", ctx.home / "w", []) == 1
    assert not vaults_json(ctx).exists()
    assert "already has a vault named 'personal'" in text(ctx)


def test_add_vault_dry_run_writes_nothing(ctx):
    assert actions.add_vault(replace(ctx, dry_run=True), "work", ctx.home / "w", []) == 0
    assert not vaults_json(ctx).exists()
    assert "Would write" in text(ctx)


def test_add_vault_warns_when_the_vault_has_no_tasks_folder(ctx):
    assert actions.add_vault(ctx, "work", ctx.home / "w", []) == 0
    assert "has no Tasks/ yet" in text(ctx)


def test_the_written_file_parses_with_the_hook_parser(ctx):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins" / "tasks" / "hooks"))
    import vaults
    actions.add_vault(ctx, "work", ctx.home / "w", ["~/acme"])
    config = vaults.parse(vaults_json(ctx).read_text(), "vaults.json", {}, str(ctx.home))
    assert config.error == ""
    assert [v.name for v in config.vaults] == ["personal", "work"]


def test_add_vault_seeds_the_vault_path_from_settings(ctx):
    ctx.settings_path.parent.mkdir(parents=True)
    ctx.settings_path.write_text(json.dumps(
        {"pluginConfigs": {"tasks@adhd-planner": {"options": {"vaultPath": str(ctx.home / "Notes" / "main")}}}}))
    assert actions.add_vault(ctx, "work", ctx.home / "w", []) == 0
    data = json.loads(vaults_json(ctx).read_text())
    assert data["vaults"]["personal"] == {"path": "~/Notes/main"}
    assert data["default"] == "personal"


def test_add_vault_writes_relative_folders_as_absolute(ctx):
    assert actions.add_vault(replace(ctx, cwd=ctx.home / "code"), "work", ctx.home / "w", ["api", "~/acme/"]) == 0
    assert json.loads(vaults_json(ctx).read_text())["vaults"]["work"]["folders"] == ["~/code/api", "~/acme"]


def test_add_vault_refuses_a_folder_another_vault_lists_and_changes_nothing(ctx):
    vaults_json(ctx).parent.mkdir(parents=True)
    before = json.dumps({"default": "home", "vaults": {"home": {"path": "~/vault", "folders": ["~/acme"]}}})
    vaults_json(ctx).write_text(before)
    assert actions.add_vault(ctx, "work", ctx.home / "w", [str(ctx.home / "acme")]) == 1
    assert vaults_json(ctx).read_text() == before
    assert "already in 'home'" in text(ctx)


def test_add_vault_seeds_a_relative_vault_env_as_absolute(ctx):
    assert actions.add_vault(replace(ctx, env={"VAULT": "notes"}), "work", ctx.home / "w", []) == 0
    assert json.loads(vaults_json(ctx).read_text())["vaults"]["personal"] == {"path": str(ctx.cwd / "notes")}


def test_add_vault_expands_tilde_in_the_env_file_and_refuses_a_relative_one(ctx):
    assert actions.add_vault(replace(ctx, env={"ADHD_PLANNER_VAULTS": "~/v.json"}), "work", ctx.home / "w", []) == 0
    assert (ctx.home / "v.json").exists()
    assert actions.add_vault(replace(ctx, env={"ADHD_PLANNER_VAULTS": "v.json"}), "work", ctx.home / "w", []) == 2
    assert not (ctx.cwd / "v.json").exists()
    assert "must be an absolute path or start with ~/" in text(ctx)


def test_add_vault_sets_the_default_when_a_one_vault_file_has_none(ctx):
    vaults_json(ctx).parent.mkdir(parents=True)
    vaults_json(ctx).write_text(json.dumps({"vaults": {"home": {"path": "~/vault"}}}))
    assert actions.add_vault(ctx, "work", ctx.home / "w", []) == 0
    assert json.loads(vaults_json(ctx).read_text())["default"] == "home"
