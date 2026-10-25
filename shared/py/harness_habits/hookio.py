"""Hook stdin/stdout helpers. Hooks never break the harness."""
import functools
import json
import sys


def read_json_stdin() -> dict:
    try:
        data = json.loads(sys.stdin.read())
    except (ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def warn(msg: str) -> None:
    sys.stderr.write(f"harness-habits: {msg}\n")


def safe_main(fn):
    """Run fn; any exception becomes a stderr warning and exit 0."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - hooks must never fail the harness
            warn(f"{type(exc).__name__}: {exc}")
        sys.exit(0)

    return wrapper
