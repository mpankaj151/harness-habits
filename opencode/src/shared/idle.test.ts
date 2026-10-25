import { test } from "node:test";
import assert from "node:assert/strict";
import { getIdle } from "./idle.ts";
import { defaultOptions } from "../options.ts";
import { fakeClient, fakeDeps, userMsg } from "./testing.ts";

function setup(sessions: Record<string, any>) {
  const f = fakeDeps();
  const { client, state } = fakeClient({ sessions, messages: { s1: [userMsg("hi")], s2: [userMsg("sub")] } });
  const ctx: any = { client, directory: "/w", options: defaultOptions(), input: {} };
  const idle = getIdle(ctx, f.deps);
  return { f, state, ctx, idle };
}
const ev = (id = "s1") => ({ type: "session.idle", properties: { sessionID: id } });

test("debounce collapses bursts into one run", async () => {
  const { f, idle } = setup({ s1: { id: "s1" } });
  const calls: any[] = [];
  idle.addListener((p) => void calls.push(p));
  idle.handleEvent(ev());
  idle.handleEvent(ev());
  idle.handleEvent(ev());
  assert.equal(f.pending(), 1);
  await f.fire();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].sessionID, "s1");
  assert.equal(calls[0].messages.length, 1);
});

test("subagent sessions are skipped and the parent lookup is cached", async () => {
  const { f, state, idle } = setup({ s1: { id: "s1" }, s2: { id: "s2", parentID: "s1" } });
  const calls: string[] = [];
  idle.addListener((p) => void calls.push(p.sessionID));
  idle.handleEvent(ev("s2"));
  await f.fire();
  idle.handleEvent(ev("s2"));
  await f.fire();
  assert.deepEqual(calls, []);
  assert.equal(state.gets.filter((g) => g === "s2").length, 1);
  assert.equal(await idle.parents.isSubagent("s2"), true);
  assert.equal(await idle.parents.isSubagent("s1"), false);
});

test("listeners run in registration order; one failing listener does not stop the next", async () => {
  const { f, idle, state } = setup({ s1: { id: "s1" } });
  const order: string[] = [];
  idle.addListener(async () => {
    order.push("a");
    throw new Error("boom");
  });
  idle.addListener(() => void order.push("b"));
  idle.handleEvent(ev());
  await f.fire();
  assert.deepEqual(order, ["a", "b"]);
  assert.match(state.logs[0].body.message, /boom/);
});

test("same event object delivered twice is processed once; other event types ignored", async () => {
  const { f, idle } = setup({ s1: { id: "s1" } });
  const calls: string[] = [];
  idle.addListener((p) => void calls.push(p.sessionID));
  const e = ev();
  idle.handleEvent(e);
  idle.handleEvent(e);
  idle.handleEvent({ type: "session.updated", properties: { sessionID: "s1" } });
  await f.fire();
  assert.deepEqual(calls, ["s1"]);
});

test("flush runs pending idles immediately with final=true and clears the timers", async () => {
  const { f, idle } = setup({ s1: { id: "s1" } });
  const calls: any[] = [];
  idle.addListener((p) => void calls.push(p));
  idle.handleEvent(ev());
  await idle.flush();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].final, true);
  assert.equal(f.pending(), 0);
});
