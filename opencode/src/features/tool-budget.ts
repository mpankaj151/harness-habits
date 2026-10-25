import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Feature } from "../compose.ts";
import { log, toast } from "../log.ts";
import { dataDir } from "../options.ts";

const BUILTINS = new Set(
  "invalid question bash read glob grep edit write task webfetch todowrite websearch skill apply_patch".split(" "),
);
const LIMIT_RE = /array too long|maximum length 128|too many tools|tools.*(limit|maximum)/i;
const EXCERPT = 120;
const MAX_SERVERS = 200;

interface State {
  updated?: string;
  overBudget: boolean;
  lastError?: string;
  servers: string[];
  disabled: string[];
}

function stateFile(): string {
  return join(dataDir(), "mcp-tool-budget.json");
}

function readState(): State {
  try {
    const raw = JSON.parse(readFileSync(stateFile(), "utf8"));
    return {
      ...raw,
      overBudget: raw?.overBudget === true,
      servers: Array.isArray(raw?.servers) ? raw.servers : [],
      disabled: Array.isArray(raw?.disabled) ? raw.disabled : [],
    };
  } catch {
    return { overBudget: false, servers: [], disabled: [] };
  }
}

function writeState(state: State): void {
  mkdirSync(dataDir(), { recursive: true });
  writeFileSync(stateFile(), JSON.stringify({ ...state, updated: new Date().toISOString() }));
}

export const toolBudget: Feature = (ctx) => {
  const opts = ctx.options.toolBudget;
  const pending: Array<{ message: string; variant: "info" | "warning" }> = [];
  const learned = new Set<string>();
  let skip = false;
  let errorHandled = false;

  const flush = () => {
    while (pending.length) {
      const t = pending.shift()!;
      toast(ctx.client, t.message, t.variant);
    }
  };

  const safe = async (what: string, fn: () => void | Promise<void>) => {
    try {
      await fn();
    } catch (err) {
      log(ctx.client, "error", `tool-budget ${what} failed: ${String(err)}`);
    }
  };

  return {
    config: async (cfg: any) =>
      safe("config", () => {
        const mcp: Record<string, any> =
          cfg && typeof cfg.mcp === "object" && cfg.mcp !== null && !Array.isArray(cfg.mcp) ? cfg.mcp : {};
        const names = Object.keys(mcp);
        const plugins: unknown[] = Array.isArray(cfg?.plugin) ? cfg.plugin : [];
        const lazy =
          plugins.some((p) => typeof p === "string" && p.includes("lazy-mcp")) ||
          (names.length > 0 && names.every((n) => mcp[n]?.enabled === false));
        if (lazy) {
          skip = true;
          log(ctx.client, "info", "tool-budget: lazy MCP loading detected, server-count heuristic skipped");
          return;
        }
        const state = readState();
        if (state.overBudget) {
          const turnedOff: string[] = [];
          for (const name of opts.disableFirst) {
            if (name in mcp && mcp[name] && typeof mcp[name] === "object") {
              mcp[name].enabled = false;
              turnedOff.push(name);
            }
          }
          if (turnedOff.length) {
            state.disabled = turnedOff;
            writeState(state);
            pending.push({
              message: `A previous run hit the provider tool limit. MCP servers disabled for this run: ${turnedOff.join(", ")}.`,
              variant: "warning",
            });
          }
        }
        const enabled = names.filter((n) => mcp[n]?.enabled !== false);
        const model = typeof cfg?.model === "string" ? cfg.model : "";
        const provider = model.split("/")[0];
        if (provider && enabled.length > opts.maxServers && new RegExp(opts.providerPattern, "i").test(provider)) {
          pending.push({
            message: `${enabled.length} MCP servers enabled for ${provider}. OpenAI-compatible endpoints reject requests with more than 128 tool definitions. Fewer servers per project or lazy loading keeps requests under the cap.`,
            variant: "warning",
          });
        }
      }),

    event: async ({ event }) =>
      safe("event", () => {
        flush();
        if (event?.type !== "session.error" || errorHandled) return;
        const data = event.properties?.error?.data;
        const raw = data?.message ?? data?.responseBody ?? "";
        const text = typeof raw === "string" ? raw : "";
        if (!LIMIT_RE.test(text)) return;
        errorHandled = true;
        const excerpt = text.slice(0, EXCERPT);
        toast(
          ctx.client,
          `The provider rejected the request because too many tools were attached (${excerpt}). Disable MCP servers for this project or enable lazy loading.`,
          "error",
        );
        log(ctx.client, "warn", `tool-budget: provider tool limit hit: ${excerpt}`);
        const state = readState();
        state.overBudget = true;
        state.lastError = excerpt;
        state.servers = [...new Set([...state.servers, ...learned])].slice(0, MAX_SERVERS);
        writeState(state);
      }),

    "tool.execute.before": async (input) =>
      safe("tool.execute.before", () => {
        flush();
        const id = input?.tool;
        if (typeof id === "string" && id.includes("_") && !BUILTINS.has(id) && learned.size < MAX_SERVERS) learned.add(id);
      }),
  };
};
