import json

import pytest

from planner_setup.files import backup_dir, load_json, write_json


def test_load_missing_or_blank_is_empty(tmp_path):
    assert load_json(tmp_path / "nope.json") == {}
    (tmp_path / "blank.json").write_text("  \n")
    assert load_json(tmp_path / "blank.json") == {}


def test_load_invalid_json_aborts_naming_the_file(tmp_path):
    bad = tmp_path / "settings.json"
    bad.write_text("{ nope")
    with pytest.raises(SystemExit) as err:
        load_json(bad)
    assert str(bad) in str(err.value) and "nothing was changed" in str(err.value)


def test_load_non_object_aborts(tmp_path):
    arr = tmp_path / "settings.json"
    arr.write_text("[]")
    with pytest.raises(SystemExit):
        load_json(arr)


def test_write_backs_up_then_replaces(tmp_path):
    home = tmp_path
    target = home / ".claude" / "settings.json"
    target.parent.mkdir()
    target.write_text('{"a": 1}')
    backups = backup_dir(home)
    saved = write_json(target, {"a": 2}, backups, home=home)
    assert json.loads(target.read_text()) == {"a": 2}
    assert saved == backups / ".claude" / "settings.json"
    assert json.loads(saved.read_text()) == {"a": 1}
    assert not list(target.parent.glob("*.tmp"))


def test_write_new_file_has_no_backup(tmp_path):
    target = tmp_path / ".claude" / "settings.json"
    assert write_json(target, {"a": 1}, backup_dir(tmp_path), home=tmp_path) is None
    assert target.read_text().endswith("\n")


def test_second_apply_is_noop_and_skips_backup(tmp_path):
    from planner_setup.settings import desired, merge
    target = tmp_path / ".claude" / "settings.json"
    merged, _ = merge(load_json(target), desired("/v", permissions=False), home="/h")
    write_json(target, merged, backup_dir(tmp_path), home=tmp_path)
    again, changes = merge(load_json(target), desired("/v", permissions=False), home="/h")
    assert changes == []  # caller skips write_json, so no backup is made


def test_backup_dir_is_new_within_the_same_second(tmp_path, monkeypatch):
    monkeypatch.setattr("planner_setup.files.time.strftime", lambda _f: "20261013120000")
    first = backup_dir(tmp_path)
    first.mkdir(parents=True)
    second = backup_dir(tmp_path)
    assert second != first and not second.exists()
    assert second.name.startswith("20261013120000")
