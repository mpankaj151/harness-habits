"""Idempotent JSON file edits: backup only on change, atomic write."""
import json
import os
import time
from pathlib import Path
from typing import Callable


def merge_file(path, mutate: Callable[[dict], dict], backup: bool = True, write: bool = True) -> bool:
    """Apply mutate to the JSON object at path. Returns True when content changes.

    Missing file reads as {}. With write=False nothing touches the disk (dry run).
    """
    path = Path(path)
    existed = path.exists()
    old = json.loads(path.read_text()) if existed and path.read_text().strip() else {}
    if not isinstance(old, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    new = mutate(json.loads(json.dumps(old)))
    if existed and new == old:
        return False
    if not write:
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    if existed and backup:
        bak = path.with_name(f"{path.name}.bak.{int(time.time())}")
        bak.write_bytes(path.read_bytes())
    tmp = path.with_name(f".{path.name}.tmp{os.getpid()}")
    tmp.write_text(json.dumps(new, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return True
