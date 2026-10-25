# harness-habits

Install-once token, memory and cost hygiene hooks for Claude Code, OpenCode and Codex CLI. v0.1 starts with an output guard that bounds runaway shell output (recursive grep, find, ls -R) and flags oversized whole-file reads before they flood the context window. Each feature can be switched on or off in a small config file or through environment variables.

Install on Claude Code: `/plugin install harness-habits --marketplace mpankaj151/harness-habits`
