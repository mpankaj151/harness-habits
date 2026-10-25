import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { compose } from "../compose.ts";
import { createSizeLint } from "./size-lint.ts";
import { defaultOptions } from "../options.ts";
import { fakeClient } from "../shared/testing.ts";

const lines = (n: number) => Array.from({ length: n }, (_, i) => "line " + i).join("\n") + "\n";

function setup(files: Record<string, number>, globalLines?: number) {
  const dir = mkdtempSync(join(tmpdir(), "hh-size-"));
  const g = mkdtempSync(join(tmpdir(), "hh-size-g-"));
  for (const [n, c] of Object.entries(files)) writeFileSync(join(dir, n), lines(c));
  if (globalLines !== undefined) writeFileSync(join(g, "AGENTS.md"), lines(globalLines));
  const { client, state } = fakeClient({ sessions: { s1: { id: "s1" }, sub: { id: "sub", parentID: "s1" } } });
  const hooks: any = compose([{ key: "size-lint", feature: createSizeLint({ globalDir: g }) }], {
    client, directory: dir, options: defaultOptions(), input: { worktree: dir } as any,
  });
  const run = async (sessionID: string | undefined) => {
    const out = { system: [] as string[] };
    await hooks["experimental.chat.system.transform"]({ sessionID, model: {} }, out);
    return out.system;
  };
  return { run, state };
}

test("reports files over 200 lines, the same lines on every call for a session", async () => {
  const s = setup({ "AGENTS.md": 312, "CLAUDE.md": 200 }, 201);
  const out = await s.run("s1");
  assert.deepEqual(out, [
    "AGENTS.md has 312 lines (guideline 200). Long instruction files cost tokens on every turn.",
    "~/.config/opencode/AGENTS.md has 201 lines (guideline 200). Long instruction files cost tokens on every turn.",
  ]);
  assert.deepEqual(await s.run("s1"), out);
  assert.deepEqual(await s.run("s1"), out);
});

test("silent when all files are small or missing", async () => {
  const s = setup({ "AGENTS.md": 10 });
  assert.deepEqual(await s.run("s1"), []);
});

test("skips subagents (via cached session.get) and sessions without id", async () => {
  const s = setup({ "AGENTS.md": 300 });
  assert.deepEqual(await s.run("sub"), []);
  assert.deepEqual(await s.run(undefined), []);
  assert.deepEqual(s.state.gets, ["sub"]);
});
