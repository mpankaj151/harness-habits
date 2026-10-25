"""Status line rendering: a cost/context segment plus an optional wrapped command."""
import json
import subprocess

from .paths import config_dir

DEFAULT_SEGMENTS = ["cost", "ctx"]


def load_config() -> dict:
    try:
        data = json.loads((config_dir() / "statusline.json").read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _get(data: dict, *keys):
    for key in keys:
        data = data.get(key) if isinstance(data, dict) else None
    return data


def segment(data: dict, names=None) -> str:
    parts = []
    for name in names or DEFAULT_SEGMENTS:
        if name == "cost":
            parts.append("$%.2f" % _num(_get(data, "cost", "total_cost_usd")))
        elif name == "ctx":
            parts.append("%d%%" % _num(_get(data, "context_window", "used_percentage")))
        elif name == "model":
            model = _get(data, "model", "display_name")
            if model:
                parts.append(str(model))
    return " · ".join(parts)


def _wrapped_command(wrapped):
    if isinstance(wrapped, dict):
        wrapped = wrapped.get("command")
    return wrapped if isinstance(wrapped, str) and wrapped.strip() else None


def render(raw: bytes, cfg: dict) -> str:
    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except ValueError:
        data = {}
    if not isinstance(data, dict):
        data = {}
    names = cfg.get("segments")
    seg = segment(data, names if isinstance(names, list) else None)
    command = _wrapped_command(cfg.get("wrapped"))
    if command:
        try:
            done = subprocess.run(command, shell=True, input=raw, capture_output=True, timeout=2)
            lines = done.stdout.decode("utf-8", "replace").splitlines() if done.returncode == 0 else []
            return f"{seg}  {lines[0]}" if lines else seg
        except (subprocess.TimeoutExpired, OSError):
            return seg
    model = _get(data, "model", "display_name")
    return f"{seg}  {model}" if model and "model" not in (cfg.get("segments") or []) else seg
