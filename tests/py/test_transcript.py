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


def _write(path, entries):
    import json
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def _user(text, **flags):
    return {"type": "user", "message": {"role": "user", "content": text}, **flags}


def _asst(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def test_messages_are_capped(tmp_path):
    p = tmp_path / "t.jsonl"
    _write(p, [_user("u" * 5000), _asst("a" * 9000)])
    s = transcript.extract(p)
    assert len(s.user_messages[0]) == 1000 and len(s.last_assistant_text) == 2000


def test_render_total_is_capped(tmp_path):
    snap = transcript.Snapshot(user_messages=["u" * 1000] * 5, last_assistant_text="a" * 2000,
                               todos=[{"status": "pending", "content": "t" * 500}] * 20,
                               edited_files=["/f/" + "x" * 200] * 30)
    out = transcript.render(snap, Path("/proj"), "s-1")
    assert len(out.encode()) <= 6 * 1024 + 20 and out.startswith("session: s-1") and out.rstrip().endswith("(truncated)")


def test_compaction_summaries_and_ui_only_entries_are_skipped(tmp_path):
    p = tmp_path / "t.jsonl"
    _write(p, [
        _user("real question"),
        _user("This session is being continued from a previous conversation...", isCompactSummary=True),
        _user("/compact output", isVisibleInTranscriptOnly=True),
        _asst("real answer"),
    ])
    s = transcript.extract(p)
    assert s.user_messages == ["real question"] and s.last_assistant_text == "real answer"
    _write(p, [{"role": "user", "content": "x", "isCompactSummary": True}, {"role": "user", "content": "kept"}])
    assert transcript.extract_tolerant(p).user_messages == ["kept"]
