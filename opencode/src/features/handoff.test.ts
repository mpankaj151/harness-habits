import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readFileSync, readdirSync, writeFileSync, utimesSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { compose } from "../compose.ts";
import { createHandoff } from "./handoff.ts";
import { defaultOptions } from "../options.ts";
import { asstMsg, fakeClient, fakeDeps, userMsg } from "../shared/testing.ts";

const idleEv = (id = "s1") => ({ event: { type: "session.idle", properties: { sessionID: id } } });
const T0 = Date.parse("2026-10-25T10:00:00Z");

function setup(opts: { git?: boolean; messages?: any[]; sessions?: any; edit?: (o: any) => void } = {}) {
  const dir = mkdtempSync(join(tmpdir(), "hh-handoff-"));
  if (opts.git) mkdirSync(join(dir, ".git", "info"), { recursive: true });
  const f = fakeDeps(T0);
  const sessions = opts.sessions ?? { s1: { id: "s1", title: "Fix the parser", time: { created: T0, updated: T0 } } };
  const messages = opts.messages ?? [
    userMsg("first ask", 1),
    asstMsg("did it", 2),
    userMsg("second ask", 3),
    asstMsg("A".repeat(2500), 4),
  ];
  const { client, state } = fakeClient({ sessions, messages: { s1: messages } });
  const options = defaultOptions();
  opts.edit?.(options);
  const hooks: any = compose([{ key: "handoff", feature: createHandoff({ deps: f.deps }) }], {
    client,
    directory: dir,
    options,
    input: { worktree: dir } as any,
  });
  const noteDir = join(dir, ".opencode", "handoff");
  return { dir, f, state, hooks, noteDir, notePath: join(noteDir, "s1.md") };
}
async function idle(s: any, id = "s1") {
  await s.hooks.event(idleEv(id));
  await s.f.fire();
}

test("note content: title, user messages, truncated assistant, open todos, approximate files", async () => {
  const s = setup({ edit: (o) => (o.handoff.userMessages = 2) });
  await s.hooks.event({ event: { type: "message.updated", properties: { sessionID: "s1", info: { role: "user" } } } });
  await s.hooks.event({ event: { type: "file.edited", properties: { file: "/w/a.ts" } } });
  await s.hooks.event({
    event: {
      type: "todo.updated",
      properties: { sessionID: "s1", todos: [{ content: "write tests", status: "pending" }, { content: "done thing", status: "completed" }] },
    },
  });
  await idle(s);
  const note = readFileSync(s.notePath, "utf8");
  assert.match(note, /^# Handoff — Fix the parser\nSession s1, updated 2026-10-25T10:00:00.000Z\n/);
  assert.match(note, /## Last user messages\n- first ask\n- second ask\n/);
  const asst = note.split("## Last assistant message\n")[1].split("\n\n## Open todos")[0];
  assert.equal(asst.length, 2000);
  assert.match(note, /## Open todos\n- \[pending\] write tests\n/);
  assert.doesNotMatch(note, /done thing/);
  assert.match(note, /## Files edited \(approximate\)\n- \/w\/a\.ts\n/);
});

test("user message count is limited, newest last", async () => {
  const s = setup({ edit: (o) => (o.handoff.userMessages = 1) });
  await idle(s);
  const note = readFileSync(s.notePath, "utf8");
  assert.match(note, /- second ask/);
  assert.doesNotMatch(note, /first ask/);
});

test("identical content is not rewritten (hash skip)", async () => {
  const s = setup();
  await idle(s);
  const old = new Date(T0 - 3600_000);
  utimesSync(s.notePath, old, old);
  const before = (await import("node:fs")).statSync(s.notePath).mtimeMs;
  await idle(s);
  assert.equal((await import("node:fs")).statSync(s.notePath).mtimeMs, before);
  await s.hooks.event({ event: { type: "file.edited", properties: { file: "b.ts" } } });
  await idle(s);
  assert.match(readFileSync(s.notePath, "utf8"), /b\.ts/);
});

test("git repo: .opencode/handoff/ appended to info/exclude once", async () => {
  const s = setup({ git: true });
  await idle(s);
  await s.hooks.event({ event: { type: "file.edited", properties: { file: "c.ts" } } });
  await idle(s);
  const ex = readFileSync(join(s.dir, ".git", "info", "exclude"), "utf8");
  assert.equal(ex.split("\n").filter((l) => l === ".opencode/handoff/").length, 1);
});

test("no .git: no exclude file is created", async () => {
  const s = setup();
  await idle(s);
  assert.equal(existsSync(join(s.dir, ".git")), false);
});

test("subagent sessions get no note", async () => {
  const s = setup({ sessions: { s1: { id: "s1", parentID: "p", title: "t", time: {} } } });
  await idle(s);
  assert.equal(existsSync(s.notePath), false);
});

test("dispose and server.instance.disposed write a final note for tracked sessions", async () => {
  const s = setup();
  await idle(s);
  await s.hooks.event({ event: { type: "file.edited", properties: { file: "late.ts" } } });
  await s.hooks.dispose();
  assert.match(readFileSync(s.notePath, "utf8"), /late\.ts/);
  await s.hooks.event({ event: { type: "file.edited", properties: { file: "later.ts" } } });
  await s.hooks.event({ event: { type: "server.instance.disposed", properties: {} } });
  assert.match(readFileSync(s.notePath, "utf8"), /later\.ts/);
});

function oldNote(dir: string, name: string, ageDays: number) {
  const nd = join(dir, ".opencode", "handoff");
  mkdirSync(nd, { recursive: true });
  const p = join(nd, name);
  writeFileSync(p, "old");
  const t = new Date(T0 - ageDays * 86400_000);
  utimesSync(p, t, t);
  return p;
}

test("system transform: newest fresh note, the same text on every call; age cutoff", async () => {
  const s = setup({ sessions: { n1: { id: "n1" }, n2: { id: "n2" } } });
  oldNote(s.dir, "x-stale.md", 30);
  const p = oldNote(s.dir, "x-fresh.md", 1);
  oldNote(s.dir, "x-fresher-but-old-enough.md", 6);
  const out1 = { system: [] as string[] };
  await s.hooks["experimental.chat.system.transform"]({ sessionID: "n1", model: {} }, out1);
  assert.equal(out1.system.length, 1);
  assert.equal(
    out1.system[0],
    `A handoff note from a previous session in this project exists at ${p}. It lists recent messages, open todos and edited files.`,
  );
  for (let i = 0; i < 3; i++) {
    const again = { system: [] as string[] };
    await s.hooks["experimental.chat.system.transform"]({ sessionID: "n1", model: {} }, again);
    assert.deepEqual(again.system, out1.system);
  }
  oldNote(s.dir, "x-newer-later.md", 0); // a note appearing mid-session does not change the prefix
  const later = { system: [] as string[] };
  await s.hooks["experimental.chat.system.transform"]({ sessionID: "n1", model: {} }, later);
  assert.deepEqual(later.system, out1.system);
  const other = { system: [] as string[] };
  await s.hooks["experimental.chat.system.transform"]({ sessionID: "n2", model: {} }, other);
  assert.equal(other.system.length, 1);
});

test("system transform: nothing when notes are older than maxAgeDays, no sessionID, or subagent", async () => {
  const s = setup({ sessions: { sub: { id: "sub", parentID: "p" } } });
  oldNote(s.dir, "only-old.md", 8);
  const a = { system: [] as string[] };
  await s.hooks["experimental.chat.system.transform"]({ sessionID: "n1", model: {} }, a);
  await s.hooks["experimental.chat.system.transform"]({ model: {} }, a);
  oldNote(s.dir, "fresh.md", 0);
  await s.hooks["experimental.chat.system.transform"]({ sessionID: "sub", model: {} }, a);
  assert.deepEqual(a.system, []);
});

test("system transform: skipped for a session this instance already wrote a note for", async () => {
  const s = setup();
  await idle(s);
  const out = { system: [] as string[] };
  await s.hooks["experimental.chat.system.transform"]({ sessionID: "s1", model: {} }, out);
  assert.deepEqual(out.system, []);
});

test("compacting hook pushes the current note", async () => {
  const s = setup();
  await idle(s);
  const out = { context: [] as string[] };
  await s.hooks["experimental.session.compacting"]({ sessionID: "s1" }, out);
  assert.equal(out.context.length, 1);
  assert.match(out.context[0], /^# Handoff — Fix the parser/);
  const none = { context: [] as string[] };
  await s.hooks["experimental.session.compacting"]({ sessionID: "zzz" }, none);
  assert.deepEqual(none.context, []);
});

test("handoff runs before idle-compaction on the same idle (composition order)", async () => {
  const { createIdleCompaction } = await import("./idle-compaction.ts");
  const dir = mkdtempSync(join(tmpdir(), "hh-order-"));
  const f = fakeDeps(T0);
  const seenAtSummarize: boolean[] = [];
  const { client } = fakeClient(
    { sessions: { s1: { id: "s1", title: "t", time: {} } }, messages: { s1: [userMsg("q", 1), asstMsg("a", 2, { tokens: { total: 9e9, input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } } })] } },
    () => void seenAtSummarize.push(existsSync(join(dir, ".opencode", "handoff", "s1.md"))),
  );
  const options = defaultOptions();
  options.features["idle-compaction"] = true;
  options.compaction.disableForProviders = [];
  const h: any = compose(
    [
      { key: "handoff", feature: createHandoff({ deps: f.deps }) },
      { key: "idle-compaction", feature: createIdleCompaction({ deps: f.deps }) },
    ],
    { client, directory: dir, options, input: { worktree: dir } as any },
  );
  await h.event(idleEv());
  await f.fire();
  assert.deepEqual(seenAtSummarize, [true]);
});

test("dispose flushes a pending debounced idle so a one-turn run still leaves a note", async () => {
  const s = setup();
  await s.hooks.event(idleEv()); // debounce timer pending, never fired
  assert.equal(existsSync(s.notePath), false);
  await s.hooks.dispose();
  assert.match(readFileSync(s.notePath, "utf8"), /^# Handoff — Fix the parser/);
});

test("shutdown flush writes the note but never starts a compaction", async () => {
  const { createIdleCompaction } = await import("./idle-compaction.ts");
  const dir = mkdtempSync(join(tmpdir(), "hh-flush-"));
  const f = fakeDeps(T0);
  const { client, state } = fakeClient({
    sessions: { s1: { id: "s1", title: "t", time: {} } },
    messages: { s1: [userMsg("q", 1), asstMsg("a", 2, { tokens: { total: 9e9, input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } } })] },
  });
  const options = defaultOptions();
  options.features["idle-compaction"] = true;
  options.compaction.disableForProviders = [];
  const h: any = compose(
    [
      { key: "handoff", feature: createHandoff({ deps: f.deps }) },
      { key: "idle-compaction", feature: createIdleCompaction({ deps: f.deps }) },
    ],
    { client, directory: dir, options, input: { worktree: dir } as any },
  );
  await h.event(idleEv());
  await h.dispose();
  assert.equal(existsSync(join(dir, ".opencode", "handoff", "s1.md")), true);
  assert.equal(state.summarized.length, 0);
});
