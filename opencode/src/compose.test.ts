import { test } from "node:test";
import assert from "node:assert/strict";
import { compose } from "./compose.ts";
import type { Feature, FeatureContext } from "./compose.ts";
import { defaultOptions } from "./options.ts";

function ctx(over: Record<string, boolean> = {}): FeatureContext & { logs: any[] } {
  const logs: any[] = [];
  const options = defaultOptions();
  Object.assign(options.features, over);
  return { client: { app: { log: (a: any) => logs.push(a) } }, directory: "/work", options, input: {} as any, logs };
}

test("throwing feature does not stop the next", async () => {
  const c = ctx();
  const seen: string[] = [];
  const bad: Feature = () => ({ event: async () => { throw new Error("boom"); } });
  const good: Feature = () => ({ event: async () => { seen.push("good"); } });
  const hooks = compose([{ key: "output-guard", feature: bad }, { key: "size-lint", feature: good }], c);
  await hooks.event!({ event: { type: "x" } });
  assert.deepEqual(seen, ["good"]);
  assert.ok(c.logs.some((l) => l.body.level === "error" && l.body.message.includes("boom")));
});

test("disabled feature is not composed", async () => {
  const c = ctx({ "size-lint": false });
  const seen: string[] = [];
  const f: Feature = () => ({ event: async () => { seen.push("ran"); } });
  const hooks = compose([{ key: "size-lint", feature: f }], c);
  assert.equal(hooks.event, undefined);
  assert.deepEqual(seen, []);
});

test("initialiser failure is isolated", async () => {
  const c = ctx();
  const bad: Feature = () => { throw new Error("init"); };
  const hooks = compose([{ key: "output-guard", feature: bad }], c);
  assert.deepEqual(Object.keys(hooks), []);
});
