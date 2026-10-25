# Handoff notes (OpenCode)

Feature key: `handoff` (on by default). OpenCode only.

After each turn (debounced by `debounceMs`, subagent sessions skipped) the plugin writes a short
Markdown note to `<worktree>/.opencode/handoff/<sessionID>.md`:

- title and session id, with the session's last-updated time
- the last `handoff.userMessages` user messages (default 5), newest last
- the last assistant message, cut at 2000 characters
- open todos (status other than `completed`)
- files edited (approximate: `file.edited` events carry no session id, so they are attributed to the
  most recently active session)

The write is skipped when the content hash matches the previous write. On the first write inside a git
repository, `.opencode/handoff/` is appended to `.git/info/exclude` so notes do not show up in `git status`.
A final write happens on `dispose` and `server.instance.disposed`.

When a new session starts, the newest note younger than `handoff.maxAgeDays` (default 7) is announced once
in the system prompt as a path, not as content. The note's current text is also added to the compaction
prompt for its own session. Notes are never deleted by the plugin.

Options (`<config dir>/opencode.json`): `handoff.maxAgeDays`, `handoff.userMessages`, `debounceMs`.

## Just this one

OpenCode: each feature has its own dependency-free bundle with plugin id `harness-habits-handoff`. Copy it without the all-in-one plugin:

```sh
cp opencode/dist/features/handoff.js ~/.config/opencode/plugins/
```

Options come from `~/.config/harness-habits/opencode.json`: `handoff.maxAgeDays`, `handoff.userMessages`, `debounceMs`. Do not install it together with `harness-habits.js`, which already contains the feature.
