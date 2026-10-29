from planner_setup import board_plugin, paths
from planner_setup.board_plugin import BOARD_VIEW, DONE_VIEW, DONE_VIEW_NAME, PLUGIN_FILES


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
