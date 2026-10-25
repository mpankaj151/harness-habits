import { log } from "../log.ts";
import type { FeatureContext } from "../compose.ts";

export interface IdleDeps {
  now: () => number;
  setTimer: (fn: () => unknown, ms: number) => unknown;
  clearTimer: (handle: unknown) => void;
}

export function realDeps(): IdleDeps {
  return {
    now: () => Date.now(),
    setTimer: (fn, ms) => {
      const h: any = setTimeout(() => void fn(), ms);
      h?.unref?.();
      return h;
    },
    clearTimer: (h) => clearTimeout(h as any),
  };
}

export interface IdlePayload {
  sessionID: string;
  session: any;
  messages: any[];
  /** true when run from flush() at shutdown: listeners that do slow or remote work should skip. */
  final?: boolean;
}
export type IdleListener = (payload: IdlePayload) => void | Promise<void>;

/** Caches `session.get` answers so each session is looked up once. Shared with other features (size-lint). */
export interface ParentCache {
  isSubagent(sessionID: string): Promise<boolean>;
  get(sessionID: string): Promise<any>;
}

export function createParentCache(client: any): ParentCache {
  const sessions = new Map<string, Promise<any>>();
  const get = (sessionID: string): Promise<any> => {
    let p = sessions.get(sessionID);
    if (!p) {
      p = Promise.resolve(client.session.get({ path: { id: sessionID } })).then((r: any) => r?.data ?? r);
      p.catch(() => sessions.delete(sessionID)); // do not cache failures
      sessions.set(sessionID, p);
    }
    return p;
  };
  return {
    get,
    isSubagent: async (id) => Boolean((await get(id))?.parentID),
  };
}

export interface IdlePipeline {
  parents: ParentCache;
  deps: IdleDeps;
  /** Listeners run in registration order (composition order). */
  addListener(fn: IdleListener): void;
  /** Safe to call from several features with the same event: each event object is processed once. */
  handleEvent(event: { type: string; properties?: any } | undefined): void;
  onIdle(sessionID: string): void;
  /** Run every debounced idle that is still pending now (shutdown path). */
  flush(): Promise<void>;
}

const pipelines = new WeakMap<object, IdlePipeline>();

export function getIdle(ctx: FeatureContext, deps: IdleDeps = realDeps()): IdlePipeline {
  const existing = pipelines.get(ctx);
  if (existing) return existing;
  const parents = createParentCache(ctx.client);
  const listeners: IdleListener[] = [];
  const timers = new Map<string, unknown>();
  const seen = new WeakSet<object>();

  async function run(sessionID: string, final = false): Promise<void> {
    timers.delete(sessionID);
    try {
      const session = await parents.get(sessionID);
      if (session?.parentID) return; // subagent
      const res = await ctx.client.session.messages({ path: { id: sessionID }, query: { limit: 20 } });
      const raw = res?.data ?? res;
      const messages = Array.isArray(raw) ? raw : [];
      for (const l of listeners) {
        try {
          await l({ sessionID, session, messages, final });
        } catch (err) {
          log(ctx.client, "error", `idle listener failed: ${String(err)}`);
        }
      }
    } catch (err) {
      log(ctx.client, "error", `idle pipeline failed: ${String(err)}`);
    }
  }

  const pipeline: IdlePipeline = {
    parents,
    deps,
    addListener: (fn) => void listeners.push(fn),
    onIdle(sessionID) {
      const prev = timers.get(sessionID);
      if (prev !== undefined) deps.clearTimer(prev);
      timers.set(sessionID, deps.setTimer(() => run(sessionID), ctx.options.debounceMs));
    },
    async flush() {
      const pending = [...timers.entries()];
      for (const [id, handle] of pending) {
        deps.clearTimer(handle);
        timers.delete(id);
      }
      for (const [id] of pending) await run(id, true);
    },
    handleEvent(event) {
      if (!event || event.type !== "session.idle") return;
      if (seen.has(event)) return;
      seen.add(event);
      const id = event.properties?.sessionID;
      if (typeof id === "string" && id) pipeline.onIdle(id);
    },
  };
  pipelines.set(ctx, pipeline);
  return pipeline;
}
