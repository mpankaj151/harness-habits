"""harness-habits installer. Stdlib only, Python 3.11+. Run via install.sh or `python3 -I install.py`."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "shared" / "py"))

from harness_habits.features import DEFAULTS  # noqa: E402
from harness_habits.jsonmerge import merge_file  # noqa: E402

MARKETPLACE = "mpankaj151/harness-habits"
PLUGIN = "harness-habits@harness-habits"
PLIST_NAME = "com.harness-habits.weekly-report.plist"
OPENCODE_DIST = ROOT / "opencode" / "dist" / "harness-habits.js"


class Ctx:
    def __init__(self, home: Path, dry: bool, explicit_home: bool):
        self.home = home
        self.dry = dry
        self.real_home = not explicit_home
        xdg_c, xdg_d = os.environ.get("XDG_CONFIG_HOME"), os.environ.get("XDG_DATA_HOME")
        self.config = (Path(xdg_c) if xdg_c and self.real_home else home / ".config") / "harness-habits"
        self.data = (Path(xdg_d) if xdg_d and self.real_home else home / ".local" / "share") / "harness-habits"

    def say(self, msg: str) -> None:
        print(("[dry-run] " if self.dry else "") + msg)

    def merge(self, path: Path, mutate, label: str) -> None:
        changed = merge_file(path, mutate, write=not self.dry)
        self.say(f"{'updated' if changed else 'unchanged'} {path} ({label})")

    def copy_file(self, src: Path, dst: Path) -> None:
        if dst.exists() and dst.read_bytes() == src.read_bytes():
            self.say(f"unchanged {dst}")
            return
        self.say(f"copy {src} -> {dst}")
        if not self.dry:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    def copy_tree(self, src: Path, dst: Path) -> None:
        for f in sorted(src.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and f.suffix != ".pyc":
                self.copy_file(f, dst / f.relative_to(src))

    def remove(self, path: Path) -> None:
        if path.exists() or path.is_symlink():
            self.say(f"remove {path}")
            if not self.dry:
                shutil.rmtree(path) if path.is_dir() else path.unlink()

    def run(self, cmd: list[str], external: bool = True) -> None:
        text = " ".join(cmd)
        self.say("run: " + text)
        if self.dry:
            return
        if external and not self.real_home:
            print(f"note: custom --home given, not running; run manually: {text}")
            return
        try:
            subprocess.run(cmd, check=False)
        except OSError:
            print(f"{cmd[0]} CLI not found; run these commands manually: {text}")


def install_runtime(ctx: Ctx, only: str | None = None) -> Path:
    """Copy bin scripts (all, or just `only`) and the harness_habits package to <data dir>/bin."""
    bindir = ctx.data / "bin"
    for script in sorted((ROOT / "shared" / "py" / "bin").glob(only or "*.py")):
        ctx.copy_file(script, bindir / script.name)
    ctx.copy_tree(ROOT / "shared" / "py" / "harness_habits", bindir / "harness_habits")
    pricing = ROOT / "shared" / "pricing.json"
    if only is None and pricing.exists() and not (ctx.data / "pricing.json").exists():
        ctx.copy_file(pricing, ctx.data / "pricing.json")  # seeded once; the user's edits are never overwritten
    return bindir


def uninstall_runtime(ctx: Ctx) -> None:
    bindir = ctx.data / "bin"
    ctx.remove(bindir / "statusline_wrap.py")
    others = [p for p in bindir.glob("*.py") if p.name != "statusline_wrap.py"] if bindir.exists() else []
    if not others:
        ctx.remove(bindir)


# --- claude -----------------------------------------------------------------------------

def do_claude(ctx: Ctx, uninstall: bool) -> None:
    if uninstall:
        ctx.run(["claude", "plugin", "uninstall", PLUGIN])
        return
    ctx.run(["claude", "plugin", "marketplace", "add", MARKETPLACE])
    ctx.run(["claude", "plugin", "install", PLUGIN])


def do_claude_dev(ctx: Ctx) -> None:
    print(f"claude --plugin-dir {ROOT}")


# --- statusline -------------------------------------------------------------------------

def do_statusline(ctx: Ctx, uninstall: bool) -> None:
    settings = ctx.home / ".claude" / "settings.json"
    cfg = ctx.config / "statusline.json"
    if uninstall:
        recorded = None
        if cfg.exists():
            recorded = json.loads(cfg.read_text() or "{}").get("wrapped")

        def restore(d: dict) -> dict:
            current = d.get("statusLine")
            if isinstance(current, dict) and "statusline_wrap.py" in str(current.get("command", "")):
                if recorded:
                    d["statusLine"] = recorded
                else:
                    d.pop("statusLine")
            return d

        if settings.exists():
            ctx.merge(settings, restore, "restore statusLine")
        if cfg.exists():
            ctx.merge(cfg, lambda d: {k: v for k, v in d.items() if k != "wrapped"}, "drop wrapped")
        uninstall_runtime(ctx)
        return

    bindir = install_runtime(ctx, "statusline_wrap.py")
    current = {}
    if settings.exists():
        current = json.loads(settings.read_text() or "{}").get("statusLine")
    if isinstance(current, dict) and current and "statusline_wrap.py" not in str(current.get("command", "")):
        ctx.merge(cfg, lambda d: {**d, "wrapped": current}, "record existing statusLine")
    ours = {"type": "command", "command": f"python3 -I {bindir / 'statusline_wrap.py'}"}
    ctx.merge(settings, lambda d: {**d, "statusLine": ours}, "set statusLine")


# --- features ---------------------------------------------------------------------------

def parse_features(raw: str) -> dict:
    chosen = {k.strip() for k in raw.split(",") if k.strip()}
    unknown = chosen - set(DEFAULTS)
    if unknown:
        sys.exit(f"install.py: unknown feature(s): {', '.join(sorted(unknown))}; valid: {', '.join(DEFAULTS)}")
    return {k: k in chosen for k in DEFAULTS}


def do_features(ctx: Ctx, feats: dict) -> None:
    ctx.merge(ctx.config / "features.json", lambda d: dict(feats), "features")


# --- opencode ---------------------------------------------------------------------------

BANNER = "// harness-habits"


def is_ours(text: str) -> bool:
    return text.startswith(BANNER)


ID_RE = re.compile(r"""\bid\s*:\s*["']harness-habits["']""")


def do_opencode(ctx: Ctx, feats: dict | None, uninstall: bool) -> None:
    plugins = ctx.home / ".config" / "opencode" / "plugins"
    target = plugins / "harness-habits.js"
    if uninstall:
        if target.exists():
            same = OPENCODE_DIST.exists() and target.read_bytes() == OPENCODE_DIST.read_bytes()
            if same or is_ours(target.read_text(errors="replace")):
                ctx.remove(target)
            else:
                ctx.say(f"notice: {target} is not a harness-habits build; leaving it")
        return
    if not OPENCODE_DIST.exists():
        ctx.say(f"skip opencode: {OPENCODE_DIST} not built (cd opencode && npm run build)")
        return
    dist = OPENCODE_DIST.read_bytes()
    for other in sorted(plugins.glob("*.js")) if plugins.exists() else []:
        if other == target:
            continue
        other_text = other.read_text(errors="replace")
        if ID_RE.search(other_text) or is_ours(other_text):
            ctx.say(f"warning: {other} already declares id \"harness-habits\"; skip opencode install")
            return
    if target.exists() and target.read_bytes() != dist:
        text = target.read_text(errors="replace")
        if not is_ours(text):
            ctx.say(f"warning: {target} is a different file; skip opencode install")
            return
    ctx.copy_file(OPENCODE_DIST, target)
    oc = ctx.config / "opencode.json"
    if oc.exists():
        ctx.say(f"unchanged {oc} (exists)")
    else:
        ctx.merge(oc, lambda d: {"features": dict(feats or DEFAULTS)}, "opencode options")


# --- codex ------------------------------------------------------------------------------

def codex_entries(hooks_src: Path) -> dict:
    return json.loads(hooks_src.read_text().replace("$HH_ROOT", str(ROOT)))


def is_our_codex_entry(entry, commands: set) -> bool:
    inner = entry.get("hooks", []) if isinstance(entry, dict) else []
    return any(isinstance(h, dict) and (h.get("command") in commands or "/shared/py/bin/codex_" in str(h.get("command", "")) and str(ROOT) in str(h.get("command", ""))) for h in inner)


def effective_features(ctx: Ctx, feats: dict | None) -> dict:
    if feats is not None:
        return feats
    result = dict(DEFAULTS)
    try:
        saved = json.loads((ctx.config / "features.json").read_text())
        if isinstance(saved, dict):
            result.update({k: bool(v) for k, v in saved.items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return result


def do_codex(ctx: Ctx, feats: dict, uninstall: bool) -> None:
    src = ROOT / "codex"
    hooks_dst = ctx.home / ".codex" / "hooks.json"
    skill_dst = ctx.home / ".agents" / "skills" / "handoff-note"
    if uninstall:
        commands = set()
        if (src / "hooks.json").exists():
            for items in codex_entries(src / "hooks.json").get("hooks", {}).values():
                commands |= {h.get("command") for e in items for h in e.get("hooks", [])}

        def strip(d: dict) -> dict:
            hooks = d.get("hooks", {})
            for event in list(hooks):
                hooks[event] = [e for e in hooks[event] if not is_our_codex_entry(e, commands)]
                if not hooks[event]:
                    del hooks[event]
            return d

        if hooks_dst.exists():
            ctx.merge(hooks_dst, strip, "remove harness-habits codex hooks")
        ctx.remove(skill_dst)
        return
    hooks_src = src / "hooks.json"
    if not hooks_src.exists():
        ctx.say("notice: codex files (codex/hooks.json, codex/skills/, codex/config.toml.snippet) are not in this checkout yet; skipping codex")
        return
    entries = codex_entries(hooks_src)

    def add(d: dict) -> dict:
        hooks = d.setdefault("hooks", {})
        for event, items in entries.get("hooks", {}).items():
            have = hooks.get(event, [])
            for item in items:
                item = dict(item)
                feature = item.pop("feature", None)
                if feature is not None and not feats.get(feature, False):
                    continue
                if item not in have:
                    have.append(item)
                    hooks[event] = have
        return d

    ctx.merge(hooks_dst, add, "codex hooks")
    skill_src = src / "skills" / "handoff-note"
    if skill_src.exists():
        ctx.copy_tree(skill_src, skill_dst)
    snippet = src / "config.toml.snippet"
    if snippet.exists():
        print("--- add to ~/.codex/config.toml (installer never writes TOML) ---")
        print(snippet.read_text())
    cfg = ctx.home / ".codex" / "config.toml"
    has = False
    if cfg.exists():
        import tomllib
        try:
            has = "features" in tomllib.loads(cfg.read_text())
        except tomllib.TOMLDecodeError:
            ctx.say(f"warning: {cfg} is not valid TOML")
    ctx.say(f"{cfg}: [features] table {'already exists; merge the snippet by hand' if has else 'not present; append the snippet'}")


# --- weekly report ----------------------------------------------------------------------

def plist_text(script: Path) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.harness-habits.weekly-report</string>
  <key>ProgramArguments</key>
  <array><string>python3</string><string>-I</string><string>{script}</string><string>--write</string></array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
</dict>
</plist>
"""


def do_report_cron(ctx: Ctx, uninstall: bool) -> None:
    script = ctx.data / "bin" / "weekly_report.py"
    plist = ctx.home / "Library" / "LaunchAgents" / PLIST_NAME
    mac = sys.platform == "darwin"
    if uninstall:
        if mac and plist.exists() and ctx.real_home:
            ctx.run(["launchctl", "unload", str(plist)])
        ctx.remove(plist)
        return
    if (ROOT / "shared" / "py" / "bin" / "weekly_report.py").exists():
        install_runtime(ctx)
    else:
        ctx.say("notice: weekly_report.py is not in shared/py/bin yet; scheduling will point at a script that does not exist until it ships")
        install_runtime(ctx)
    if mac:
        ctx.say(f"write {plist}")
        if not ctx.dry:
            plist.parent.mkdir(parents=True, exist_ok=True)
            plist.write_text(plist_text(script))
        if ctx.real_home:
            ctx.run(["launchctl", "load", str(plist)], external=False)
        else:
            ctx.say("skip launchctl load (custom --home)")
    else:
        print(f"add to crontab: 0 9 * * 1 python3 -I {script} --write")


# --- main -------------------------------------------------------------------------------

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Install harness-habits")
    for flag in ("claude", "claude-dev", "statusline", "opencode", "codex", "report-cron", "all", "uninstall", "dry-run"):
        ap.add_argument("--" + flag, action="store_true")
    ap.add_argument("--features")
    ap.add_argument("--home")
    a = ap.parse_args(argv)
    ctx = Ctx(Path(a.home) if a.home else Path.home(), a.dry_run, bool(a.home))
    feats = parse_features(a.features) if a.features is not None else None
    sel = {k: getattr(a, k.replace("-", "_")) or a.all for k in ("claude", "statusline", "opencode", "codex", "report-cron")}
    if not any(sel.values()) and not a.claude_dev and feats is None:
        ap.print_help()
        return
    if a.claude_dev and not a.uninstall:
        do_claude_dev(ctx)
    if feats is not None and not a.uninstall:
        do_features(ctx, feats)
    if sel["claude"]:
        do_claude(ctx, a.uninstall)
    if sel["statusline"]:
        do_statusline(ctx, a.uninstall)
    if sel["opencode"]:
        do_opencode(ctx, feats, a.uninstall)
    if sel["codex"]:
        do_codex(ctx, effective_features(ctx, feats), a.uninstall)
    if sel["report-cron"]:
        do_report_cron(ctx, a.uninstall)


if __name__ == "__main__":
    main()
