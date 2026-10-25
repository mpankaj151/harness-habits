import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { loadOptions } from "./options.ts";

function env(json?: object, extra: Record<string, string> = {}) {
  const x = mkdtempSync(join(tmpdir(), "hh-"));
  if (json) {
    mkdirSync(join(x, "harness-habits"));
    writeFileSync(join(x, "harness-habits", "opencode.json"), JSON.stringify(json));
  }
  return { XDG_CONFIG_HOME: x, ...extra };
}

test("defaults", () => {
  const o = loadOptions(undefined, env());
  assert.equal(o.features["output-guard"], true);
  assert.equal(o.features["idle-compaction"], false);
  assert.equal(o.features["tool-budget"], false);
  assert.equal(o.compaction.pct, 0.6);
  assert.deepEqual(o.compaction.disableForProviders, ["ollama"]);
  assert.equal(o.debounceMs, 1500);
});

test("file < npm options < env", () => {
  const e = env({ features: { "size-lint": false, handoff: false }, compaction: { pct: 0.7 } }, { HH_FEATURE_HANDOFF: "on" });
  const o = loadOptions({ features: { "size-lint": true, "cache-break": "off" } }, e);
  assert.equal(o.features["size-lint"], true);
  assert.equal(o.features["cache-break"], false);
  assert.equal(o.features.handoff, true);
  assert.equal(o.compaction.pct, 0.7);
  assert.equal(o.compaction.cooldownMs, 60000);
});

test("features.json is read; opencode.json, npm options and env override it", () => {
  const e = env({ features: { "cache-break": true } });
  writeFileSync(join(e.XDG_CONFIG_HOME, "harness-habits", "features.json"), JSON.stringify({ handoff: false, "cache-break": false, "size-lint": false }));
  const o = loadOptions({ features: { "size-lint": true } }, e);
  assert.equal(o.features.handoff, false);
  assert.equal(o.features["cache-break"], true); // opencode.json wins over features.json
  assert.equal(o.features["size-lint"], true); // npm options win
  const o2 = loadOptions(undefined, { ...e, HH_FEATURE_HANDOFF: "1" });
  assert.equal(o2.features.handoff, true); // env wins
});

test("features.json alone disables handoff", () => {
  const e = env({});
  writeFileSync(join(e.XDG_CONFIG_HOME, "harness-habits", "features.json"), JSON.stringify({ handoff: false }));
  assert.equal(loadOptions(undefined, e).features.handoff, false);
});

test("env off values and bad file", () => {
  const o = loadOptions(undefined, env(undefined, { HH_FEATURE_OUTPUT_GUARD: "false", HH_FEATURE_COST_LOGGER: "0" }));
  assert.equal(o.features["output-guard"], false);
  assert.equal(o.features["cost-logger"], false);
});

test("optional keys inside known sections survive file and npm merge", () => {
  const o = loadOptions({ handoff: { extra: 2 } }, env({ compaction: { absoluteTokens: 1 } }));
  assert.equal(o.compaction.absoluteTokens, 1);
  assert.equal(o.compaction.pct, 0.6);
  assert.equal((o.handoff as any).extra, 2);
});
