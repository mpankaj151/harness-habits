"""Filesystem locations used by harness-habits."""
import os
from pathlib import Path

APP = "harness-habits"


def _xdg(var: str, default: str) -> Path:
    base = os.environ.get(var)
    return Path(base) if base else Path.home() / default


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / APP


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / APP


def rules_path() -> Path:
    return Path(__file__).resolve().parents[2] / "rules" / "output-guard.json"
