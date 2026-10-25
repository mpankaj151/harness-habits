import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { compose } from "../compose.ts";
import { toolBudget } from "./tool-budget.ts";
import { defaultOptions } from "../options.ts";

function setup(optsPatch: any = {}, seed?: any) {
  const xdg = mkdtempSync(join(tmpdir(), "hh-tb-"));
  process.env.XDG_DATA_HOME = xdg;
  const file = join(xdg, "harness-habits", "mcp-tool-budget.json");
  if (seed) {
    mkdirSync(join(xdg, "harness-habits"), { recursive: true });
    writeFileSync(file, JSON.stringify(seed));
  }
  const toasts: string[] = [];
  const logs: string[] = [];
  const client = {
    tui: { showToast: async (a: any) => void toasts.push(a.body.message) },
    app: { log: async (a: any) => void logs.push(a.body.message) },
  };
  const options = defaultOptions();
  options.features["tool-budget"] = true;
  Object.assign(options.toolBudget, optsPatch);
  const hooks: any = compose([{ key: "tool-budget", feature: toolBudget }], { client, directory: xdg, options, input: {} as any });
  return { hooks, toasts, logs, file };
}
const servers = (n: number) => Object.fromEntries(Array.from({ length: n }, (_, i) => [`s${i}`, { type: "local" }]));
const err = (message: any) => ({ event: { type: "session.error", properties: { sessionID: "s", error: { name: "APIError", data: message } } } });
const idle = { event: { type: "session.idle", properties: { sessionID: "s" } } };

test("lazy-mcp plugin spec sets skip: no heuristic toast", async () => {
  const s = setup();
  await s.hooks.config({ model: "openai/gpt-5", plugin: ["opencode-lazy-mcp"], mcp: servers(10) });
  await s.hooks.event(idle);
  assert.equal(s.toasts.length, 0);
  assert.ok(s.logs.some((l) => /lazy/i.test(l)));
});

test("all mcp entries disabled counts as lazy; mixed does not", async () => {
  const a = setup();
  await a.hooks.config({ model: "openai/x", mcp: { a: { enabled: false }, b: { enabled: false } } });
  await a.hooks.event(idle);
  assert.equal(a.toasts.length, 0);
  assert.ok(a.logs.some((l) => /lazy/i.test(l)));
  const b = setup();
  await b.hooks.config({ model: "openai/x", mcp: { ...servers(9), z: { enabled: false } } });
  await b.hooks.event(idle);
  assert.equal(b.toasts.length, 1);
});

test("server heuristic gated by provider pattern and maxServers, toasts once", async () => {
  const s = setup();
  await s.hooks.config({ model: "openai/gpt-5", mcp: servers(9) });
  await s.hooks.event(idle);
  await s.hooks.event(idle);
  assert.deepEqual(s.toasts, [
    "9 MCP servers enabled for openai. OpenAI-compatible endpoints reject requests with more than 128 tool definitions. Fewer servers per project or lazy loading keeps requests under the cap.",
  ]);
  const anth = setup();
  await anth.hooks.config({ model: "anthropic/claude", mcp: servers(20) });
  await anth.hooks.event(idle);
  assert.equal(anth.toasts.length, 0);
  const few = setup();
  await few.hooks.config({ model: "azure/x", mcp: servers(8) });
  await few.hooks.event(idle);
  assert.equal(few.toasts.length, 0);
  const nomodel = setup();
  await nomodel.hooks.config({ mcp: servers(20) });
  await nomodel.hooks.event(idle);
  assert.equal(nomodel.toasts.length, 0);
});

test("session.error matches limit messages, persists, toasts once", async () => {
  const s = setup();
  await s.hooks.config({ mcp: servers(1) });
  await s.hooks.event(err({ message: "Invalid 'tools': array too long. Expected maximum length 128" }));
  await s.hooks.event(err({ message: "too many tools" }));
  assert.equal(s.toasts.length, 1);
  assert.match(s.toasts[0], /^The provider rejected the request because too many tools were attached \(Invalid 'tools'/);
  assert.match(s.toasts[0], /Disable MCP servers for this project or enable lazy loading\.$/);
  const saved = JSON.parse(readFileSync(s.file, "utf8"));
  assert.equal(saved.overBudget, true);
  assert.match(saved.lastError, /array too long/);
  assert.deepEqual(saved.disabled, []);
});

test("session.error: responseBody fallback, excerpt capped, non-matches and missing fields ignored", async () => {
  const s = setup();
  await s.hooks.event(err({ message: "rate limited" }));
  await s.hooks.event({ event: { type: "session.error", properties: {} } });
  await s.hooks.event({ event: { type: "session.error" } });
  await s.hooks.event(err({}));
  assert.equal(s.toasts.length, 0);
  assert.equal(existsSync(s.file), false);
  await s.hooks.event(err({ responseBody: "tools exceed the maximum allowed " + "x".repeat(300) }));
  assert.equal(s.toasts.length, 1);
  assert.ok(JSON.parse(readFileSync(s.file, "utf8")).lastError.length <= 120);
});

test("persisted overBudget disables disableFirst servers present in cfg.mcp, toast once", async () => {
  const s = setup({ disableFirst: ["a", "missing", "b"] }, { updated: "x", overBudget: true, servers: [], disabled: [] });
  const cfg: any = { mcp: { a: { enabled: true }, b: {}, c: {} } };
  await s.hooks.config(cfg);
  assert.equal(cfg.mcp.a.enabled, false);
  assert.equal(cfg.mcp.b.enabled, false);
  assert.notEqual(cfg.mcp.c.enabled, false);
  await s.hooks.event(idle);
  await s.hooks.event(idle);
  assert.equal(s.toasts.length, 1);
  assert.match(s.toasts[0], /a, b/);
  assert.deepEqual(JSON.parse(readFileSync(s.file, "utf8")).disabled, ["a", "b"]);
});

test("overBudget false leaves servers alone; corrupt file ignored", async () => {
  const s = setup({ disableFirst: ["a"] }, { overBudget: false });
  const cfg: any = { mcp: { a: {} } };
  await s.hooks.config(cfg);
  assert.equal(cfg.mcp.a.enabled, undefined);
  const c = setup({ disableFirst: ["a"] });
  mkdirSync(join(process.env.XDG_DATA_HOME!, "harness-habits"), { recursive: true });
  writeFileSync(c.file, "{nope");
  await c.hooks.config({ mcp: { a: {} } });
});

test("tool.execute.before records non-builtin ids with underscore", async () => {
  const s = setup();
  await s.hooks.config({ mcp: servers(1) });
  for (const tool of ["bash", "apply_patch", "github_create_issue", "github_create_issue", "plain"]) {
    await s.hooks["tool.execute.before"]({ tool, sessionID: "s", callID: "c" }, { args: {} });
  }
  await s.hooks.event(err({ message: "too many tools" }));
  assert.deepEqual(JSON.parse(readFileSync(s.file, "utf8")).servers, ["github_create_issue"]);
});

test("malformed config does not throw", async () => {
  const s = setup();
  await s.hooks.config({ mcp: "bad", plugin: 5, model: 3 });
  await s.hooks.config(undefined);
});
