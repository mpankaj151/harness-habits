import { test } from "node:test";
import assert from "node:assert/strict";
import { split, isComposed, segments } from "./shellsplit.ts";

// Expected values were produced by Python shlex(posix, punctuation_chars, whitespace_split).
const cases: Array<[string, string[] | null]> = [
  ["a|b", ["a", "|", "b"]],
  ["2>&1", ["2", ">&", "1"]],
  ["foo>bar;x", ["foo", ">", "bar", ";", "x"]],
  ['echo "a|b" \'c;d\'', ["echo", "a|b", "c;d"]],
  ["echo $(cat x)", ["echo", "$", "(", "cat", "x", ")"]],
  ["a\\ b", ["a b"]],
  ["a\\|b", ["a|b"]],
  ['"a"b', ["ab"]],
  ['echo ""', ["echo", ""]],
  ["echo '' x", ["echo", "", "x"]],
  ['cat "a', null],
  ["echo 'a", null],
  ["a#b", ["a"]],
  ["echo a\\", null],
  ["a  \t b", ["a", "b"]],
  ["x>>y", ["x", ">>", "y"]],
  ["a&&b||c", ["a", "&&", "b", "||", "c"]],
  ['"a\\"b"', ['a"b']],
  ["'a\\b'", ["a\\b"]],
  ['"a\\nb"', ["a\\nb"]],
  ["a&>b", ["a", "&>", "b"]],
  ['a"b c"d', ["ab cd"]],
  ["echo \\\"", ["echo", '"']],
];

for (const [input, expected] of cases) {
  test(`split ${JSON.stringify(input)}`, () => {
    assert.deepEqual(split(input), expected);
  });
}

test("segments and composed", () => {
  const ops = new Set(["|", "&&"]);
  const t = split("grep x . | wc -l")!;
  assert.deepEqual(segments(t, ops), [["grep", "x", "."], ["wc", "-l"]]);
  assert.equal(isComposed(t, "grep x . | wc -l", ops), true);
  assert.equal(isComposed(["ls"], "ls\nls", ops), true);
  assert.equal(isComposed(["ls"], "ls", ops), false);
});
