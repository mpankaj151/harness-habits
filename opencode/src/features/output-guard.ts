import rules from "../../../shared/rules/output-guard.json" with { type: "json" };
import { blockError } from "../compose.ts";
import type { Feature } from "../compose.ts";
import { log } from "../log.ts";
import { evaluate, realFs } from "../shared/guard-engine.ts";
import type { FileSystem } from "../shared/guard-engine.ts";

export function createOutputGuard(fsFactory: (cwd: string) => FileSystem = (cwd) => realFs(cwd, (rules as any).max_lines)): Feature {
  return (ctx) => ({
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "bash") return;
      const command = output?.args?.command;
      if (typeof command !== "string") return;
      const decision = evaluate(command, ctx.directory, fsFactory(ctx.directory), rules);
      if (decision.action === "deny") throw blockError(decision.message ?? "harness-habits: blocked");
      if (decision.action === "rewrite" && decision.command) {
        output.args.command = decision.command; // mutate in place; reassigning output.args is ignored
        log(ctx.client, "info", decision.message ?? "");
      } else if (decision.action === "advise") {
        log(ctx.client, "info", decision.message ?? "");
      }
    },
  });
}

export const outputGuard: Feature = createOutputGuard();
