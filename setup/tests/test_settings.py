from planner_setup.settings import desired, merge


def test_desired_sets_vault_for_both_plugins_only():
    d = desired("/v", permissions=False)
    assert d == {"pluginConfigs": {
        "tasks@adhd-planner": {"options": {"vaultPath": "/v"}},
        "task-track@adhd-planner": {"options": {"vaultPath": "/v"}},
    }}


def test_desired_with_permissions():
    d = desired("/v", permissions=True)
    assert d["permissions"] == {"allow": ["Bash(obsidian:*)"]}


def test_merge_keeps_unrelated_keys():
    current = {
        "enabledPlugins": {"x@y": True},
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "say hi"}]}]},
        "permissions": {"allow": ["Bash(ls:*)"], "deny": ["Read(.env)"]},
        "pluginConfigs": {"tasks@adhd-planner": {"options": {"other": 1}}},
    }
    merged, changes = merge(current, desired("/v", permissions=True), home="/h")
    assert merged["enabledPlugins"] == {"x@y": True}
    assert merged["hooks"] == current["hooks"]
    assert merged["permissions"]["deny"] == ["Read(.env)"]
    assert merged["permissions"]["allow"] == ["Bash(ls:*)", "Bash(obsidian:*)"]
    assert merged["pluginConfigs"]["tasks@adhd-planner"]["options"] == {"other": 1, "vaultPath": "/v"}
    assert current["permissions"]["allow"] == ["Bash(ls:*)"]  # input untouched
    assert "permissions.allow: add Bash(obsidian:*)" in changes
    assert 'pluginConfigs["tasks@adhd-planner"].options.vaultPath: set' in changes


def test_merge_replaces_a_different_vault_and_says_so():
    current = desired("/old", permissions=False)
    merged, changes = merge(current, desired("/new", permissions=False), home="/h")
    assert merged["pluginConfigs"]["tasks@adhd-planner"]["options"]["vaultPath"] == "/new"
    assert 'pluginConfigs["tasks@adhd-planner"].options.vaultPath: change' in changes


def test_merge_is_idempotent():
    once, _ = merge({}, desired("/v", permissions=True), home="/h")
    twice, changes = merge(once, desired("/v", permissions=True), home="/h")
    assert twice == once and changes == []


def test_change_lines_never_contain_values():
    _, changes = merge({}, desired("/secret/vault", permissions=False), home="/h")
    assert not any("/secret/vault" in c for c in changes)


def test_merge_does_not_duplicate_a_tilde_or_trailing_slash_dir():
    for existing in ("~/vault", "~/vault/", "/h/vault/"):
        current = {"permissions": {"additionalDirectories": [existing]}}
        merged, changes = merge(current, desired("/h/vault", permissions=True), home="/h")
        assert merged["permissions"]["additionalDirectories"] == [existing], existing
        assert "permissions.additionalDirectories: add vault" not in changes


def test_wrong_typed_keys_abort_naming_the_key():
    import pytest
    cases = [
        ({"pluginConfigs": []}, "pluginConfigs"),
        ({"pluginConfigs": {"tasks@adhd-planner": None}}, 'pluginConfigs["tasks@adhd-planner"]'),
        ({"pluginConfigs": {"tasks@adhd-planner": {"options": "x"}}}, 'pluginConfigs["tasks@adhd-planner"].options'),
        ({"permissions": None}, "permissions"),
        ({"permissions": {"additionalDirectories": "~/vault"}}, "permissions.additionalDirectories"),
    ]
    for current, label in cases:
        with pytest.raises(SystemExit) as err:
            wanted = desired("/v", permissions=True)
            wanted["permissions"]["additionalDirectories"] = ["/v"]  # merge() must still validate it
            merge(current, wanted, home="/h")
        assert f"settings.json {label} is a " in str(err.value) and "nothing was changed" in str(err.value), label
