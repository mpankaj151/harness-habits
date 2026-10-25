import json
from pathlib import Path

import pytest

from harness_habits import guard
from harness_habits.paths import rules_path

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "output-guard"
RULES = json.loads(rules_path().read_text())


class FakeFS:
    def __init__(self, files):
        self.files = files

    def line_count(self, path):
        n = self.files.get(path)
        return None if n is None or n < 0 else n


def _cases():
    return list(_iter_cases())


def _iter_cases():
    for f in sorted(FIXTURES.glob("*.json")):
        for case in json.loads(f.read_text()):
            yield pytest.param(case, id=f"{f.stem}:{case['name']}")


@pytest.mark.parametrize("case", _cases())
def test_fixture(case):
    d = guard.evaluate(case["command"], case["cwd"], FakeFS(case["files"]), RULES)
    exp = case["expect"]
    assert d.action == exp["action"]
    if "command" in exp:
        assert d.command == exp["command"]
    if "message_contains" in exp:
        assert exp["message_contains"] in (d.message or "")


def test_evaluate_read():
    fs = FakeFS({"big.txt": 800, "small.txt": 5})
    assert guard.evaluate_read("big.txt", None, "/work", fs, RULES).action == "advise"
    assert guard.evaluate_read("big.txt", 100, "/work", fs, RULES).action == "allow"
    assert guard.evaluate_read("small.txt", None, "/work", fs, RULES).action == "allow"
    assert guard.evaluate_read("missing.txt", None, "/work", fs, RULES).action == "allow"


def test_capped_count_renders_more_than():
    d = guard.evaluate("cat big.txt", "/work", FakeFS({"big.txt": 501}), RULES)
    assert "more than 500 lines" in d.message
    d = guard.evaluate("cat big.txt", "/work", FakeFS({"big.txt": 800}), RULES)
    assert "800 lines" in d.message
    d = guard.evaluate_read("big.txt", None, "/work", FakeFS({"big.txt": 501}), RULES)
    assert "more than 500 lines" in d.message
