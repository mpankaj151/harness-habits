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
