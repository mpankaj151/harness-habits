import { closeSync, fstatSync, openSync, readSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { isAbsolute, join } from "node:path";
import { isComposed, segments, split } from "./shellsplit.ts";

export interface Decision {
  action: "allow" | "deny" | "rewrite" | "advise";
  command?: string;
  message?: string;
}

export interface FileSystem {
  lineCount(path: string): number | null;
}

const MAX_READ_BYTES = 2 * 1024 * 1024; // a file longer than this counts as over the limit without reading on

const PREFIXES = ["sudo", "command", "nice", "time"];

function basename(p: string): string {
  const trimmed = p.replace(/\/+$/, "");
  return trimmed.slice(trimmed.lastIndexOf("/") + 1);
}

/** Counts lines of a regular text file, stopping at maxLines + 1. Binary or unreadable -> null. */
export function realFs(cwd: string, maxLines = 500): FileSystem {
  return {
    lineCount(path: string): number | null {
      let fd: number | undefined;
      try {
        const expanded = path === "~" || path.startsWith("~/") ? join(homedir(), path.slice(1)) : path;
        const full = isAbsolute(expanded) ? expanded : join(cwd || process.cwd(), expanded);
        if (!statSync(full).isFile()) return null; // before open: opening a FIFO would block
        fd = openSync(full, "r");
        if (!fstatSync(fd).isFile()) return null;
        const buf = Buffer.alloc(64 * 1024);
        const cap = maxLines + 1;
        let lines = 0;
        let total = 0;
        let lastByte = 10;
        for (;;) {
          const got = readSync(fd, buf, 0, buf.length, null);
          if (got === 0) break;
          if (total < 8192 && buf.subarray(0, Math.min(got, 8192 - total)).includes(0)) return null;
          total += got;
          if (total >= MAX_READ_BYTES) return cap;
          for (let i = 0; i < got; i++) {
            if (buf[i] === 10) {
              lines++;
              if (lines >= cap) return cap;
            }
          }
          lastByte = buf[got - 1];
        }
        if (total > 0 && lastByte !== 10) lines++; // final line without newline
        return Math.min(lines, cap);
      } catch {
        return null;
      } finally {
        if (fd !== undefined) {
          try {
            closeSync(fd);
          } catch {
            // ignore
          }
        }
      }
    },
  };
}

function fmt(rules: any, key: string, vars: Record<string, string>): string {
  const all: Record<string, string> = { max: String(rules.max_lines), head: String(rules.head_n), ...vars };
  return String(rules.messages[key]).replace(/\{(\w+)\}/g, (m, k) => (k in all ? all[k] : m));
}

function lines(n: number, rules: any): string {
  return n === rules.max_lines + 1 ? `more than ${rules.max_lines}` : String(n);
}

function stripPrefixes(seg: string[]): string[] {
  let i = 0;
  while (i < seg.length - 1 && PREFIXES.includes(basename(seg[i]))) i++;
  return seg.slice(i);
}

function hasSkip(cmd: string, args: string[], rules: any): boolean {
  const skip: string[] = rules.skip_flags[cmd] ?? [];
  return args.some((a) => skip.includes(a));
}

export function evaluate(command: string, cwd: string, fs: FileSystem, rules: any): Decision {
  try {
    return evaluateInner(command, cwd, fs, rules);
  } catch {
    return { action: "allow" }; // never block on engine errors
  }
}

function evaluateInner(command: string, _cwd: string, fs: FileSystem, rules: any): Decision {
  const ops = new Set<string>(rules.operators);
  const tokens = split(command);
  if (!tokens || tokens.length === 0) return { action: "allow" };
  const segs = segments(tokens, ops);
  if (segs.length === 0) return { action: "allow" };

  if (isComposed(tokens, command, ops)) {
    const first = stripPrefixes(segs[0]);
    const cmd = basename(first[0]);
    if (
      rules.unbounded_commands.includes(cmd) &&
      !hasSkip(cmd, first.slice(1), rules) &&
      !tokens.some((t) => rules.bounding_commands.includes(basename(t)))
    ) {
      return { action: "advise", message: fmt(rules, "advise_unbounded", { cmd }) };
    }
    return { action: "allow" };
  }

  const seg = stripPrefixes(segs[0]);
  const cmd = basename(seg[0]);
  const args = seg.slice(1);

  if (rules.full_read_commands.includes(cmd)) {
    const paths = args.filter((a) => !a.startsWith("-"));
    if (paths.some((p) => /[*?[]/.test(p))) return { action: "allow" };
    for (const p of paths) {
      const n = fs.lineCount(p);
      if (n !== null && n > rules.max_lines) {
        return { action: "deny", message: fmt(rules, "deny_full_read", { path: p, lines: lines(n, rules) }) };
      }
    }
    return { action: "allow" };
  }

  if (cmd === "tail") {
    const flag = args.find((a) => rules.follow_flags.includes(a));
    if (flag) {
      const path = [...args].reverse().find((a) => !a.startsWith("-")) ?? "<file>";
      return { action: "deny", message: fmt(rules, "deny_follow", { flag, path }) };
    }
    return { action: "allow" };
  }

  const rewrite =
    (rules.unbounded_commands.includes(cmd) && !hasSkip(cmd, args, rules)) ||
    (cmd === "ls" && args.some((a) => rules.ls_recursive_flags.includes(a)));
  if (rewrite) {
    return {
      action: "rewrite",
      command: `${command} | head -n ${rules.head_n}`,
      message: fmt(rules, "rewrite_note", {}),
    };
  }
  return { action: "allow" };
}
