import http.client
import json

from planner_setup import board_plugin, paths
from planner_setup.board_plugin import (BOARD_VIEW, DONE_VIEW, DONE_VIEW_NAME, PLUGIN_FILES, PLUGIN_ID, PLUGIN_REPO,
                                        PLUGIN_VERSION, install_plugin, installed_version, merge_base)


def starter_base() -> str:
    return (paths.examples() / "vault-starter" / "Tasks.base").read_text()


def test_starter_has_the_board_view_verbatim():
    assert BOARD_VIEW in starter_base()


def test_board_groups_by_status_in_board_order():
    assert "groupByProperty: note.status" in BOARD_VIEW
    cols = BOARD_VIEW.split("note.status:\n", 1)[1].split()
    assert cols[:6] == ["-", "parked", "-", "active", "-", "done"]


def test_board_and_done_view_hide_done_older_than_seven_days():
    window = 'finished >= today() - "6 days"'
    assert window in BOARD_VIEW and window in DONE_VIEW


def test_starter_has_the_done_view_verbatim():
    assert f"name: {DONE_VIEW_NAME}\n" in DONE_VIEW
    assert DONE_VIEW in starter_base()


def test_views_are_list_items_under_views():
    for view in (BOARD_VIEW, DONE_VIEW):
        assert view.startswith("  - type: ") and view.endswith("\n")


def test_plugin_files_and_pin():
    assert {"manifest.json", "main.js"} <= set(PLUGIN_FILES)
    assert board_plugin.PLUGIN_REPO.count("/") == 1
    assert board_plugin.PLUGIN_VERSION and board_plugin.PLUGIN_ID


# ~/vaults/personal/Tasks.base as of 2026-10-29: custom views and a custom sort the merge must keep.
PERSONAL_BASE = '''\
filters:
  and:
    - file.inFolder("Tasks")
properties:
  note.up:
    displayName: Project
views:
  - type: table
    name: Active
    filters:
      and:
        - status == "active"
    order:
      - file.name
      - up
      - started
    sort:
      - property: started
        direction: DESC
  - type: table
    name: Parked
    filters:
      and:
        - status == "parked"
    order:
      - file.name
      - up
      - started
  - type: table
    name: Done
    filters:
      and:
        - status == "done"
    order:
      - file.name
      - up
      - started
'''

BASE_WITH_OTHER_BOARD = PERSONAL_BASE + '''\
  - type: kanban-view
    name: Board
    groupByProperty: note.up
'''


def fake_fetch(calls=None, fail_on=None, version=PLUGIN_VERSION):
    def fetch(url):
        if calls is not None:
            calls.append(url)
        name = url.rsplit("/", 1)[1]
        if name == fail_on:
            raise OSError(f"no route to host for {name}")
        if name == "manifest.json":
            return json.dumps({"id": PLUGIN_ID, "version": version}).encode()
        return f"/* {name} */".encode()
    return fetch


def test_merge_adds_board_once():
    t, o = merge_base(PERSONAL_BASE)
    assert o == "added"
    assert t.startswith(PERSONAL_BASE) and t.endswith(BOARD_VIEW + DONE_VIEW)
    assert merge_base(t) == (t, "unchanged")


def test_merge_keeps_custom_sort():
    assert "direction: DESC" in merge_base(PERSONAL_BASE)[0]


def test_merge_crlf_round_trip():
    crlf = PERSONAL_BASE.replace("\n", "\r\n")
    t, o = merge_base(crlf)
    assert o == "added" and "\r\n" in t and "\n" not in t.replace("\r\n", "")
    assert merge_base(t) == (t, "unchanged")


def test_merge_conflict_on_same_name_other_text():
    assert merge_base(BASE_WITH_OTHER_BOARD) == (BASE_WITH_OTHER_BOARD, "conflict")


def test_merge_conflict_without_block_views():
    assert merge_base("filters:\n  and: []\n")[1] == "conflict"
    assert merge_base("views: []\n")[1] == "conflict"
    assert merge_base("views:\n- type: table\n  name: Active\n")[1] == "conflict"  # items not at the starter's indent


def test_merge_inserts_before_the_next_top_level_key():
    t, o = merge_base(PERSONAL_BASE + "\nsummaries:\n  x: 1\n")
    assert o == "added"
    assert t == PERSONAL_BASE + BOARD_VIEW + DONE_VIEW + "\nsummaries:\n  x: 1\n"


def test_merge_without_final_newline():
    t, o = merge_base(PERSONAL_BASE.rstrip("\n"))
    assert o == "added" and t == PERSONAL_BASE + BOARD_VIEW + DONE_VIEW


def test_merge_adds_only_the_missing_view():
    t, o = merge_base(PERSONAL_BASE + BOARD_VIEW)
    assert o == "added" and t == PERSONAL_BASE + BOARD_VIEW + DONE_VIEW


def test_starter_base_is_unchanged():
    assert merge_base(starter_base()) == (starter_base(), "unchanged")


def obsidian(tmp_path, plugins=None):
    vault = tmp_path / "v"
    (vault / ".obsidian").mkdir(parents=True)
    if plugins is not None:
        (vault / ".obsidian" / "community-plugins.json").write_text(json.dumps(plugins))
    return vault


def test_install_downloads_the_pinned_release(tmp_path):
    vault, calls = obsidian(tmp_path), []
    assert install_plugin(vault, fake_fetch(calls), tmp_path / "backups", home=tmp_path) == "installed"
    base = f"https://github.com/{PLUGIN_REPO}/releases/download/{PLUGIN_VERSION}/"
    assert calls == [base + f for f in PLUGIN_FILES]
    dest = vault / ".obsidian" / "plugins" / PLUGIN_ID
    assert sorted(p.name for p in dest.iterdir()) == sorted(PLUGIN_FILES)
    assert json.loads((vault / ".obsidian" / "community-plugins.json").read_text()) == [PLUGIN_ID]


def test_install_keeps_existing_plugins(tmp_path):
    vault = obsidian(tmp_path, ["meetings-plus"])
    assert install_plugin(vault, fake_fetch(), tmp_path / "backups", home=tmp_path) == "installed"
    assert json.loads((vault / ".obsidian" / "community-plugins.json").read_text()) == ["meetings-plus", PLUGIN_ID]
    backup = tmp_path / "backups" / "v" / ".obsidian" / "community-plugins.json"
    assert json.loads(backup.read_text()) == ["meetings-plus"]


def test_install_failed_fetch_leaves_nothing(tmp_path):
    vault = obsidian(tmp_path, ["meetings-plus"])
    result = install_plugin(vault, fake_fetch(fail_on="main.js"), tmp_path / "backups", home=tmp_path)
    assert result.startswith("failed: ") and "main.js" in result
    assert not (vault / ".obsidian" / "plugins" / PLUGIN_ID).exists()
    assert json.loads((vault / ".obsidian" / "community-plugins.json").read_text()) == ["meetings-plus"]


def test_install_failed_read_leaves_nothing(tmp_path):
    vault = obsidian(tmp_path, ["meetings-plus"])

    def fetch(url):
        raise http.client.IncompleteRead(b"")
    result = install_plugin(vault, fetch, tmp_path / "backups", home=tmp_path)
    assert result.startswith("failed: ")
    assert not (vault / ".obsidian" / "plugins" / PLUGIN_ID).exists()


def test_install_refuses_a_release_with_another_version(tmp_path):
    vault = obsidian(tmp_path)
    result = install_plugin(vault, fake_fetch(version="0.0.1"), tmp_path / "backups", home=tmp_path)
    assert result.startswith("failed: ") and "0.0.1" in result
    assert not (vault / ".obsidian" / "plugins").exists()


def test_install_refuses_a_community_plugins_file_that_is_not_a_list(tmp_path):
    vault = obsidian(tmp_path, {"meetings-plus": True})
    result = install_plugin(vault, fake_fetch(), tmp_path / "backups", home=tmp_path)
    assert result.startswith("failed: ") and "community-plugins.json" in result
    assert not (vault / ".obsidian" / "plugins").exists()


def test_install_present_does_not_download(tmp_path):
    vault = obsidian(tmp_path)
    install_plugin(vault, fake_fetch(), tmp_path / "backups", home=tmp_path)
    calls = []
    assert install_plugin(vault, fake_fetch(calls), tmp_path / "backups2", home=tmp_path) == "present"
    assert calls == [] and not (tmp_path / "backups2").exists()


def test_install_replaces_an_older_version_with_backup(tmp_path):
    vault = obsidian(tmp_path)
    dest = vault / ".obsidian" / "plugins" / PLUGIN_ID
    dest.mkdir(parents=True)
    (dest / "manifest.json").write_text(json.dumps({"version": "0.9.0"}))
    (dest / "data.json").write_text('{"mine": 1}')
    assert installed_version(vault) == "0.9.0"
    assert install_plugin(vault, fake_fetch(), tmp_path / "backups", home=tmp_path) == "installed"
    assert installed_version(vault) == PLUGIN_VERSION
    assert (dest / "data.json").read_text() == '{"mine": 1}'
    old = tmp_path / "backups" / "v" / ".obsidian" / "plugins" / PLUGIN_ID / "manifest.json"
    assert json.loads(old.read_text())["version"] == "0.9.0"
