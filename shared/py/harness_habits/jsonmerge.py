"""Idempotent JSON file edits: backup only on change, atomic write through symlinks, mode preserved."""
import json
import os
import shutil
import time
from pathlib import Path
from typing import Callable


def _backup_name(path: Path) -> Path:
    stamp = int(time.time())
    bak = path.with_name(f"{path.name}.bak.{stamp}")
    n = 1
    while bak.exists() or bak.is_symlink():
        bak = path.with_name(f"{path.name}.bak.{stamp}.{n}")
        n += 1
    return bak


def merge_file(path, mutate: Callable[[dict], dict], backup: bool = True, write: bool = True) -> bool:
    """Apply mutate to the JSON object at path. Returns True when content changes.

    Missing file reads as {}. With write=False nothing touches the disk (dry run).
    A symlinked file is edited through the link (the link survives); the file mode is kept.
    """
    path = Path(path)
    target = path.resolve() if path.is_symlink() else path
    existed = target.exists()
    text = target.read_text() if existed else ""
    old = json.loads(text) if text.strip() else {}
    if not isinstance(old, dict):
        raise ValueError(f"{path} does not contain a JSON object")
    new = mutate(json.loads(json.dumps(old)))
    if existed and new == old:
        return False
    if not write:
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    if existed and backup:
        bak = _backup_name(target)
        bak.write_bytes(target.read_bytes())
        shutil.copymode(target, bak)
    tmp = target.with_name(f".{target.name}.tmp{os.getpid()}")
    try:
        payload = (json.dumps(new, indent=2, ensure_ascii=False) + "\n").encode()
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600 if existed else 0o666)  # never wider than the original
        with os.fdopen(fd, "wb") as fh:
            fh.write(payload)
        if existed:
            shutil.copymode(target, tmp)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()
    return True
