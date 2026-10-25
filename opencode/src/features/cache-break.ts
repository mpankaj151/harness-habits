import { basename } from "node:path";
import type { Feature } from "../compose.ts";
import { toast } from "../log.ts";

const WATCHED = new Set(["opencode.json", "opencode.jsonc", "AGENTS.md", "CLAUDE.md"]);

export const cacheBreak: Feature = (ctx) => {
  const shown = new Set<string>();
  return {
    "tool.execute.after": async (input, output) => {
      if (input?.tool !== "edit" && input?.tool !== "write") return;
      const path = (output as any)?.args?.filePath ?? input?.args?.filePath;
      if (typeof path !== "string" || !path) return;
      const file = basename(path);
      if (!WATCHED.has(file)) return;
      const key = `${input.sessionID}\0${file}`;
      if (shown.has(key)) return;
      shown.add(key);
      toast(
        ctx.client,
        `${file} changed; it is part of the prompt prefix, so the next turn re-reads the full prefix (cache miss).`,
        "info",
      );
    },
  };
};
