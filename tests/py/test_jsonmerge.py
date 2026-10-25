import json

from harness_habits.jsonmerge import merge_file


def test_missing_creates_without_backup(tmp_path):
    p = tmp_path / "a.json"
    assert merge_file(p, lambda d: {**d, "x": 1}) is True
    assert json.loads(p.read_text()) == {"x": 1}
    assert p.read_text().startswith('{\n  "x"')
    assert list(tmp_path.glob("*.bak.*")) == []


def test_backup_only_on_change(tmp_path):
    p = tmp_path / "a.json"
    p.write_text('{"y": 2}')
    assert merge_file(p, lambda d: {**d, "x": 1}) is True
    assert len(list(tmp_path.glob("a.json.bak.*"))) == 1
    before = p.read_text()
    assert merge_file(p, lambda d: {**d, "x": 1}) is False
    assert p.read_text() == before
    assert len(list(tmp_path.glob("a.json.bak.*"))) == 1


def test_no_backup_flag_and_dry_run(tmp_path):
    p = tmp_path / "a.json"
    p.write_text("{}")
    merge_file(p, lambda d: {"x": 1}, backup=False)
    assert list(tmp_path.glob("*.bak.*")) == []
    assert merge_file(p, lambda d: {"x": 2}, write=False) is True
    assert json.loads(p.read_text()) == {"x": 1}


def test_symlinked_0600_file_keeps_link_and_mode(tmp_path):
    import os
    real = tmp_path / "dotfiles" / "settings.json"
    real.parent.mkdir()
    real.write_text('{"secret": 1}')
    real.chmod(0o600)
    link = tmp_path / "settings.json"
    link.symlink_to(real)
    assert merge_file(link, lambda d: {**d, "x": 1}) is True
    assert link.is_symlink() and link.resolve() == real.resolve()
    assert json.loads(real.read_text()) == {"secret": 1, "x": 1}
    assert os.stat(real).st_mode & 0o777 == 0o600
    baks = list(real.parent.glob("settings.json.bak.*"))
    assert len(baks) == 1 and os.stat(baks[0]).st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob(".*.tmp*")) and not list(real.parent.glob(".*.tmp*"))


def test_two_edits_in_one_second_keep_both_backups(tmp_path, monkeypatch):
    import time
    monkeypatch.setattr(time, "time", lambda: 1_700_000_000.0)
    p = tmp_path / "a.json"
    p.write_text('{"n": 0}')
    merge_file(p, lambda d: {"n": 1})
    merge_file(p, lambda d: {"n": 2})
    merge_file(p, lambda d: {"n": 3})
    baks = sorted(tmp_path.glob("a.json.bak.*"))
    assert len(baks) == 3
    assert sorted(json.loads(b.read_text())["n"] for b in baks) == [0, 1, 2]
