import { test } from "node:test";
import assert from "node:assert/strict";
import { compose } from "../compose.ts";
import { createOutputGuard } from "./output-guard.ts";
import { defaultOptions } from "../options.ts";

const big = { lineCount: (p: string) => (p === "big.txt" ? 800 : null) };

function hooks() {
  const logs: any[] = [];
  const h = compose([{ key: "output-guard", feature: createOutputGuard(() => big) }], {
    client: { app: { log: (a: any) => logs.push(a) } },
    directory: "/work",
    options: defaultOptions(),
    input: {} as any,
  });
  return { h, logs };
}
const inp = { tool: "bash", sessionID: "s", callID: "c" };

test("rewrite mutates args in place", async () => {
  const { h, logs } = hooks();
  const args: any = { command: "grep -r foo ." };
  const output = { args };
  await h["tool.execute.before"]!(inp, output);
  assert.equal(output.args, args);
  assert.equal(args.command, "grep -r foo . | head -n 200");
  assert.equal(logs.length, 1);
  assert.equal(logs[0].body.service, "harness-habits");
});

test("deny throws through compose with the message", async () => {
  const { h } = hooks();
  await assert.rejects(h["tool.execute.before"]!(inp, { args: { command: "cat big.txt" } }), /big\.txt has 800 lines/);
});

test("advise logs and leaves command", async () => {
  const { h, logs } = hooks();
  const args = { command: "grep -r foo . | sort" };
  await h["tool.execute.before"]!(inp, { args });
  assert.equal(args.command, "grep -r foo . | sort");
  assert.match(logs[0].body.message, /no output bound/);
});

test("ignores other tools and non-string commands", async () => {
  const { h } = hooks();
  const a: any = { command: "cat big.txt" };
  await h["tool.execute.before"]!({ ...inp, tool: "read" }, { args: a });
  await h["tool.execute.before"]!(inp, { args: { command: 5 } });
  await h["tool.execute.before"]!(inp, { args: undefined });
});
