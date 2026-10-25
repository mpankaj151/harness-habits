import { test } from "node:test";
import assert from "node:assert/strict";
import { compose } from "../compose.ts";
import { createIdleCompaction, contextLimit } from "./idle-compaction.ts";
import { defaultOptions } from "../options.ts";
import { asstMsg, fakeClient, fakeDeps, userMsg } from "../shared/testing.ts";

const idleEv = (id = "s1") => ({ event: { type: "session.idle", properties: { sessionID: id } } });

function setup(opts: { messages?: any[]; cfg?: any; options?: (o: any) => void; onSummarize?: any } = {}) {
  const f = fakeDeps();
  const { client, state } = fakeClient(
    { sessions: { s1: { id: "s1" } }, messages: { s1: opts.messages ?? [] } },
    opts.onSummarize,
  );
  const options = defaultOptions();
  options.features["idle-compaction"] = true;
  options.compaction.disableForProviders = [];
  opts.options?.(options);
  const hooks: any = compose([{ key: "idle-compaction", feature: createIdleCompaction({ deps: f.deps }) }], {
    client,
    directory: "/w",
    options,
    input: {} as any,
  });
  return { f, state, hooks, options };
}
const big = (total: number, extra: any = {}) => [userMsg("x", 1), asstMsg("y", 2, { tokens: { total, input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } }, ...extra })];
async function idle(h: any, f: any, id = "s1") {
  await h.event(idleEv(id));
  await f.fire();
}

test("contextLimit chain: option map, then config hook, then 200000", () => {
  const cfg = { provider: { anthropic: { models: { claude: { limit: { context: 50000 } } } } } };
  assert.equal(contextLimit({ "anthropic/claude": 1000 }, cfg, "anthropic", "claude"), 1000);
  assert.equal(contextLimit({}, cfg, "anthropic", "claude"), 50000);
  assert.equal(contextLimit(undefined, undefined, "anthropic", "claude"), 200000);
  assert.equal(contextLimit({}, cfg, "x", "y"), 200000);
});

test("threshold math: pct of default 200000 context (0.6 -> 120000)", async () => {
  const lo = setup({ messages: big(119999) });
  await idle(lo.hooks, lo.f);
  assert.equal(lo.state.summarized.length, 0);
  const hi = setup({ messages: big(120000) });
  await idle(hi.hooks, hi.f);
  assert.equal(hi.state.summarized.length, 1);
  assert.deepEqual(hi.state.summarized[0], { path: { id: "s1" }, body: { providerID: "anthropic", modelID: "claude" } });
  assert.match(hi.state.toasts[0].body.message, /^harness-habits compacted the session at 60% of context$/);
});

test("threshold uses contextLimits option", async () => {
  const s = setup({ messages: big(600), options: (o) => (o.compaction.contextLimits = { "anthropic/claude": 1000 }) });
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 1);
});

test("threshold uses limit captured by the config hook", async () => {
  const s = setup({ messages: big(30000) });
  await s.hooks.config({ provider: { anthropic: { models: { claude: { limit: { context: 40000 } } } } } });
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 1); // 30000 >= 0.6 * 40000
});

test("absoluteTokens overrides pct and context", async () => {
  const s = setup({ messages: big(5), options: (o) => (o.compaction.absoluteTokens = 5) });
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 1);
});

test("tokens fall back to input + output + cache when total is missing", async () => {
  const m = [userMsg("x", 1), asstMsg("y", 2, { tokens: { input: 50, output: 20, reasoning: 0, cache: { read: 25, write: 5 } } })];
  const s = setup({ messages: m, options: (o) => (o.compaction.absoluteTokens = 100) });
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 1);
  const s2 = setup({ messages: m, options: (o) => (o.compaction.absoluteTokens = 101) });
  await idle(s2.hooks, s2.f);
  assert.equal(s2.state.summarized.length, 0);
});

test("skips when there is no assistant message or the last one is a summary", async () => {
  const a = setup({ messages: [userMsg("x")], options: (o) => (o.compaction.absoluteTokens = 1) });
  await idle(a.hooks, a.f);
  const b = setup({ messages: big(999999, { summary: true }) });
  await idle(b.hooks, b.f);
  assert.equal(a.state.summarized.length + b.state.summarized.length, 0);
});

test("provider disable list", async () => {
  const s = setup({ messages: big(999999), options: (o) => (o.compaction.disableForProviders = ["Anthropic"]) });
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 0);
});

test("cooldown blocks a second compaction until it elapses; inflight cleared by session.compacted", async () => {
  const s = setup({ messages: big(999999) });
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 1);
  await s.hooks.event({ event: { type: "session.compacted", properties: { sessionID: "s1" } } });
  s.f.advance(30000);
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 1); // cooldown 60000
  s.f.advance(31000);
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 2);
});

test("inflight blocks until session.compacted or the 120 s timer", async () => {
  const s = setup({ messages: big(999999), options: (o) => (o.compaction.cooldownMs = 0) });
  await idle(s.hooks, s.f);
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 1); // still inflight
  await s.hooks.event({ event: { type: "session.compacted", properties: { sessionID: "s1" } } });
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 2);
  // 120 s expiry: the timer set when inflight was added clears it
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 2);
  await s.f.fire(200000); // fires the pending 120 s timer
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 3);
});

test("loop guard: summarize produces a summary message, the follow-up idle does not summarize again", async () => {
  const s = setup({
    messages: big(999999),
    options: (o) => (o.compaction.cooldownMs = 0),
    onSummarize: (_a: any, st: any) => st.messages.s1.push(asstMsg("summary", 10, { summary: true })),
  });
  await idle(s.hooks, s.f);
  await s.hooks.event({ event: { type: "session.compacted", properties: { sessionID: "s1" } } });
  await idle(s.hooks, s.f); // the idle that follows a compaction
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 1);
});

test("a failing summarize releases inflight and does not throw", async () => {
  const s = setup({ messages: big(999999), options: (o) => (o.compaction.cooldownMs = 0), onSummarize: () => { throw new Error("nope"); } });
  await idle(s.hooks, s.f);
  await idle(s.hooks, s.f);
  assert.equal(s.state.summarized.length, 2);
});
