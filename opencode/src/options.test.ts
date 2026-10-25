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

test("env off values and bad file", () => {
  const o = loadOptions(undefined, env(undefined, { HH_FEATURE_OUTPUT_GUARD: "false", HH_FEATURE_COST_LOGGER: "0" }));
  assert.equal(o.features["output-guard"], false);
  assert.equal(o.features["cost-logger"], false);
});
