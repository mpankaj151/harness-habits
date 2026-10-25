import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { compose } from "../compose.ts";
import { costLogger } from "./cost-logger.ts";
import { defaultOptions } from "../options.ts";
import { fakeClient } from "../shared/testing.ts";

function setup() {
  const xdg = mkdtempSync(join(tmpdir(), "hh-cost-"));
  process.env.XDG_DATA_HOME = xdg;
  const { client } = fakeClient();
  const hooks: any = compose([{ key: "cost-logger", feature: costLogger }], { client, directory: xdg, options: defaultOptions(), input: {} as any });
  return { hooks, file: join(xdg, "harness-habits", "opencode-usage.jsonl") };
}
const upd = (info: any, sessionID = "s1") => ({ event: { type: "message.updated", properties: { sessionID, info } } });
const asst = (id: string, extra: any = {}) => ({
  id, role: "assistant", providerID: "anthropic", modelID: "claude", cost: 0.5,
  tokens: { input: 10, output: 5, reasoning: 0, cache: { read: 1, write: 2 } }, time: { created: 1, completed: 2 }, ...extra,
});

test("logs completed assistant message once, honouring XDG_DATA_HOME", async () => {
  const saved = process.env.XDG_DATA_HOME;
  try {
    const s = setup();
    await s.hooks.event(upd(asst("m1")));
    await s.hooks.event(upd(asst("m1", { cost: 0.9 })));
    const lines = readFileSync(s.file, "utf8").trim().split("\n");
    assert.equal(lines.length, 1);
    const row = JSON.parse(lines[0]);
    assert.deepEqual(
      { ...row, ts: typeof row.ts },
      { ts: "string", sessionID: "s1", messageID: "m1", providerID: "anthropic", modelID: "claude", cost: 0.5,
        tokens_last_step: { input: 10, output: 5, reasoning: 0, cache: { read: 1, write: 2 } } },
    );
    assert.ok(!Number.isNaN(Date.parse(row.ts)));
  } finally {
    if (saved === undefined) delete process.env.XDG_DATA_HOME; else process.env.XDG_DATA_HOME = saved;
  }
});

test("ignores incomplete, user and non-message events", async () => {
  const saved = process.env.XDG_DATA_HOME;
  try {
    const s = setup();
    await s.hooks.event(upd(asst("m2", { time: { created: 1 } })));
    await s.hooks.event(upd({ id: "u1", role: "user", time: { created: 1, completed: 2 } }));
    await s.hooks.event({ event: { type: "session.idle", properties: { sessionID: "s1" } } });
    assert.equal(existsSync(s.file), false);
    await s.hooks.event(upd(asst("m3")));
    assert.equal(readFileSync(s.file, "utf8").trim().split("\n").length, 1);
  } finally {
    if (saved === undefined) delete process.env.XDG_DATA_HOME; else process.env.XDG_DATA_HOME = saved;
  }
});

test("seen set is bounded FIFO at 5000: oldest id can be logged again", async () => {
  const saved = process.env.XDG_DATA_HOME;
  try {
    const s = setup();
    for (let i = 0; i < 5001; i++) await s.hooks.event(upd(asst("id" + i)));
    await s.hooks.event(upd(asst("id5000"))); // still remembered
    await s.hooks.event(upd(asst("id0"))); // evicted
    const lines = readFileSync(s.file, "utf8").trim().split("\n");
    assert.equal(lines.length, 5002);
    assert.equal(JSON.parse(lines[5001]).messageID, "id0");
  } finally {
    if (saved === undefined) delete process.env.XDG_DATA_HOME; else process.env.XDG_DATA_HOME = saved;
  }
});
