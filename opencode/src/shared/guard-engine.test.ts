import { test } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { join } from "node:path";
import { evaluate, realFs } from "./guard-engine.ts";
import type { FileSystem } from "./guard-engine.ts";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const rules = JSON.parse(readFileSync(join(root, "shared/rules/output-guard.json"), "utf8"));
const dir = join(root, "tests/fixtures/output-guard");

function fakeFs(files: Record<string, number>): FileSystem {
  return {
    lineCount(path: string) {
      const n = files[path];
      return n === undefined || n < 0 ? null : n;
    },
  };
}

for (const file of readdirSync(dir).filter((f) => f.endsWith(".json")).sort()) {
  const cases = JSON.parse(readFileSync(join(dir, file), "utf8"));
  for (const c of cases) {
    test(`${file.replace(".json", "")}:${c.name}`, () => {
      const d = evaluate(c.command, c.cwd, fakeFs(c.files), rules);
      assert.equal(d.action, c.expect.action);
      if ("command" in c.expect) assert.equal(d.command, c.expect.command);
      if ("message_contains" in c.expect) assert.ok((d.message ?? "").includes(c.expect.message_contains), d.message);
    });
  }
}

test("capped count renders more than", () => {
  const d = evaluate("cat big.txt", "/work", fakeFs({ "big.txt": 501 }), rules);
  assert.ok(d.message!.includes("more than 500 lines"));
  const e = evaluate("cat big.txt", "/work", fakeFs({ "big.txt": 800 }), rules);
  assert.ok(e.message!.includes("800 lines"));
});

test("prefixes are stripped", () => {
  assert.equal(evaluate("sudo cat big.txt", "/work", fakeFs({ "big.txt": 800 }), rules).action, "deny");
  assert.equal(evaluate("time nice grep -r x .", "/work", fakeFs({}), rules).action, "rewrite");
});

test("engine errors allow", () => {
  const boom: FileSystem = { lineCount() { throw new Error("x"); } };
  assert.equal(evaluate("cat a.txt", "/work", boom, rules).action, "allow");
});

test("realFs: a FIFO or directory is not opened and counts as unreadable (no hang)", () => {
  const d = mkdtempSync(join(tmpdir(), "hh-fs-"));
  let special = join(d, "pipe");
  try {
    execFileSync("mkfifo", [special]);
  } catch {
    special = join(d, "adir");
    mkdirSync(special);
  }
  assert.equal(realFs(d).lineCount(special), null);
});

test("realFs: counts lines, caps at max+1, and stops reading after 2 MiB", () => {
  const d = mkdtempSync(join(tmpdir(), "hh-fs-"));
  writeFileSync(join(d, "small.txt"), "a\nb\nc");
  writeFileSync(join(d, "wide.txt"), "x".repeat(3 * 1024 * 1024)); // one huge line, no newline
  assert.equal(realFs(d).lineCount("small.txt"), 3);
  assert.equal(realFs(d).lineCount("wide.txt"), 501);
});
