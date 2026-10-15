import json
import os
import stat

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


def test_write_through_a_symlink_keeps_the_link_and_the_mode(tmp_path):
    real = tmp_path / "dotfiles" / "settings.json"
    real.parent.mkdir()
    real.write_text('{"a": 1}')
    real.chmod(0o600)
    link = tmp_path / ".claude" / "settings.json"
    link.parent.mkdir()
    link.symlink_to(real)
    write_json(link, {"a": 2}, backup_dir(tmp_path), home=tmp_path)
    assert link.is_symlink() and link.resolve() == real.resolve()
    assert json.loads(real.read_text()) == {"a": 2}
    assert stat.S_IMODE(real.stat().st_mode) == 0o600
    assert not list(real.parent.glob("*.tmp")) and not list(link.parent.glob("*.tmp"))


def test_write_keeps_a_private_mode(tmp_path):
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir()
    target.write_text("{}")
    target.chmod(0o600)
    write_json(target, {"a": 1}, backup_dir(tmp_path), home=tmp_path)
    assert stat.S_IMODE(target.stat().st_mode) == 0o600


def test_write_through_a_dangling_symlink_creates_the_target(tmp_path):
    real = tmp_path / "dotfiles" / "settings.json"
    real.parent.mkdir()
    link = tmp_path / ".claude" / "settings.json"
    link.parent.mkdir()
    link.symlink_to(real)
    assert write_json(link, {"a": 1}, backup_dir(tmp_path), home=tmp_path) is None
    assert link.is_symlink()
    assert json.loads(real.read_text()) == {"a": 1}


def test_content_is_never_written_to_a_looser_file(tmp_path, monkeypatch):
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir()
    target.write_text("{}")
    target.chmod(0o600)
    modes = []
    real_write = os.write

    def spy(fd, data):
        modes.append(stat.S_IMODE(os.fstat(fd).st_mode))
        return real_write(fd, data)

    monkeypatch.setattr(os, "write", spy)
    write_json(target, {"a": 1}, backup_dir(tmp_path), home=tmp_path)
    assert modes and set(modes) == {0o600}


def test_a_failed_write_leaves_no_tmp(tmp_path, monkeypatch):
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir()
    target.write_text('{"a": 1}')

    def full_disk(fd, data):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "write", full_disk)
    with pytest.raises(OSError):
        write_json(target, {"a": 2}, backup_dir(tmp_path), home=tmp_path)
    assert json.loads(target.read_text()) == {"a": 1}
    assert not list(target.parent.glob("*.tmp"))


def test_a_stale_tmp_symlink_is_not_written_through(tmp_path):
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir()
    target.write_text("{}")
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_text("untouched")
    (target.parent / "settings.json.tmp").symlink_to(elsewhere)
    write_json(target, {"a": 1}, backup_dir(tmp_path), home=tmp_path)
    assert elsewhere.read_text() == "untouched"
    assert json.loads(target.read_text()) == {"a": 1}


def test_a_short_write_is_completed(tmp_path, monkeypatch):
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir()
    real_write = os.write

    def one_byte(fd, data):
        return real_write(fd, bytes(data[:1]))

    monkeypatch.setattr(os, "write", one_byte)
    write_json(target, {"a": 1}, backup_dir(tmp_path), home=tmp_path)
    assert json.loads(target.read_text()) == {"a": 1}


def test_another_writers_tmp_is_left_alone(tmp_path):
    # Two setup runs at once must not share a tmp path: each gets its own.
    target = tmp_path / ".claude" / "settings.json"
    target.parent.mkdir()
    target.write_text("{}")
    other = target.parent / "settings.json.tmp"
    other.write_text("another run's half-written file")
    write_json(target, {"a": 1}, backup_dir(tmp_path), home=tmp_path)
    assert other.read_text() == "another run's half-written file"
    assert json.loads(target.read_text()) == {"a": 1}


def test_a_new_file_gets_the_umask_mode(tmp_path):
    target = tmp_path / ".claude" / "settings.json"
    old = os.umask(0o022)
    try:
        write_json(target, {"a": 1}, backup_dir(tmp_path), home=tmp_path)
    finally:
        os.umask(old)
    assert stat.S_IMODE(target.stat().st_mode) == 0o644
