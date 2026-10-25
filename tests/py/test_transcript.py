from pathlib import Path

from harness_habits import transcript

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "transcripts" / "sample.jsonl"


def test_extract():
    s = transcript.extract(FIX)
    assert s.user_messages == ["second", "third", "fourth", "fifth", "sixth"]
    assert s.last_assistant_text == "Tests are written."
    assert [t["content"] for t in s.todos] == ["write tests", "ship"]
    assert s.edited_files == ["/proj/src/parser.py", "/proj/nb.ipynb", "/proj/tests/test_parser.py"]


def test_missing_file_is_empty(tmp_path):
    s = transcript.extract(tmp_path / "nope.jsonl")
    assert s.user_messages == [] and s.todos == [] and s.edited_files == []


def test_render():
    out = transcript.render(transcript.extract(FIX), Path("/proj"), "s-1")
    lines = out.splitlines()
    assert lines[0] == "session: s-1" and lines[1] == "cwd: /proj" and lines[2].startswith("written: 20")
    assert "write tests" in out and "/proj/tests/test_parser.py" in out and "Tests are written." in out
