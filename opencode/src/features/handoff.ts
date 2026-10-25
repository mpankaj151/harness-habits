import { createHash } from "node:crypto";
import { appendFileSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Feature } from "../compose.ts";
import { log } from "../log.ts";
import { getIdle, realDeps } from "../shared/idle.ts";
import type { IdleDeps, IdlePayload } from "../shared/idle.ts";

const ASSISTANT_MAX = 2000;
const USER_MAX = 1000;
const EXCLUDE_LINE = ".opencode/handoff/";
const DAY_MS = 86400000;

interface Snapshot {
  session: any;
  messages: any[];
}

function byCreated(messages: any[]): any[] {
  return [...messages].sort((a, b) => (a?.info?.time?.created ?? 0) - (b?.info?.time?.created ?? 0));
}

function textOf(msg: any): string {
  const parts: any[] = Array.isArray(msg?.parts) ? msg.parts : [];
  return parts
    .filter((p) => p?.type === "text" && typeof p.text === "string" && !p.synthetic && !p.ignored)
    .map((p) => p.text)
    .join("\n")
    .trim();
}

export function buildNote(opts: {
  sessionID: string;
  snapshot: Snapshot;
  todos: any[];
  files: string[];
  userMessages: number;
  now: number;
}): string {
  const { sessionID, snapshot, todos, files, userMessages, now } = opts;
  const sorted = byCreated(snapshot.messages);
  const users = sorted
    .filter((m) => m?.info?.role === "user")
    .map(textOf)
    .filter(Boolean)
    .slice(-Math.max(0, userMessages));
  let lastAssistant = "";
  for (let i = sorted.length - 1; i >= 0; i--) {
    if (sorted[i]?.info?.role === "assistant") {
      lastAssistant = textOf(sorted[i]);
      break;
    }
  }
  const updated = snapshot.session?.time?.updated ?? snapshot.session?.time?.created ?? now;
  const title = snapshot.session?.title || sessionID;
  const open = todos.filter((t) => t?.status !== "completed");
  const indent = (s: string) => s.slice(0, USER_MAX).replace(/\n/g, "\n  ");
  return [
    `# Handoff — ${title}`,
    `Session ${sessionID}, updated ${new Date(updated).toISOString()}`,
    "",
    "## Last user messages",
    ...(users.length ? users.map((u) => `- ${indent(u)}`) : ["(none)"]),
    "",
    "## Last assistant message",
    lastAssistant.slice(0, ASSISTANT_MAX) || "(none)",
    "",
    "## Open todos",
    ...(open.length ? open.map((t) => `- [${t.status ?? "pending"}] ${t.content ?? ""}`) : ["(none)"]),
    "",
    "## Files edited (approximate)",
    ...(files.length ? files.map((f) => `- ${f}`) : ["(none)"]),
    "",
  ].join("\n");
}

export function createHandoff(opts: { deps?: IdleDeps } = {}): Feature {
  return (ctx) => {
    const idle = getIdle(ctx, opts.deps ?? realDeps());
    const deps = idle.deps;
    const worktree = (ctx.input?.worktree as string | undefined) || ctx.directory;
    const noteDir = join(worktree, ".opencode", "handoff");
    const notePath = (id: string) => join(noteDir, `${id}.md`);

    const edited = new Map<string, Set<string>>();
    const unattributed = new Set<string>();
    const todos = new Map<string, any[]>();
    const snapshots = new Map<string, Snapshot>();
    const hashes = new Map<string, string>();
    const notes = new Map<string, string>();
    // Computed once per session and pushed on every transform call (the title-generation request fires first
    // with the same sessionID), so the prompt prefix does not change between requests.
    const notices = new Map<string, Promise<string[]>>();
    let active: string | undefined;
    let excludeDone = false;

    const filesFor = (id: string) => {
      let s = edited.get(id);
      if (!s) edited.set(id, (s = new Set()));
      if (unattributed.size) {
        for (const f of unattributed) s.add(f);
        unattributed.clear();
      }
      return s;
    };

    function ensureExclude(): void {
      if (excludeDone) return;
      excludeDone = true;
      try {
        const gitDir = join(worktree, ".git");
        if (!existsSync(gitDir) || !statSync(gitDir).isDirectory()) return;
        const file = join(gitDir, "info", "exclude");
        const current = existsSync(file) ? readFileSync(file, "utf8") : "";
        if (current.split("\n").some((l) => l.trim() === EXCLUDE_LINE)) return;
        mkdirSync(join(gitDir, "info"), { recursive: true });
        appendFileSync(file, (current && !current.endsWith("\n") ? "\n" : "") + EXCLUDE_LINE + "\n");
      } catch (err) {
        log(ctx.client, "warn", `handoff: could not update git exclude: ${String(err)}`);
      }
    }

    function write(id: string): void {
      const snap = snapshots.get(id);
      if (!snap) return;
      const note = buildNote({
        sessionID: id,
        snapshot: snap,
        todos: todos.get(id) ?? [],
        files: [...filesFor(id)],
        userMessages: ctx.options.handoff.userMessages,
        now: deps.now(),
      });
      notes.set(id, note);
      const hash = createHash("sha1").update(note).digest("hex");
      if (hashes.get(id) === hash) return;
      mkdirSync(noteDir, { recursive: true });
      writeFileSync(notePath(id), note);
      hashes.set(id, hash);
      ensureExclude();
    }

    function writeAll(): void {
      for (const id of snapshots.keys()) {
        try {
          write(id);
        } catch (err) {
          log(ctx.client, "error", `handoff final write failed: ${String(err)}`);
        }
      }
    }

    idle.addListener(({ sessionID, session, messages }: IdlePayload) => {
      snapshots.set(sessionID, { session, messages });
      write(sessionID);
    });

    function newestFreshNote(): string | undefined {
      if (!existsSync(noteDir)) return undefined;
      const cutoff = deps.now() - ctx.options.handoff.maxAgeDays * DAY_MS;
      let best: { path: string; mtime: number } | undefined;
      for (const name of readdirSync(noteDir)) {
        if (!name.endsWith(".md")) continue;
        const path = join(noteDir, name);
        const mtime = statSync(path).mtimeMs;
        if (mtime < cutoff) continue;
        if (!best || mtime > best.mtime) best = { path, mtime };
      }
      return best?.path;
    }

    return {
      event: async ({ event }) => {
        idle.handleEvent(event);
        const p = event?.properties ?? {};
        switch (event?.type) {
          case "session.idle":
          case "session.status":
          case "message.updated":
          case "message.part.updated":
            if (typeof p.sessionID === "string" && p.sessionID) active = p.sessionID;
            break;
          case "todo.updated":
            if (typeof p.sessionID === "string" && Array.isArray(p.todos)) todos.set(p.sessionID, p.todos);
            break;
          case "file.edited":
            if (typeof p.file === "string") (active ? filesFor(active) : unattributed).add(p.file);
            break;
          case "server.instance.disposed":
            await idle.flush();
            writeAll();
            break;
        }
      },
      dispose: async () => {
        await idle.flush(); // `opencode run` disposes right after the last turn, before the debounce fires
        writeAll();
      },
      "experimental.chat.system.transform": async (input, output) => {
        const id = input?.sessionID;
        if (!id) return;
        let p = notices.get(id);
        if (!p) {
          notices.set(
            id,
            (async () => {
              if (hashes.has(id) || (await idle.parents.isSubagent(id))) return [];
              const path = newestFreshNote();
              if (!path) return [];
              return [
                `A handoff note from a previous session in this project exists at ${path}. It lists recent messages, open todos and edited files.`,
              ];
            })(),
          );
          p = notices.get(id)!;
        }
        output.system.push(...(await p));
      },
      "experimental.session.compacting": async (input, output) => {
        const note = notes.get(input?.sessionID);
        if (note) output.context.push(note);
      },
    };
  };
}

export const handoff: Feature = createHandoff();
