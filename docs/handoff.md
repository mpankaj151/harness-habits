# Handoff notes

## Why

When a session ends or is compacted, the next one starts without knowing what you were doing. A short note written after every turn lets a new session in the same worktree pick up the thread without you retyping it, and it is announced as a path, not pasted, so it costs almost nothing.

## What you see

- A file `~/.local/share/harness-habits/handoff/<worktree-slug>/<sessionID>.md` (`<data dir>/handoff/...`) after each turn.
- At the start of a new session in the same worktree, the system prompt gains: `A handoff note from a previous session in this project exists at <path>. It lists recent messages, open todos and edited files.`
- On Codex, the `handoff-note` skill (`$handoff-note`) writes `HANDOFF.md` in the working directory when you ask; it is not automatic.

## Setup

### Claude Code

Not applicable; Claude Code uses the [pre-compaction snapshot](precompact-snapshot.md).

### OpenCode

`./install.sh --opencode` (feature `handoff`, on by default).

### Codex CLI

`./install.sh --codex` copies the `handoff-note` skill to `~/.agents/skills/handoff-note`.

## Switch it off

Set `"handoff": false` in `~/.config/harness-habits/features.json`, or export `HH_FEATURE_HANDOFF=0` in the shell that launches the harness.

## Just this one

OpenCode: each feature has its own dependency-free bundle with plugin id `harness-habits-handoff`. Copy it without the all-in-one plugin:

```sh
cp opencode/dist/features/handoff.js ~/.config/opencode/plugins/
```

Options come from `~/.config/harness-habits/opencode.json`: `handoff.maxAgeDays`, `handoff.userMessages`, `debounceMs`. Do not install it together with `harness-habits.js`, which already contains the feature.

## Details / Limits

Feature key: `handoff` (on by default). OpenCode only.

After each turn (debounced by `debounceMs`, subagent sessions skipped) the plugin writes a short
Markdown note (`worktree-slug` is the worktree path with every non-alphanumeric character replaced by `-`):

- title and session id, with the session's last-updated time
- the last `handoff.userMessages` user messages (default 5), newest last
- the last assistant message, cut at 2000 characters
- open todos (status other than `completed`)
- files edited (approximate: `file.edited` events carry no session id, so they are attributed to the
  most recently active session)

The write is skipped when the content hash matches the previous write. Notes live outside the repository,
so there is nothing to git-ignore, worktrees and submodules behave like any other directory, and a `.md`
file a repository ships can never be announced as a handoff note. A final write happens on `dispose` and
`server.instance.disposed`.

When a session starts, the newest note in that worktree's folder younger than `handoff.maxAgeDays`
(default 7) is announced in the system prompt as a path, not as content. The notice is worked out once per
session and the same text is added on every request of that session, so the prompt prefix stays stable and
the cache is not invalidated. The note's current text is also added to the compaction prompt for its own
session. Notes are never deleted by the plugin.

Options (`<config dir>/opencode.json`): `handoff.maxAgeDays`, `handoff.userMessages`, `debounceMs`.
