# harness-habits v0.1 implementation plan

Spec: `~/.claude/plans/delightful-chasing-marble.md` (approved 2026-10-25).
Repo root: `~/Documents/Projects/personal-projects/self/harness-habits`, branch `build/v0.1`.
Developer reference notes (read the one your task names): `docs/dev/claude-hooks.md`,
`docs/dev/opencode-plugin-api.md`, `docs/dev/codex-hooks.md`.

## Global Constraints

- Name everywhere: `harness-habits`. Plugin id `harness-habits`. Env prefix `HH_`.
- Config dir: `$XDG_CONFIG_HOME/harness-habits` (default `~/.config/harness-habits`).
  Data dir: `$XDG_DATA_HOME/harness-habits` (default `~/.local/share/harness-habits`).
- Feature keys (exact strings): `output-guard`, `size-lint`, `cache-break`, `handoff`,
  `idle-compaction`, `cost-logger`, `tool-budget`, `precompact-snapshot`.
  Defaults: all `true` except `idle-compaction: false` and `tool-budget: false`.
- Feature resolution order (last wins): defaults ← `<config dir>/features.json`
  ← env `HH_FEATURE_<KEY_UPPER_WITH_UNDERSCORES>` (`0`/`false`/`off` = off, anything else = on)
  ← env `CLAUDE_PLUGIN_OPTION_<KEY_UPPER_WITH_UNDERSCORES>` (same parsing). Example key
  `output-guard` → `HH_FEATURE_OUTPUT_GUARD`, `CLAUDE_PLUGIN_OPTION_OUTPUT_GUARD`.
- Python: 3.11+, stdlib only, every script runs under `python3 -I`. Scripts live in
  `shared/py/bin/` and import `harness_habits` from `shared/py/` via `sys.path.insert(0, <bin>/..)`.
- Hooks must never break the harness: any exception → behave as "allow / no output", write one
  line to stderr prefixed `harness-habits:`, exit 0. Disabled feature → exit 0 with no stdout.
- TypeScript: `opencode/src/**`, built by esbuild to `opencode/dist/harness-habits.js` (ESM,
  zero runtime imports, `@opencode-ai/plugin` imported as `import type` only). Tests with
  `node --test` on Node 25 (type-stripping: no enums, no parameter properties, no namespaces).
- Both engines read the same rules file `shared/rules/output-guard.json` and pass the same
  fixtures in `tests/fixtures/output-guard/*.json`.
- Tests: Python `pytest` (run `uv run --with pytest pytest tests/py`), TS `node --test`.
  TDD: write the failing test first for engine and hook I/O work.
- Commits: conventional subjects (`feat:`, `test:`, `docs:`, `chore:`), one or more per task,
  ending with the attribution line `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
  Never push. Never publish to npm. Never edit files under `~/.claude`, `~/.config/opencode`,
  `~/.codex` (the installer is tested only against temp HOMEs).
- Messages the model sees are factual statements, not imperatives ("X has 800 lines (limit 500).
  A line range such as `sed -n '1,200p' X` keeps output bounded." not "Do not cat large files").

## Task 1: Scaffold, shared rules, Python guard engine, Claude PreToolUse hook

Files to create:
- `LICENSE` (MIT, copyright 2026 Pankaj Modi), `.gitignore` (`node_modules/`, `__pycache__/`,
  `.pytest_cache/`, `.superpowers/`, `*.bak.*`, `.venv/`), `README.md` (one paragraph stub).
- `.claude-plugin/plugin.json`:
  `{"name":"harness-habits","version":"0.1.0","description":"Install-once token, memory and cost hygiene for Claude Code, OpenCode and Codex CLI","author":{"name":"Pankaj Modi"},"repository":"https://github.com/mpankaj151/harness-habits","license":"MIT","keywords":["hooks","tokens","compaction","memory","cost"]}`
- `.claude-plugin/marketplace.json`:
  `{"name":"harness-habits","owner":{"name":"Pankaj Modi"},"plugins":[{"name":"harness-habits","source":"./","description":"Install-once token, memory and cost hygiene"}]}`
- `shared/rules/output-guard.json` exactly:
```json
{
  "version": 1,
  "max_lines": 500,
  "head_n": 200,
  "full_read_commands": ["cat", "less", "more"],
  "unbounded_commands": ["grep", "rg", "find"],
  "ls_recursive_flags": ["-R", "--recursive"],
  "skip_flags": {
    "grep": ["-c", "-l", "-L", "-q", "--count", "--files-with-matches", "--files-without-match", "--quiet"],
    "rg":   ["-c", "-l", "--count", "--files", "--files-with-matches", "--count-matches", "-q", "--quiet"],
    "find": ["-exec", "-execdir", "-delete", "-ok", "-okdir"]
  },
  "bounding_commands": ["head", "tail", "wc", "less", "more"],
  "follow_flags": ["-f", "-F", "--follow"],
  "operators": ["|", "||", "&&", ";", "&", ">", ">>", "<", "<<", "<<<", "2>", "2>>", "&>", "(", ")"],
  "messages": {
    "deny_full_read": "harness-habits: {path} has {lines} lines (limit {max}). A line range keeps output bounded, for example: sed -n '1,{head}p' {path}",
    "deny_follow": "harness-habits: `tail {flag}` never returns. `tail -n {head} {path}` shows the end once.",
    "rewrite_note": "harness-habits appended `| head -n {head}` to bound the output.",
    "advise_unbounded": "harness-habits: `{cmd}` in this pipeline has no output bound. `| head -n {head}`, `-l` or `-c` keeps the result small.",
    "advise_read": "harness-habits: {path} has {lines} lines. Read without `limit` loads all of them; `offset`/`limit` or a grep first keeps context small."
  }
}
```
- `shared/py/harness_habits/__init__.py` (version string `__version__ = "0.1.0"`).
- `shared/py/harness_habits/paths.py`: `config_dir()`, `data_dir()`, `rules_path()` (resolve
  `shared/rules/output-guard.json` relative to the package: `Path(__file__).resolve().parents[2] / "rules"`).
- `shared/py/harness_habits/features.py`: `enabled(key: str) -> bool` implementing the Global
  Constraints resolution order; `load_features() -> dict`. Unknown key → `False`.
- `shared/py/harness_habits/hookio.py`: `read_json_stdin() -> dict` (empty/invalid → `{}`),
  `emit(obj: dict) -> None` (json.dumps to stdout), `warn(msg)` (stderr, prefixed), and a
  decorator/context `safe_main(fn)` that catches every exception → `warn` + exit 0.
- `shared/py/harness_habits/shellsplit.py`: `split(command: str) -> list[str]` using
  `shlex.shlex(command, posix=True, punctuation_chars=True)` with `whitespace_split=True`; on
  `ValueError` (unbalanced quotes) return `None`. `segments(tokens) -> list[list[str]]` splits on
  operator tokens from the rules file; `is_composed(tokens) -> bool` true when any operator token
  present OR the raw command contains `$(` or a backtick or a heredoc `<<`.
- `shared/py/harness_habits/guard.py`:
  - `@dataclass Decision: action: Literal["allow","deny","rewrite","advise"]; command: str|None=None; message: str|None=None`
  - `class FileSystem` protocol with `line_count(path: str) -> int | None` (None = missing,
    unreadable, directory, or binary [NUL byte in first 8 KiB]); `RealFS(cwd)` implementation that
    resolves relative paths against cwd, expands `~`, stops counting at `max_lines + 1`.
  - `evaluate(command: str, cwd: str, fs: FileSystem, rules: dict) -> Decision`:
    1. tokens = split(command); None or empty → allow.
    2. composed = is_composed. If composed: look at the FIRST segment; if its command is in
       `unbounded_commands`, none of its `skip_flags` present, and no token in the whole command is
       in `bounding_commands` → `advise` with `advise_unbounded`. Otherwise allow. (Never rewrite or
       deny a composed command.)
    3. Simple command (one segment), cmd = basename of token 0 (strip a leading `sudo`, `command`,
       `nice`, `time`, `env` is NOT stripped):
       - cmd in `full_read_commands`: paths = tokens that do not start with `-`; if any path contains
         `*`, `?` or `[` → advise `advise_read`-style? NO: → allow (globs are not resolved in v0.1).
         For each path, `fs.line_count`; if any count > `max_lines` → `deny` with `deny_full_read`
         (first offending path). Else allow.
       - cmd == `tail` and any token in `follow_flags` → `deny` with `deny_follow` ({flag} = the
         token, {path} = last non-flag token or `<file>`).
       - cmd in `unbounded_commands` and no `skip_flags[cmd]` token present → `rewrite`:
         `command + " | head -n " + head_n`, message `rewrite_note`.
       - cmd == `ls` and any `ls_recursive_flags` token → `rewrite` same way.
       - else allow.
    4. Any exception → allow.
  - `evaluate_read(file_path: str, limit, cwd, fs, rules) -> Decision` for Claude's Read tool:
    `limit` falsy and `line_count > max_lines` → `advise` with `advise_read`; else allow.
- `shared/py/bin/claude_pretooluse.py`: reads stdin; if `tool_name == "Bash"` and
  `features.enabled("output-guard")`: evaluate `tool_input.command` with `RealFS(cwd)`.
  Output (stdout JSON, exit 0):
  - deny → `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":<message>}}`
  - rewrite → `{"hookSpecificOutput":{"hookEventName":"PreToolUse","updatedInput":{...tool_input, "command": <new>},"additionalContext":<message>}}`
    (no `permissionDecision` key)
  - advise → `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":<message>}}`
  - allow → no stdout.
  If `tool_name == "Read"`: `evaluate_read(tool_input.file_path, tool_input.get("limit"))` → advise
  as above or nothing. Any other tool → nothing.
- `hooks/hooks.json`:
```json
{
  "description": "harness-habits: token, memory and cost hygiene",
  "hooks": {
    "PreToolUse": [
      {"matcher": "Bash|Read",
       "hooks": [{"type": "command", "command": "python3 -I \"${CLAUDE_PLUGIN_ROOT}/shared/py/bin/claude_pretooluse.py\"", "timeout": 10}]}
    ]
  }
}
```
  (later tasks append more events to this file.)
- Fixtures `tests/fixtures/output-guard/*.json`, one JSON array per file, each case
  `{"name": str, "command": str, "cwd": "/work", "files": {"<relative path>": <line count>},
  "expect": {"action": ..., "command"?: str, "message_contains"?: str}}`. Required cases (at least):
  `cat big.txt` (800) → deny containing "800 lines"; `cat small.txt` (10) → allow; `cat -n big.txt`
  → deny; `cat a.txt b.txt` (10, 900) → deny; `cat *.log` → allow; `less big.txt` → deny;
  `grep -r foo .` → rewrite `grep -r foo . | head -n 200`; `grep -c foo file` → allow;
  `grep -l foo .` → allow; `rg foo` → rewrite; `rg --files` → allow; `find . -name '*.py'` →
  rewrite; `find . -name x -delete` → allow; `find . -exec rm {} \;` → allow; `ls -R` → rewrite;
  `ls -la` → allow; `tail -f app.log` → deny containing "never returns"; `tail -n 50 app.log` →
  allow; `grep -r foo . | wc -l` → allow; `grep -r foo . | sort` → advise; `grep -c foo . | sort`
  → allow; `cat big.txt | head` → allow; `echo $(cat big.txt)` → allow (composed, first segment
  echo); `git log --oneline` → allow; `cat "big file.txt"` (800, with the space) → deny;
  `cat 'unterminated` → allow; `sudo cat big.txt` → deny; `cat missing.txt` → allow;
  `cat bin.dat` with `"files": {"bin.dat": -1}` meaning binary → allow.
  Fixture `files` with value `-1` means `line_count` returns None.
- `tests/py/conftest.py` adds `shared/py` to `sys.path`. `tests/py/test_guard_fixtures.py`
  iterates every fixture with a `FakeFS` built from `files`. `tests/py/test_claude_pretooluse.py`
  runs the script via `subprocess.run([sys.executable, "-I", script], input=json, env=...)` with a
  temp dir holding a real 800-line file, asserting the exact stdout JSON shapes above, the
  disabled-feature path (`HH_FEATURE_OUTPUT_GUARD=0` → empty stdout, exit 0), and invalid stdin
  → empty stdout, exit 0. `tests/py/test_features.py` covers the resolution order with a temp
  config dir (`XDG_CONFIG_HOME`).
- `docs/output-guard.md`: what it does, the decision table, the "just this one" section with the
  `settings.json` hooks snippet pointing at an absolute path.

Verification: `uv run --with pytest pytest tests/py -q` all green; `claude plugin validate .`
exits 0 (if it rejects root-as-plugin, STOP and report BLOCKED with the exact output);
`echo '{"tool_name":"Bash","tool_input":{"command":"cat big.txt"},"cwd":"<tmp>"}' | python3 -I shared/py/bin/claude_pretooluse.py`
prints a deny.

## Task 2: OpenCode plugin skeleton, options, output guard, esbuild, parity tests

Read `docs/dev/opencode-plugin-api.md` first.
Files:
- `opencode/package.json`: `{"name":"harness-habits","version":"0.1.0","type":"module","main":"dist/harness-habits.js","exports":{".":"./dist/harness-habits.js","./server":"./dist/harness-habits.js"},"files":["dist"],"engines":{"opencode":">=1.18.0"},"scripts":{"build":"node build.mjs","test":"node --test src/**/*.test.ts"},"devDependencies":{"esbuild":"^0.28.2","@opencode-ai/plugin":"1.18.15"}}`.
  Run `npm install` inside `opencode/` (creates `opencode/package-lock.json`, commit it).
- `opencode/build.mjs`: esbuild `bundle: true, format: "esm", platform: "node", target: "es2022",
  outfile: "dist/harness-habits.js"`, entry `src/index.ts`; plus one build per feature entry
  `src/standalone/<feature>.ts` → `dist/features/<feature>.js` (for Task 2 only `output-guard`;
  later tasks add theirs). Inline the rules JSON via esbuild's JSON loader (`import rules from
  "../../shared/rules/output-guard.json"`). Banner comment with name and version.
- `opencode/src/types.ts`: minimal local types for `Hooks`, `PluginInput`, `Event` shapes we use
  (copy only what is needed from `@opencode-ai/plugin`'s `index.d.ts`; `import type` is fine too).
- `opencode/src/log.ts`: `log(client, level, message, extra?)` → `client.app.log({body:{service:"harness-habits", level, message, extra}})` wrapped in try/catch; `toast(client, message, variant)` → `client.tui.showToast`, try/catch.
- `opencode/src/options.ts`: `loadOptions(npmOptions)` merging `defaults ← <config dir>/opencode.json
  (JSON, if present) ← npmOptions ← env HH_FEATURE_*`. Shape:
  `{features: Record<FeatureKey, boolean>, compaction: {pct: 0.6, absoluteTokens?: number, cooldownMs: 60000, disableForProviders: ["ollama"]}, handoff: {maxAgeDays: 7, userMessages: 5}, toolBudget: {budget: 128, providerPattern: "openai|azure", disableFirst: []}, debounceMs: 1500}`.
  Feature defaults as in Global Constraints. Config dir resolution identical to Python (`XDG_CONFIG_HOME`).
- `opencode/src/compose.ts`: `type Feature = (ctx: FeatureContext) => Partial<Hooks>`;
  `compose(features: Feature[], ctx): Hooks` merges hooks: for `event`, `tool.execute.before/after`,
  `experimental.chat.system.transform`, `experimental.session.compacting`, `dispose`, `config` call
  every feature's handler in order, each wrapped in try/catch that logs and continues. Only features
  whose key is enabled are composed.
- `opencode/src/shared/shellsplit.ts`: tokenizer matching Python `shlex` with punctuation_chars:
  respects single/double quotes and backslash escapes, splits off operator runs of `();<>|&`.
  Returns `null` on unbalanced quotes.
- `opencode/src/shared/guard-engine.ts`: `evaluate(command, cwd, fs, rules): Decision` and
  `FileSystem { lineCount(path): number | null }` plus `realFs(cwd)` using `node:fs` (sync read in
  64 KiB chunks, NUL in first 8 KiB → null, stop at max_lines+1). Logic identical to Task 1's
  Python `guard.py` step list.
- `opencode/src/features/output-guard.ts`: `"tool.execute.before"`: if `input.tool === "bash"` and
  `typeof output.args.command === "string"`: decision = evaluate(command, ctx.directory, realFs,
  rules). deny → `throw new Error(message)`. rewrite → `output.args.command = decision.command`
  (mutate in place; never reassign `output.args`) and `log(client, "info", message)`. advise →
  `log(client, "info", message)`.
- `opencode/src/index.ts`: `const server = async (input, options) => compose([...], ctx)`;
  `export default { id: "harness-habits", server }`. No other exports.
- `opencode/src/standalone/output-guard.ts`: same but only that feature, id `harness-habits-output-guard`.
- Tests: `opencode/src/shared/guard-engine.test.ts` loads every `tests/fixtures/output-guard/*.json`
  (path relative to repo root via `import.meta.url`) and asserts parity with the Python expectations
  using a fake fs; `shellsplit.test.ts` with quote/operator cases; `compose.test.ts` proving a
  throwing feature does not stop the next one and a disabled feature is not composed;
  `output-guard.test.ts` proving in-place mutation and throw-on-deny with a fake client.
- `tests/smoke/opencode.sh`: adapted from `<lazy-mcp tutorial>/sandbox/run.sh`:
  creates `tests/smoke/.sandbox/` with `opencode.json` `{"$schema":"https://opencode.ai/config.json","model":"ollama/qwen3.8-fast"}`
  (no mcp), copies `opencode/dist/harness-habits.js` to `.sandbox/plugins/`, writes an 800-line
  `.sandbox/work/big.txt`, runs
  `OPENCODE_CONFIG_DIR=<sandbox> opencode run --print-logs --log-level DEBUG "Run exactly this shell command and show me the result: cat big.txt"`
  from `.sandbox/work`, polls for up to 180 s, kills, greps the log for `service=harness-habits`
  and `has 800 lines`. Add `.sandbox/` to `.gitignore`. Run it once and paste the proof lines into
  the report; if ollama is not running, say so and skip (not a failure).
Commit `opencode/dist/harness-habits.js` and `opencode/dist/features/output-guard.js`.

## Task 3: OpenCode handoff notes and idle compaction

Read `docs/dev/opencode-plugin-api.md` (sections: events, client, compaction, loop guard).
- `opencode/src/shared/idle.ts`: shared idle pipeline used by several features:
  `onIdle(sessionID)` debounced per session (`options.debounceMs`), then
  `client.session.get({path:{id}})` → skip if `parentID` (subagent; cache the answer per session),
  then `client.session.messages({path:{id}, query:{limit: 20}})`, then calls registered idle
  listeners in registration order with `{sessionID, session, messages}`. Listeners are registered
  by features in the order the plugin composes them: handoff before idle-compaction (this order is
  the contract: the note is written before compaction runs).
- `opencode/src/features/handoff.ts`:
  - state per session: `editedFiles: Set<string>` filled from `file.edited` events (attributed to
    the most recently idle/active session; mark approximate in the note), `todos` from
    `todo.updated` (`properties.todos` array, keep as-is), `title` from `session.get`.
  - On idle: build the note: `# Handoff — <title>` / `Session <id>, updated <ISO time>` /
    `## Last user messages` (last `options.handoff.userMessages` user text parts, newest last) /
    `## Last assistant message` (text parts of the last assistant message, truncated to 2000 chars)
    / `## Open todos` (status != completed) / `## Files edited (approximate)` list.
    Write to `<worktree>/.opencode/handoff/<sessionID>.md` with `writeFileSync` (mkdir -p). Skip
    the write when the SHA-1 of the content equals the last written hash for that session.
    On first write in a git repo (`<worktree>/.git` exists), append `.opencode/handoff/` to
    `<worktree>/.git/info/exclude` if not already present.
  - `dispose` and `server.instance.disposed`: final write for every tracked session (sync).
  - `experimental.chat.system.transform`: once per sessionID (not for sessions that this plugin
    instance has already written a note for, not for subagents), find the newest
    `.opencode/handoff/*.md` with mtime < `maxAgeDays`; if found push
    `"A handoff note from a previous session in this project exists at <path>. It lists recent
    messages, open todos and edited files."` onto `output.system`.
  - `experimental.session.compacting`: push the current note text (if any) onto `output.context`.
- `opencode/src/features/idle-compaction.ts`:
  - On idle (after handoff): last assistant message `m`; skip if none, if `m.info.summary === true`,
    if sessionID is in `inflight`, if `Date.now() - lastCompacted[sessionID] < cooldownMs`, or if
    `providerID` matches `options.compaction.disableForProviders`.
    tokens = `m.info.tokens.total ?? input + output + cache.read + cache.write`.
    limit = `options.compaction.absoluteTokens ?? pct * contextLimit(providerID, modelID)`.
    contextLimit chain: `options.compaction.contextLimits["<provider>/<model>"]` →
    `cfg.provider?.[providerID]?.models?.[modelID]?.limit?.context` captured in the `config` hook →
    200000.
    If tokens ≥ limit: `inflight.add`, `await client.session.summarize({path:{id:sessionID}, body:{providerID, modelID}})`,
    toast `"harness-habits compacted the session at <pct>% of context"`, set `lastCompacted`.
    Clear `inflight` on `session.compacted` event or after 120 s.
  - Loop guard test: feed the fake client a message sequence where the summarize call produces a
    `summary: true` assistant message and a second `session.idle`; assert summarize is called once.
- Standalone builds `dist/features/handoff.js`, `dist/features/idle-compaction.js`.
- Tests with a fake client and fake fs/time: debounce, subagent skip, note content, hash skip,
  exclude-file append, system transform once per session and age cutoff, threshold math with each
  contextLimit source, cooldown, inflight, loop guard, provider disable.
- Smoke: extend `tests/smoke/opencode.sh` with a second scenario using
  `<config dir>/opencode.json` `{"features":{"idle-compaction":true},"compaction":{"absoluteTokens":1,"disableForProviders":[]}}`
  so the first idle forces compaction; proof lines: `compacted the session` once and
  `.sandbox/work/.opencode/handoff/*.md` exists. Paste proof into the report (skip if ollama down).
- `docs/handoff.md`, `docs/compaction.md` (including the trade-off paragraph: summary call cost
  plus a cache break versus cheaper later turns; off by default for local models; how to set
  `absoluteTokens`).

## Task 4: OpenCode cost logger, cache-break toast, size-lint transform

- `opencode/src/features/cost-logger.ts`: `event` `message.updated` where
  `info.role === "assistant" && info.time?.completed` and `info.id` not in a bounded `Set` (max
  5000, FIFO) → `appendFileSync(<data dir>/opencode-usage.jsonl, JSON.stringify({ts: new Date().toISOString(), sessionID, messageID: info.id, providerID, modelID, cost: info.cost, tokens_last_step: info.tokens}) + "\n")`.
  mkdir -p data dir. Standalone build `dist/features/cost-logger.js`.
- `opencode/src/features/cache-break.ts`: `tool.execute.after` when `input.tool` is `edit` or
  `write` and `basename(output.args?.filePath ?? input.args?.filePath)` ∈ {`opencode.json`,
  `opencode.jsonc`, `AGENTS.md`, `CLAUDE.md`} → toast once per (session, file):
  `"<file> changed; it is part of the prompt prefix, so the next turn re-reads the full prefix (cache miss)."`.
  Check the real arg name for the edit/write tools in `docs/dev/opencode-plugin-api.md`; if not
  listed, read `<lazy-mcp tutorial>/sandbox/node_modules/@opencode-ai/plugin/dist/tool.d.ts`
  or the OpenCode source clone at
  `<scratch>/oc/packages/opencode/src/tool/{edit,write}.ts`.
- `opencode/src/features/size-lint.ts`: `experimental.chat.system.transform` once per sessionID
  (skip subagents by consulting the idle pipeline's parentID cache, or `client.session.get`):
  compute findings for `<worktree>/AGENTS.md`, `<worktree>/CLAUDE.md`, `~/.config/opencode/AGENTS.md`
  (> 200 lines) and push one factual line per finding onto `output.system`, e.g.
  `"AGENTS.md has 312 lines (guideline 200). Long instruction files cost tokens on every turn."`.
- Tests for each with fake client; dedupe and once-per-session behaviour; data dir honours
  `XDG_DATA_HOME`.
- Rebuild dist; commit dist.
- `docs/cost-report.md` gets a section "OpenCode usage log format" (fields above and the caveat:
  `cost` accumulates across steps within a message, `tokens_last_step` is the last step only).

## Task 5: Claude Code Python hooks: size lint, cache-break, model switch, compaction snapshot

Read `docs/dev/claude-hooks.md`.
- `shared/py/harness_habits/lint.py`: `lint(cwd: Path, home: Path) -> list[Finding]`,
  `Finding(path, lines, bytes, guideline, note)`. Checks: `cwd/CLAUDE.md`, `cwd/.claude/CLAUDE.md`,
  `cwd/AGENTS.md`, `home/.claude/CLAUDE.md` over 200 lines; auto-memory
  `home/.claude/projects/<slug>/memory/MEMORY.md` over 180 lines or over 22528 bytes where
  `slug = re.sub(r"[^A-Za-z0-9]", "-", str(cwd.resolve()))` (verify against the directory names in
  `~/.claude/projects`, e.g. `/Users/alice` → `-Users-alice`); `.claude/rules/` missing while
  `CLAUDE.md` > 200 lines → note "path-scoped rules in .claude/rules/ load only when matching files are touched".
  `format(findings) -> str` one factual line each.
- `shared/py/bin/claude_sessionstart.py`: stdin `source`. If `source in {"startup","clear"}` and
  `size-lint` enabled → findings → `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext": text}}`
  (nothing if no findings). If `source in {"compact","resume"}` and `precompact-snapshot` enabled →
  read `<data dir>/precompact/<session_id>.md` if it exists → additionalContext
  `"Snapshot taken before the last compaction of this session:\n" + text`. If env
  `HH_STARTUP_HANDOFF=1` and `source == "startup"` → newest snapshot whose header `cwd:` equals
  this cwd and age < 7 days. Both contexts may be concatenated.
- `shared/py/harness_habits/transcript.py`: `extract(path: Path) -> Snapshot` streaming JSONL:
  user text messages (last 5), last assistant text, latest `TodoWrite` tool_use input `todos`,
  edited file paths from `Edit|Write|MultiEdit|NotebookEdit` tool_use inputs (`file_path` /
  `notebook_path`), deduped. Tolerant of unknown line shapes. `render(snapshot, cwd, session_id) -> str`
  markdown with a header block `session: <id>` / `cwd: <cwd>` / `written: <ISO>`.
  Build the fixture `tests/fixtures/transcripts/sample.jsonl` from the real shape: inspect one file
  under `~/.claude/projects/-Users-alice/*.jsonl` READ-ONLY to learn the structure (`type`,
  `message.role`, `message.content[]` with `type: text|tool_use|tool_result`), then hand-write a
  small anonymised fixture (no real content).
- `shared/py/bin/claude_precompact.py` and `claude_sessionend.py`: if `precompact-snapshot`
  enabled → extract(`transcript_path`) → write `<data dir>/precompact/<session_id>.md`. Data dir:
  `CLAUDE_PLUGIN_DATA` if set, else `data_dir()`. Never block (no exit 2).
- `shared/py/harness_habits/cachebreak.py` + `shared/py/bin/claude_posttooluse.py`: on
  `tool_name in {"Edit","Write","MultiEdit"}` and `basename(file_path)` ∈ {`CLAUDE.md`, `.mcp.json`,
  `settings.json`, `settings.local.json`} or path contains `/.claude/rules/` → once per
  (session_id, file) using a marker file under `<data dir>/cachebreak/<session_id>.json` →
  `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"<file> is part of the prompt prefix; the next request re-reads the whole prefix at full input price (cache miss)."}}`.
- `shared/py/bin/claude_configchange.py`: same message for stdin `hook_event_name == "ConfigChange"` (file from stdin if present).
- `shared/py/bin/claude_postmodelswitch.py`: if `cache-break` enabled print plain text
  `"Model switched; the prompt cache is per model, so this first turn re-reads the full context at full price."` (plain stdout reaches the model for PostModelSwitch).
- `hooks/hooks.json`: add `SessionStart` (no matcher), `PostToolUse` matcher `Edit|Write|MultiEdit`,
  `ConfigChange`, `PostModelSwitch`, `PreCompact` (no matcher), `SessionEnd`; each `python3 -I "${CLAUDE_PLUGIN_ROOT}/shared/py/bin/<script>.py"`, timeout 10 (PreCompact/SessionEnd 30).
- `shared/py/bin/lint_cli.py [--strict] [--cwd PATH]`: prints findings, exit 1 under `--strict`
  when any; `.pre-commit-hooks.yaml` entry `harness-habits-size-lint`.
- Tests: each script via subprocess with temp HOME/XDG dirs and fixture transcript; lint
  thresholds at 200/201 lines, 180/181, bytes boundary; slug function against the real example.
- `docs/size-lint.md`, `docs/cache-break.md`, `docs/precompact-snapshot.md`, `docs/autocompact-pct.md`
  (`export CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=50` in the shell rc; settings `env` block reportedly
  ignored; cannot raise above default).

## Task 6: Status line wrapper and installer

- `shared/py/harness_habits/statusline.py` + `shared/py/bin/statusline_wrap.py`: read stdin JSON
  once; segment = `"$%.2f · %d%%" % (cost.total_cost_usd or 0, context_window.used_percentage or 0)`
  (segments list configurable via `<config dir>/statusline.json` `{"segments":["cost","ctx"],"wrapped":"bash ~/.claude/statusline-command.sh"}`;
  supported segments `cost`, `ctx`, `model`). If `wrapped` set: run it with `shell=True`, the same
  stdin bytes, timeout 2 s; print `segment + "  " + first line of its stdout`; on failure or timeout
  print segment only. No wrapped → `segment + "  " + model.display_name`.
- `shared/py/harness_habits/jsonmerge.py`: `merge_file(path, mutate: Callable[[dict], dict], backup=True)`:
  read JSON (missing → `{}`), back up to `<path>.bak.<epoch>` only when content will change, write
  atomically (tmp + rename), preserve 2-space indent. Idempotent by construction.
- `install.py` (stdlib, Python 3.11+) and `install.sh` (checks `python3 --version` ≥ 3.11 then
  `exec python3 -I install.py "$@"`). Flags: `--claude` (prints the two `claude plugin ...`
  commands and runs them unless `--dry-run`; `--claude-dev` prints `claude --plugin-dir <repo>`),
  `--statusline`, `--opencode`, `--codex`, `--report-cron`, `--all`, `--features a,b,c`,
  `--uninstall`, `--dry-run`, `--home PATH` (test seam; default `Path.home()`).
  - `--statusline`: copy `statusline_wrap.py` and the `harness_habits` package to
    `<data dir>/bin/`; record the existing `statusLine` object into `<config dir>/statusline.json`
    as `wrapped` (only if its command does not already contain `statusline_wrap.py`); set
    `settings.json["statusLine"] = {"type":"command","command":"python3 -I <data dir>/bin/statusline_wrap.py"}`
    via `jsonmerge`. `--uninstall` restores the recorded object.
  - `--opencode`: copy `opencode/dist/harness-habits.js` to `~/.config/opencode/plugins/harness-habits.js`
    (warn and skip if a different file with the same `id:` string exists); write
    `<config dir>/opencode.json` with the chosen features if absent. `--uninstall` removes the file.
  - `--features`: write `<config dir>/features.json` with the listed keys true and all others false.
  - `--codex`: merge `codex/hooks.json` entries into `~/.codex/hooks.json` (only features enabled),
    copy `codex/skills/handoff-note/` to `~/.agents/skills/handoff-note/`, print the
    `config.toml.snippet` and whether `[features]` already exists in `~/.codex/config.toml`
    (read with `tomllib`; never write TOML). Codex files come from Task 9; if absent, print a notice.
  - `--report-cron`: macOS: write `~/Library/LaunchAgents/com.harness-habits.weekly-report.plist`
    running `python3 -I <data dir>/bin/weekly_report.py --write` Monday 09:00 and `launchctl load`
    unless `--dry-run`; Linux: print the crontab line. (`weekly_report.py` arrives in Task 7; copy
    whatever exists in `shared/py/bin/`.)
  - Every step prints what it did; `--dry-run` prints without writing.
- Tests: `tests/py/test_statusline.py` (with/without wrapped, timeout path using `sleep 5`,
  malformed stdin); `tests/py/test_install.py` runs `install.py --home <tmp> --statusline --opencode --features output-guard,handoff --dry-run`
  and then without `--dry-run`, asserts files, backup creation only on change, second run is a
  no-op (no new `.bak.*`), `--uninstall` restores the original statusLine.
- `docs/install.md`.

## Task 7: Weekly cost report

- `shared/py/harness_habits/report.py` + `shared/py/bin/weekly_report.py [--since 7d|30d|YYYY-MM-DD] [--format md|json] [--write] [--registry PATH] [--usage-log PATH] [--claude-projects PATH]`.
  Section 1 (if registry exists, default `~/.session-browser/registry.db`, read-only `sqlite3`
  URI `file:...?mode=ro`): from table `sessions` columns `session_id, title, folder_name,
  cli_source, model_used, last_activity, input_tokens, output_tokens, cache_read_tokens,
  cache_write_tokens, cost_usd`: totals per `cli_source`, per `model_used`, cache-hit ratio
  `cache_read / (input + cache_read + cache_write)` guarded against zero, top 10 by `cost_usd`.
  `last_activity` may be ISO text or epoch; handle both.
  Section 2 (always separate, never summed with section 1): `<data dir>/opencode-usage.jsonl`
  grouped per `providerID/modelID`: message count, sum of `cost`, note the caveat.
  Fallback for section 1 when registry is absent: walk `~/.claude/projects/*/*.jsonl`, take
  assistant entries' `message.usage` (`input_tokens`, `output_tokens`, `cache_read_input_tokens`,
  `cache_creation_input_tokens`) and `message.model`, dedupe by `message.id` (keep the last
  occurrence), price with `shared/pricing.json` (`{"<model-id-prefix>": {"input": $, "output": $, "cache_read": $, "cache_write": $}}` per million tokens, with a `"default"` entry; mark every
  figure "estimated"). Fill `pricing.json` with conservative placeholder values and a comment
  field `"_note"` saying to edit them; do not invent exact vendor prices.
  `--write` saves to `<data dir>/reports/<ISO-week>.md`.
- Tests: build a temp `registry.db` with the exact `sessions` schema in the test, three harness
  sources, zero-division guard, `since` parsing, fallback path with a fixture transcript including a
  duplicated `message.id`, usage-log section.
- `docs/cost-report.md` completed.

## Task 8: OpenCode tool budget guard

Read `docs/dev/opencode-plugin-api.md` (config hook, events).
CONTROLLER FINDING (2026-10-25, live check against `opencode serve` 1.18.15 with an MCP server
connected): `client.tool.ids()` and `client.tool.list()` return ONLY built-in tools; no HTTP route or
SDK call exposes MCP tool lists to a plugin. The guard therefore cannot count MCP tools up front.
Design, in priority order:
- `opencode/src/features/tool-budget.ts`:
  - `config(cfg)`: capture `cfg.mcp` (name → {enabled?, ...}), `cfg.model`, `cfg.plugin`. Detect
    lazy-mcp: any plugin spec string containing `lazy-mcp`, or `cfg.mcp` non-empty and every entry
    `enabled === false` → set `skip = true` and log once. Server heuristic: `enabledServers =`
    entries with `enabled !== false`; if `enabledServers.length > options.toolBudget.maxServers`
    (default 8) and the configured provider (`cfg.model.split("/")[0]`) matches
    `new RegExp(options.toolBudget.providerPattern, "i")` → remember to toast once after startup:
    `"<n> MCP servers enabled for <provider>. OpenAI-compatible endpoints reject requests with more than 128 tool definitions. Fewer servers per project or lazy loading keeps requests under the cap."`.
    Apply persisted decisions: read `<data dir>/mcp-tool-budget.json`
    `{updated, overBudget: boolean, lastError?: string, servers: [...names], disabled: [...]}`; when
    `overBudget` is true, for each name in `options.toolBudget.disableFirst` present in `cfg.mcp` →
    `cfg.mcp[name].enabled = false`, record in `disabled`, toast once after startup naming them.
  - Reactive detection (the reliable signal): on `event` `session.error`, read
    `properties.error?.data?.message ?? properties.error?.data?.responseBody ?? ""`; if it matches
    `/array too long|maximum length 128|too many tools|tools.*(limit|maximum)/i` → toast
    `"The provider rejected the request because too many tools were attached (<excerpt, 120 chars>). Disable MCP servers for this project or enable lazy loading."`, log, and persist
    `overBudget: true, lastError: <excerpt>` so `disableFirst` applies on the next run. Once per run.
  - Learned prefixes: in `tool.execute.before`, record tool ids containing `_` that are not built-ins
    (`invalid question bash read glob grep edit write task webfetch todowrite websearch skill apply_patch`)
    into `servers` as observed MCP tool names (best-effort, for the report; no gating).
  - Any thrown error inside the feature is caught and logged; never block anything.
- Options: `toolBudget: {maxServers: 8, providerPattern: "openai|azure", disableFirst: []}`
  (`budget` key removed; document that per-tool counting is not available from a plugin).
- Tests with fake client and temp data dir: lazy-mcp detection both ways, server heuristic gating by
  provider pattern, `session.error` regex matching (positive, negative, missing fields), persistence
  and next-run `disableFirst` application, once-per-run toasts, learned-prefix recording.
- Standalone build; rebuild dist; `docs/tool-budget.md` (links to the lazy-mcp tutorial repo
  `<lazy-mcp tutorial>` described as "a colleague's lazy-mcp plugin, documented
  separately" with no code copied, and to `OPENCODE_EXPERIMENTAL_CODE_MODE`).

## Task 9: Codex files, MCP-set templates, docs

Read `docs/dev/codex-hooks.md`.
- `shared/py/bin/codex_pretooluse.py`: same engine; deny →
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason": message + " Suggested: " + suggested}}`
  where for rewrite decisions the default is ALSO deny-with-suggestion (because `updatedInput` on
  Codex auto-approves) unless env `HH_CODEX_REWRITE=1`, in which case
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","updatedInput":{"command": <new>}}}`.
  advise → `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext": message}}`.
- `codex_sessionstart.py`: lint findings as plain stdout. `codex_sessionend.py` and
  `codex_precompact.py`: `transcript.extract(transcript_path)` tolerant of Codex's JSONL shape
  (unknown shape → write whatever user/assistant text lines were found) → `~/.codex/handoff/<session_id>.md`
  (override dir with `HH_CODEX_HANDOFF_DIR`).
- `codex/hooks.json`:
```json
{"hooks":{
  "PreToolUse":[{"matcher":"Bash","hooks":[{"type":"command","command":"python3 -I \"$HH_ROOT/shared/py/bin/codex_pretooluse.py\"","timeout":10}]}],
  "SessionStart":[{"hooks":[{"type":"command","command":"python3 -I \"$HH_ROOT/shared/py/bin/codex_sessionstart.py\"","timeout":10}]}],
  "SessionEnd":[{"hooks":[{"type":"command","command":"python3 -I \"$HH_ROOT/shared/py/bin/codex_sessionend.py\"","timeout":30}]}],
  "PreCompact":[{"hooks":[{"type":"command","command":"python3 -I \"$HH_ROOT/shared/py/bin/codex_precompact.py\"","timeout":30}]}]
}}
```
  `install.py --codex` replaces `$HH_ROOT` with the absolute repo path when merging (Task 6's
  installer: add that substitution in this task).
- `codex/config.toml.snippet`: `[features]\nmemories = true\n` with a comment header.
- `codex/skills/handoff-note/SKILL.md`: `name: handoff-note`, `description: Write a short handoff
  note (done, decisions, open items, files to open first) before ending a long session`, body with
  the template.
- `templates/mcp-sets/claude/.mcp.json`, `templates/mcp-sets/claude/settings.json`
  (`enableAllProjectMcpServers: false`, `enabledMcpjsonServers: [...]`),
  `templates/mcp-sets/opencode/opencode.json` (two servers, one `enabled: false`),
  `templates/mcp-sets/lazy-mcp/lazy-mcp.json` (`{"only": ["..."]}` with a comment in the docs).
- `docs/codex.md` (badge text: "Doc-verified. Not yet exercised against a live Codex binary.
  Hooks need trust via `/hooks` after every change."), `docs/mcp-sets.md`.
- Tests: `codex_pretooluse.py` both modes via subprocess; `codex/hooks.json` parses and every
  `command` references an existing script.

## Task 10: CI, README, Makefile, final polish

- `.github/workflows/ci.yml`: matrix ubuntu-latest + macos-latest; steps: checkout; setup-python
  3.11 and 3.12 (`uv run --with pytest pytest tests/py -q`); setup-node 22 (`cd opencode && npm ci
  && npm run build && npm test`); `git diff --exit-code opencode/dist` (built artefact current);
  `npm i -g @anthropic-ai/claude-code && claude plugin validate .` (allow-failure: false);
  `jq empty hooks/hooks.json codex/hooks.json .claude-plugin/*.json`; `shellcheck install.sh tests/smoke/*.sh`.
- `Makefile`: `test`, `build`, `smoke-opencode`, `lint`, `validate`.
- `README.md`: what it is (one paragraph), the problem table (habit → what it costs → what
  harness-habits does), install per harness (three commands), feature matrix with the three
  pluggability levels, "status: Claude Code and OpenCode tested locally; Codex doc-verified",
  link to each doc, credits (session-browser for registry; the lazy-mcp tutorial as related work).
- `docs/dev/` notes stay. Add `CHANGELOG.md` with `0.1.0`.
- Run the full verification: pytest, node tests, build, `claude plugin validate .`,
  `claude plugin details` is not available for an uninstalled plugin so skip; run
  `tests/smoke/opencode.sh` if ollama is up. Paste all results in the report.
