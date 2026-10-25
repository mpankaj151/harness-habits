"""Stream a Claude Code transcript JSONL into a small resumable snapshot."""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
MAX_USER = 5


@dataclass
class Snapshot:
    user_messages: list = field(default_factory=list)
    last_assistant_text: str = ""
    todos: list = field(default_factory=list)
    edited_files: list = field(default_factory=list)


def _blocks(content):
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def iter_entries(path: Path):
    """Yield each JSON-object line of a transcript; unreadable files and malformed lines are skipped."""
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return
    with fh:
        for raw in fh:
            try:
                d = json.loads(raw)
            except ValueError:
                continue
            if isinstance(d, dict):
                yield d


def extract(path: Path) -> Snapshot:
    snap = Snapshot()
    seen = set()
    for d in iter_entries(path):
        if d.get("isSidechain"):
            continue
        kind, msg = d.get("type"), d.get("message")
        if kind not in ("user", "assistant") or not isinstance(msg, dict):
            continue
        blocks = _blocks(msg.get("content"))
        if kind == "user":
            text = "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text" and isinstance(b.get("text"), str)).strip()
            if text and not d.get("isMeta"):
                snap.user_messages.append(text)
                del snap.user_messages[:-MAX_USER]
            continue
        texts = [b["text"] for b in blocks if b.get("type") == "text" and isinstance(b.get("text"), str) and b["text"].strip()]
        if texts:
            snap.last_assistant_text = "\n".join(texts).strip()
        for b in blocks:
            if b.get("type") != "tool_use" or not isinstance(b.get("input"), dict):
                continue
            name, tin = b.get("name"), b["input"]
            if name == "TodoWrite" and isinstance(tin.get("todos"), list):
                snap.todos = [t for t in tin["todos"] if isinstance(t, dict)]
            elif name in EDIT_TOOLS:
                fp = tin.get("file_path") or tin.get("notebook_path")
                if isinstance(fp, str) and fp not in seen:
                    seen.add(fp)
                    snap.edited_files.append(fp)
    return snap


def render(snapshot: Snapshot, cwd, session_id: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = [f"session: {session_id}", f"cwd: {cwd}", f"written: {now}", ""]
    out.append("## Recent user messages")
    out += [f"- {m}" for m in snapshot.user_messages] or ["- (none)"]
    out += ["", "## Last assistant message", snapshot.last_assistant_text or "(none)", "", "## Todos"]
    out += [f"- [{t.get('status', '?')}] {t.get('content', '')}" for t in snapshot.todos] or ["- (none)"]
    out += ["", "## Files edited"]
    out += [f"- {p}" for p in snapshot.edited_files] or ["- (none)"]
    return "\n".join(out) + "\n"


def extract_tolerant(path: Path) -> Snapshot:
    """Claude-shape extraction first; if that finds no text, scan for any {role, content} message.

    Codex rollout lines are not verified against a live binary, so messages are looked for at the top
    level and under `payload` / `message`. Unknown lines are ignored.
    """
    snap = extract(path)
    if snap.user_messages or snap.last_assistant_text:
        return snap
    for d in iter_entries(path):
        for cand in (d, d.get("payload"), d.get("message")):
            if not isinstance(cand, dict) or cand.get("role") not in ("user", "assistant"):
                continue
            text = "\n".join(b["text"] for b in _blocks(cand.get("content")) if isinstance(b.get("text"), str)).strip()
            if not text:
                continue
            if cand["role"] == "assistant":
                snap.last_assistant_text = text
            elif not text.startswith("<"):  # skip injected <environment_context>-style blocks
                snap.user_messages.append(text)
                del snap.user_messages[:-MAX_USER]
            break
    return snap
