import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import type { Feature } from "../compose.ts";
import { log } from "../log.ts";
import { dataDir } from "../options.ts";

const MAX_SEEN = 5000;

export const costLogger: Feature = (ctx) => {
  const seen = new Set<string>();
  return {
    event: async ({ event }) => {
      if (event?.type !== "message.updated") return;
      const info = event.properties?.info;
      if (!info || info.role !== "assistant" || !info.time?.completed || typeof info.id !== "string") return;
      if (seen.has(info.id)) return;
      seen.add(info.id);
      if (seen.size > MAX_SEEN) seen.delete(seen.values().next().value as string); // FIFO
      try {
        const dir = dataDir();
        mkdirSync(dir, { recursive: true });
        const row = {
          ts: new Date().toISOString(),
          sessionID: event.properties?.sessionID ?? info.sessionID,
          messageID: info.id,
          providerID: info.providerID,
          modelID: info.modelID,
          cost: info.cost,
          tokens_last_step: info.tokens,
        };
        appendFileSync(join(dir, "opencode-usage.jsonl"), JSON.stringify(row) + "\n");
      } catch (err) {
        log(ctx.client, "warn", `cost-logger: could not write usage log: ${String(err)}`);
      }
    },
  };
};
