import { test } from "node:test";
import assert from "node:assert/strict";
import { compose } from "../compose.ts";
import { cacheBreak } from "./cache-break.ts";
import { defaultOptions } from "../options.ts";
import { fakeClient } from "../shared/testing.ts";

function setup() {
  const { client, state } = fakeClient();
  const hooks: any = compose([{ key: "cache-break", feature: cacheBreak }], { client, directory: "/w", options: defaultOptions(), input: {} as any });
  const run = (tool: string, filePath: any, sessionID = "s1", where: "input" | "output" = "input") =>
    hooks["tool.execute.after"](
      { tool, sessionID, callID: "c", args: where === "input" ? { filePath } : undefined },
      { title: "", output: "", metadata: {}, ...(where === "output" ? { args: { filePath } } : {}) },
    );
  return { state, run };
}

test("toasts once per (session, file) for watched files", async () => {
  const s = setup();
  await s.run("edit", "/w/AGENTS.md");
  await s.run("write", "/other/AGENTS.md");
  assert.equal(s.state.toasts.length, 1);
  assert.equal(
    s.state.toasts[0].body.message,
    "AGENTS.md changed; it is part of the prompt prefix, so the next turn re-reads the full prefix (cache miss).",
  );
  await s.run("edit", "/w/CLAUDE.md");
  await s.run("write", "/w/opencode.json", "s1", "output");
  await s.run("edit", "/w/opencode.jsonc");
  await s.run("edit", "/w/AGENTS.md", "s2");
  assert.equal(s.state.toasts.length, 5);
});

test("ignores other tools and files", async () => {
  const s = setup();
  await s.run("read", "/w/AGENTS.md");
  await s.run("bash", "/w/AGENTS.md");
  await s.run("edit", "/w/src/index.ts");
  await s.run("edit", undefined);
  await s.run("edit", "/w/AGENTS.md.bak");
  assert.equal(s.state.toasts.length, 0);
});
