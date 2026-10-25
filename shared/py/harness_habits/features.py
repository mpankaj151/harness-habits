"""Feature toggles: defaults <- features.json <- HH_FEATURE_* <- CLAUDE_PLUGIN_OPTION_*."""
import json
import os

from .paths import config_dir

DEFAULTS = {
    "output-guard": True,
    "size-lint": True,
    "cache-break": True,
    "handoff": True,
    "idle-compaction": False,
    "cost-logger": True,
    "tool-budget": False,
    "precompact-snapshot": True,
}

_OFF = {"0", "false", "off"}


def _parse(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in _OFF


def load_features() -> dict:
    result = dict(DEFAULTS)
    try:
        data = json.loads((config_dir() / "features.json").read_text())
        if isinstance(data, dict):
            for key, value in data.items():
                if key in DEFAULTS:
                    result[key] = _parse(value)
    except (OSError, ValueError):
        pass
    for key in DEFAULTS:
        suffix = key.upper().replace("-", "_")
        for prefix in ("HH_FEATURE_", "CLAUDE_PLUGIN_OPTION_"):
            raw = os.environ.get(prefix + suffix)
            if raw is not None and raw != "":
                result[key] = _parse(raw)
    return result


def enabled(key: str) -> bool:
    return load_features().get(key, False)
