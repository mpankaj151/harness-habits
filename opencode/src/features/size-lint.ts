import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { Feature } from "../compose.ts";
import { createParentCache } from "../shared/idle.ts";

const LIMIT = 200;

function lineCount(path: string): number | undefined {
  try {
    const text = readFileSync(path, "utf8");
    if (!text) return 0;
    const n = text.split("\n").length;
    return text.endsWith("\n") ? n - 1 : n;
  } catch {
    return undefined;
  }
}

export function createSizeLint(opts: { globalDir?: string } = {}): Feature {
  return (ctx) => {
    const worktree = (ctx.input?.worktree as string | undefined) || ctx.directory;
    const globalDir = opts.globalDir ?? join(homedir(), ".config", "opencode");
    const parents = createParentCache(ctx.client);
    const done = new Set<string>();
    return {
      "experimental.chat.system.transform": async (input, output) => {
        const id = input?.sessionID;
        if (!id || done.has(id)) return;
        done.add(id);
        if (await parents.isSubagent(id)) return;
        const targets: Array<[string, string]> = [
          ["AGENTS.md", join(worktree, "AGENTS.md")],
          ["CLAUDE.md", join(worktree, "CLAUDE.md")],
          ["~/.config/opencode/AGENTS.md", join(globalDir, "AGENTS.md")],
        ];
        for (const [label, path] of targets) {
          const n = lineCount(path);
          if (n !== undefined && n > LIMIT) {
            output.system.push(`${label} has ${n} lines (guideline ${LIMIT}). Long instruction files cost tokens on every turn.`);
          }
        }
      },
    };
  };
}

export const sizeLint: Feature = createSizeLint();
