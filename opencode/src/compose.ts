import { log } from "./log.ts";
import type { FeatureKey, Hooks, PluginInput } from "./types.ts";
import type { Options } from "./options.ts";

export interface FeatureContext {
  client: any;
  directory: string;
  options: Options;
  input: PluginInput;
}

export type Feature = ((ctx: FeatureContext) => Partial<Hooks>) & { key?: FeatureKey };

const HOOK_NAMES = [
  "event",
  "tool.execute.before",
  "tool.execute.after",
  "experimental.chat.system.transform",
  "experimental.session.compacting",
  "dispose",
  "config",
] as const;

export function blockError(message: string): Error {
  const err = new Error(message);
  (err as any).harnessHabitsBlock = true;
  return err;
}

function isBlock(err: unknown): boolean {
  return typeof err === "object" && err !== null && (err as any).harnessHabitsBlock === true;
}

export function compose(features: Array<{ key: FeatureKey; feature: Feature }>, ctx: FeatureContext): Hooks {
  const active = features.filter((f) => ctx.options.features[f.key]);
  const built: Array<{ key: FeatureKey; hooks: Record<string, any> }> = [];
  for (const f of active) {
    try {
      built.push({ key: f.key, hooks: (f.feature(ctx) ?? {}) as Record<string, any> });
    } catch (err) {
      log(ctx.client, "error", `feature ${f.key} failed to initialise: ${String(err)}`);
    }
  }
  const out: Record<string, any> = {};
  for (const name of HOOK_NAMES) {
    const handlers = built.filter((b) => typeof b.hooks[name] === "function");
    if (handlers.length === 0) continue;
    out[name] = async (...args: any[]) => {
      for (const h of handlers) {
        try {
          await h.hooks[name](...args);
        } catch (err) {
          // A deliberate block (for example output-guard deny) must reach OpenCode.
          if (isBlock(err)) throw err;
          log(ctx.client, "error", `feature ${h.key} ${name} failed: ${String(err)}`);
        }
      }
    };
  }
  return out as Hooks;
}
