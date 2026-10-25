"""Weekly cost report: session-browser registry, OpenCode usage log, transcript fallback."""
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .transcript import iter_entries

TOP_N = 10
DEFAULT_PRICE = {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75}


def parse_since(value: str, now: datetime) -> datetime:
    m = re.fullmatch(r"(\d+)d", value.strip())
    if m:
        return now - timedelta(days=int(m.group(1)))
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        raise ValueError(f"unrecognized --since value {value!r} (use 7d, 30d or YYYY-MM-DD)") from None


def parse_ts(value):
    """ISO text, epoch seconds or epoch milliseconds (number or numeric string) -> aware UTC datetime."""
    if value is None or isinstance(value, bool):
        return None
    try:
        if isinstance(value, str) and not re.fullmatch(r"\d+(\.\d+)?", value.strip()):
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        n = float(value)
        if n > 1e11:
            n /= 1000.0
        return datetime.fromtimestamp(n, timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None


def _int(v) -> int:
    return v if isinstance(v, int) and not isinstance(v, bool) else 0


def _num(v) -> float:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else 0.0


def registry_section(path: Path, since: datetime) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT session_id, title, folder_name, cli_source, model_used, last_activity, "
            "input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cost_usd FROM sessions"
        ).fetchall()
    finally:
        con.close()
    by_source, by_model, top = {}, {}, []
    tot = {"input": 0, "cache_read": 0, "cache_write": 0}
    n = 0
    for sid, title, folder, src, model, last, i, o, cr, cw, cost in rows:
        ts = parse_ts(last)
        if ts is None or ts < since:
            continue
        n += 1
        c = _num(cost)
        for table, key in ((by_source, src or "(unknown)"), (by_model, model or "(unknown)")):
            e = table.setdefault(key, {"sessions": 0, "cost": 0.0, "input_tokens": 0, "output_tokens": 0})
            e["sessions"] += 1
            e["cost"] += c
            e["input_tokens"] += _int(i)
            e["output_tokens"] += _int(o)
        tot["input"] += _int(i)
        tot["cache_read"] += _int(cr)
        tot["cache_write"] += _int(cw)
        if cost is not None:
            top.append({"session_id": sid, "title": title or "", "folder_name": folder or "",
                        "cli_source": src, "model_used": model, "cost": c})
    top.sort(key=lambda t: -t["cost"])
    denom = tot["input"] + tot["cache_read"] + tot["cache_write"]
    return {"sessions": n, "by_source": by_source, "by_model": by_model, "top": top[:TOP_N],
            "total_cost": sum(e["cost"] for e in by_source.values()),
            "cache_hit_ratio": tot["cache_read"] / denom if denom else 0.0}


def usage_section(path: Path, since: datetime):
    if not path.exists():
        return None
    by_model = {}
    for d in iter_entries(path):
        ts = parse_ts(d.get("ts"))
        if ts is None or ts < since:
            continue
        key = f"{d.get('providerID') or '?'}/{d.get('modelID') or '?'}"
        e = by_model.setdefault(key, {"messages": 0, "cost": 0.0})
        e["messages"] += 1
        e["cost"] += _num(d.get("cost"))
    return {"by_model": by_model, "total_cost": sum(e["cost"] for e in by_model.values())}


def price_for(model, pricing: dict) -> dict:
    best = ""
    for k in pricing:
        if k not in ("default", "_note") and isinstance(model, str) and model.startswith(k) and len(k) > len(best):
            best = k
    chosen = pricing.get(best) if best else pricing.get("default")
    return chosen if isinstance(chosen, dict) else DEFAULT_PRICE


def load_pricing(data_dir: Path, shipped: Path) -> dict:
    """User copy in the data dir wins, then the repo copy, then built-in defaults."""
    for p in (data_dir / "pricing.json", shipped):
        try:
            d = json.loads(p.read_text())
            if isinstance(d, dict):
                return d
        except (OSError, ValueError):
            continue
    return {"default": DEFAULT_PRICE}


def transcript_section(projects: Path, since: datetime, pricing: dict):
    files = sorted(projects.glob("*/*.jsonl")) if projects.is_dir() else []
    if not files:
        return None
    msgs, order = {}, 0
    for f in files:
        for d in iter_entries(f):
            msg = d.get("message")
            if d.get("type") != "assistant" or not isinstance(msg, dict) or not isinstance(msg.get("usage"), dict):
                continue
            ts = parse_ts(d.get("timestamp"))
            if ts is not None and ts < since:
                continue
            order += 1
            mid = msg.get("id") if isinstance(msg.get("id"), str) else f"{f}#{order}"
            msgs[mid] = (msg.get("model"), msg["usage"])  # last occurrence wins
    by_model = {}
    for model, u in msgs.values():
        key = model if isinstance(model, str) and model else "(unknown)"
        e = by_model.setdefault(key, {"messages": 0, "input_tokens": 0, "output_tokens": 0,
                                      "cache_read_tokens": 0, "cache_write_tokens": 0, "cost": 0.0})
        i, o = _int(u.get("input_tokens")), _int(u.get("output_tokens"))
        cr, cw = _int(u.get("cache_read_input_tokens")), _int(u.get("cache_creation_input_tokens"))
        p = price_for(model, pricing)
        e["messages"] += 1
        e["input_tokens"] += i
        e["output_tokens"] += o
        e["cache_read_tokens"] += cr
        e["cache_write_tokens"] += cw
        e["cost"] += (i * _num(p.get("input")) + o * _num(p.get("output"))
                      + cr * _num(p.get("cache_read")) + cw * _num(p.get("cache_write"))) / 1e6
    return {"estimated": True, "messages": len(msgs), "by_model": by_model,
            "total_cost": sum(e["cost"] for e in by_model.values())}


def build(registry, usage_log, projects, since, pricing) -> dict:
    reg = registry_section(registry, since) if registry.exists() else None
    return {"since": since.isoformat(), "registry": reg, "usage_log": usage_section(usage_log, since),
            "transcripts": None if reg is not None else transcript_section(projects, since, pricing)}


def _table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out


def _cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_md(data: dict, title: str) -> str:
    out = [f"# harness-habits cost report ({title})", "", f"Window start: {data['since']}",
           "", "Sections below come from different sources and are never summed together.", ""]
    reg, usage, tr = data["registry"], data["usage_log"], data["transcripts"]
    if reg:
        out += ["## 1. Session-browser registry", "",
                f"{reg['sessions']} sessions, total cost ${reg['total_cost']:.2f} (sessions with no recorded cost count as $0).",
                f"Cache-hit ratio: {reg['cache_hit_ratio']:.1%} (cache_read / (input + cache_read + cache_write)).", "",
                "### By harness", ""]
        out += _table(["cli_source", "sessions", "cost"], [(k, v["sessions"], f"${v['cost']:.2f}") for k, v in sorted(reg["by_source"].items())])
        out += ["", "### By model", ""]
        out += _table(["model", "sessions", "cost"], [(_cell(k), v["sessions"], f"${v['cost']:.2f}") for k, v in sorted(reg["by_model"].items())])
        out += ["", f"### Top {TOP_N} sessions by cost", ""]
        out += _table(["session", "title", "folder", "harness", "cost"],
                      [(t["session_id"][:8], _cell(t["title"][:60]), _cell(t["folder_name"]), t["cli_source"], f"${t['cost']:.2f}") for t in reg["top"]])
        out.append("")
    elif tr:
        out += ["## 1. Claude transcripts (estimated)", "",
                "No registry found; figures are estimated from ~/.claude/projects transcripts with placeholder prices from pricing.json.", "",
                f"{tr['messages']} assistant messages, estimated cost ${tr['total_cost']:.2f}.", ""]
        out += _table(["model", "messages", "input", "output", "cache read", "cache write", "estimated cost"],
                      [(_cell(k), v["messages"], v["input_tokens"], v["output_tokens"], v["cache_read_tokens"], v["cache_write_tokens"], f"${v['cost']:.2f} (estimated)")
                       for k, v in sorted(tr["by_model"].items())])
        out.append("")
    else:
        out += ["## 1. Session data", "", "No registry or Claude transcripts found.", ""]
    out += ["## 2. OpenCode usage log", ""]
    if usage:
        out += ["Caveat: cost is the per-message accumulated cost reported by OpenCode; token counts in the log cover only the last step.", ""]
        out += _table(["provider/model", "messages", "cost"], [(_cell(k), v["messages"], f"${v['cost']:.2f}") for k, v in sorted(usage["by_model"].items())])
        out.append(f"\nSubtotal for this section: ${usage['total_cost']:.2f} (not added to section 1).")
    else:
        out.append("No usage log found (the cost-logger feature writes it).")
    return "\n".join(out) + "\n"
