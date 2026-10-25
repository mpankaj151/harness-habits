import type { Feature } from "../compose.ts";
import { log, toast } from "../log.ts";
import { getIdle, realDeps } from "../shared/idle.ts";
import type { IdleDeps, IdlePayload } from "../shared/idle.ts";

const DEFAULT_CONTEXT = 200000;
const INFLIGHT_MS = 120000;

/** options.compaction.contextLimits["provider/model"] -> cfg.provider[p].models[m].limit.context -> 200000 */
export function contextLimit(
  limits: Record<string, number> | undefined,
  cfg: any,
  providerID: string,
  modelID: string,
): number {
  const fromOptions = limits?.[`${providerID}/${modelID}`];
  if (typeof fromOptions === "number" && fromOptions > 0) return fromOptions;
  const fromCfg = cfg?.provider?.[providerID]?.models?.[modelID]?.limit?.context;
  if (typeof fromCfg === "number" && fromCfg > 0) return fromCfg;
  return DEFAULT_CONTEXT;
}

export function messageTokens(info: any): number {
  const t = info?.tokens ?? {};
  return t.total ?? (t.input ?? 0) + (t.output ?? 0) + (t.cache?.read ?? 0) + (t.cache?.write ?? 0);
}

function lastAssistant(messages: any[]): any | undefined {
  const sorted = [...messages].sort((a, b) => (a?.info?.time?.created ?? 0) - (b?.info?.time?.created ?? 0));
  for (let i = sorted.length - 1; i >= 0; i--) if (sorted[i]?.info?.role === "assistant") return sorted[i];
  return undefined;
}

export function createIdleCompaction(opts: { deps?: IdleDeps } = {}): Feature {
  return (ctx) => {
    const idle = getIdle(ctx, opts.deps ?? realDeps());
    const deps = idle.deps;
    const inflight = new Map<string, unknown>(); // sessionID -> expiry timer
    const lastCompacted = new Map<string, number>();
    let cfg: any;

    const release = (id: string) => {
      const t = inflight.get(id);
      if (t !== undefined) deps.clearTimer(t);
      inflight.delete(id);
    };

    async function onIdle({ sessionID, messages, final }: IdlePayload): Promise<void> {
      if (final) return; // shutdown flush: never start a summary while the instance is going away
      const m = lastAssistant(messages);
      if (!m || m.info.summary === true) return;
      if (inflight.has(sessionID)) return;
      const c = ctx.options.compaction;
      const last = lastCompacted.get(sessionID);
      if (last !== undefined && deps.now() - last < c.cooldownMs) return;
      const providerID: string = m.info.providerID;
      const modelID: string = m.info.modelID;
      const pid = String(providerID ?? "").toLowerCase();
      if (c.disableForProviders.some((p) => String(p).toLowerCase() === pid)) return;
      const tokens = messageTokens(m.info);
      const ctxLimit = contextLimit(c.contextLimits, cfg, providerID, modelID);
      const limit = c.absoluteTokens ?? c.pct * ctxLimit;
      if (tokens < limit) return;

      inflight.set(sessionID, deps.setTimer(() => release(sessionID), INFLIGHT_MS));
      try {
        await ctx.client.session.summarize({ path: { id: sessionID }, body: { providerID, modelID } });
        lastCompacted.set(sessionID, deps.now());
        toast(ctx.client, `harness-habits compacted the session at ${Math.round((tokens / ctxLimit) * 100)}% of context`, "info");
        log(ctx.client, "info", `compacted the session ${sessionID} at ${tokens} tokens (limit ${Math.round(limit)})`);
      } catch (err) {
        release(sessionID);
        log(ctx.client, "error", `idle compaction failed: ${String(err)}`);
      }
    }
    idle.addListener(onIdle);

    return {
      config: async (c: any) => {
        cfg = c;
      },
      event: async ({ event }) => {
        idle.handleEvent(event);
        if (event?.type === "session.compacted") {
          const id = event.properties?.sessionID;
          if (typeof id === "string") release(id);
        }
      },
    };
  };
}

export const idleCompaction: Feature = createIdleCompaction();
