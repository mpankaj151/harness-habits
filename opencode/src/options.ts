import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import type { FeatureKey } from "./types.ts";

export const FEATURE_DEFAULTS: Record<FeatureKey, boolean> = {
  "output-guard": true,
  "size-lint": true,
  "cache-break": true,
  handoff: true,
  "idle-compaction": false,
  "cost-logger": true,
  "tool-budget": false,
  "precompact-snapshot": true,
};

export interface Options {
  features: Record<FeatureKey, boolean>;
  compaction: { pct: number; absoluteTokens?: number; cooldownMs: number; disableForProviders: string[] };
  handoff: { maxAgeDays: number; userMessages: number };
  toolBudget: { budget: number; providerPattern: string; disableFirst: string[] };
  debounceMs: number;
}

export function defaultOptions(): Options {
  return {
    features: { ...FEATURE_DEFAULTS },
    compaction: { pct: 0.6, cooldownMs: 60000, disableForProviders: ["ollama"] },
    handoff: { maxAgeDays: 7, userMessages: 5 },
    toolBudget: { budget: 128, providerPattern: "openai|azure", disableFirst: [] },
    debounceMs: 1500,
  };
}

export function configDir(env: Record<string, string | undefined> = process.env): string {
  const base = env.XDG_CONFIG_HOME;
  return join(base ? base : join(homedir(), ".config"), "harness-habits");
}

function parseBool(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  return !["0", "false", "off"].includes(String(value).trim().toLowerCase());
}

function isObject(v: unknown): v is Record<string, any> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

// Inside known sections any key is accepted, so optional keys (compaction.absoluteTokens) survive.
function mergeSection(target: Record<string, any>, src: Record<string, any>): void {
  for (const [k, v] of Object.entries(src)) {
    if (v !== undefined) target[k] = v;
  }
}

function merge(target: Record<string, any>, src: unknown): void {
  if (!isObject(src)) return;
  for (const [k, v] of Object.entries(src)) {
    if (k === "features") {
      if (isObject(v)) {
        for (const [fk, fv] of Object.entries(v)) {
          if (fk in FEATURE_DEFAULTS) target.features[fk] = parseBool(fv);
        }
      }
    } else if (isObject(v) && isObject(target[k])) {
      mergeSection(target[k], v);
    } else if ((k in target || k === "debounceMs") && v !== undefined) {
      target[k] = v;
    }
  }
}

export function loadOptions(
  npmOptions?: Record<string, unknown>,
  env: Record<string, string | undefined> = process.env,
): Options {
  const opts = defaultOptions();
  try {
    merge(opts, JSON.parse(readFileSync(join(configDir(env), "opencode.json"), "utf8")));
  } catch {
    // missing or invalid file: defaults
  }
  merge(opts, npmOptions);
  for (const key of Object.keys(FEATURE_DEFAULTS) as FeatureKey[]) {
    const raw = env["HH_FEATURE_" + key.toUpperCase().replace(/-/g, "_")];
    if (raw !== undefined && raw !== "") opts.features[key] = parseBool(raw);
  }
  return opts;
}
