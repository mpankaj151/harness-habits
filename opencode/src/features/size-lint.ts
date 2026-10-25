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
    // The transform runs on every request (the title-generation request included), so the lines are
    // computed once per session and the same lines are pushed each time: the prompt prefix stays stable.
    const lines = new Map<string, Promise<string[]>>();
    async function compute(id: string): Promise<string[]> {
      if (await parents.isSubagent(id)) return [];
      const found: string[] = [];
      const targets: Array<[string, string]> = [
        ["AGENTS.md", join(worktree, "AGENTS.md")],
        ["CLAUDE.md", join(worktree, "CLAUDE.md")],
        ["~/.config/opencode/AGENTS.md", join(globalDir, "AGENTS.md")],
      ];
      for (const [label, path] of targets) {
        const n = lineCount(path);
        if (n !== undefined && n > LIMIT) {
          found.push(`${label} has ${n} lines (guideline ${LIMIT}). Long instruction files cost tokens on every turn.`);
        }
      }
      return found;
    }
    return {
      "experimental.chat.system.transform": async (input, output) => {
        const id = input?.sessionID;
        if (!id) return;
        let p = lines.get(id);
        if (!p) lines.set(id, (p = compute(id)));
        output.system.push(...(await p));
      },
    };
  };
}

export const sizeLint: Feature = createSizeLint();
