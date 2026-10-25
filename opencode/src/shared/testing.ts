// Test helpers: fake timers/clock and a fake OpenCode client. Not imported by production code.
import type { IdleDeps } from "./idle.ts";

export function fakeDeps(start = 1_000_000) {
  let t = start;
  let seq = 0;
  const timers = new Map<number, { fn: () => unknown; ms: number }>();
  const deps: IdleDeps = {
    now: () => t,
    setTimer: (fn, ms) => {
      const id = ++seq;
      timers.set(id, { fn, ms });
      return id;
    },
    clearTimer: (h) => void timers.delete(h as number),
  };
  return {
    deps,
    pending: () => timers.size,
    advance(ms: number) {
      t += ms;
    },
    /** Fire pending timers whose delay is at most maxMs (default: debounce-sized) and wait for the work they start. */
    async fire(maxMs = 10_000) {
      const due = [...timers.entries()].filter(([, x]) => x.ms <= maxMs);
      for (const [id] of due) timers.delete(id);
      await Promise.all(due.map(([, x]) => x.fn()));
    },
  };
}

export interface FakeClientState {
  sessions: Record<string, any>;
  messages: Record<string, any[]>;
  gets: string[];
  summarized: any[];
  toasts: any[];
  logs: any[];
}

export function fakeClient(init: Partial<FakeClientState> = {}, onSummarize?: (args: any, state: FakeClientState) => void) {
  const state: FakeClientState = { sessions: {}, messages: {}, gets: [], summarized: [], toasts: [], logs: [], ...init };
  const client = {
    session: {
      get: async ({ path }: any) => {
        state.gets.push(path.id);
        return { data: state.sessions[path.id] };
      },
      messages: async ({ path }: any) => ({ data: state.messages[path.id] ?? [] }),
      summarize: async (args: any) => {
        state.summarized.push(args);
        onSummarize?.(args, state);
        return { data: true };
      },
    },
    tui: { showToast: async (a: any) => void state.toasts.push(a) },
    app: { log: async (a: any) => void state.logs.push(a) },
  };
  return { client, state };
}

export function userMsg(text: string, created = 1) {
  return { info: { id: "u" + created, role: "user", time: { created } }, parts: [{ type: "text", text }] };
}
export function asstMsg(text: string, created: number, extra: Record<string, any> = {}) {
  return {
    info: {
      id: "a" + created,
      role: "assistant",
      providerID: "anthropic",
      modelID: "claude",
      time: { created },
      tokens: { input: 0, output: 0, reasoning: 0, cache: { read: 0, write: 0 } },
      ...extra,
    },
    parts: [{ type: "text", text }],
  };
}
