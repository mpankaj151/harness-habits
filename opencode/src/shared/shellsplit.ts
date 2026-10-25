// Tokenizer mirroring Python shlex(posix=True, punctuation_chars=True, whitespace_split=True).
const PUNCT = "();<>|&";

export function split(command: string): string[] | null {
  const tokens: string[] = [];
  let cur = "";
  let has = false; // a token is in progress (an empty quoted string still counts)
  let i = 0;
  const n = command.length;
  const flush = () => {
    if (has) tokens.push(cur);
    cur = "";
    has = false;
  };
  while (i < n) {
    const ch = command[i];
    if (ch === " " || ch === "\t" || ch === "\n" || ch === "\r") {
      flush();
      i++;
    } else if (ch === "#") {
      flush();
      while (i < n && command[i] !== "\n") i++;
    } else if (PUNCT.includes(ch)) {
      flush();
      let run = "";
      while (i < n && PUNCT.includes(command[i])) run += command[i++];
      tokens.push(run);
    } else if (ch === "'") {
      const end = command.indexOf("'", i + 1);
      if (end === -1) return null;
      cur += command.slice(i + 1, end);
      has = true;
      i = end + 1;
    } else if (ch === '"') {
      i++;
      let closed = false;
      while (i < n) {
        const c = command[i];
        if (c === '"') {
          closed = true;
          i++;
          break;
        }
        if (c === "\\") {
          if (i + 1 >= n) return null;
          const nx = command[i + 1];
          if (nx === '"' || nx === "\\") {
            cur += nx;
          } else {
            cur += "\\" + nx;
          }
          i += 2;
        } else {
          cur += c;
          i++;
        }
      }
      if (!closed) return null;
      has = true;
    } else if (ch === "\\") {
      if (i + 1 >= n) return null;
      cur += command[i + 1];
      has = true;
      i += 2;
    } else {
      cur += ch;
      has = true;
      i++;
    }
  }
  flush();
  return tokens;
}

export function isOperator(token: string, operators: Set<string>): boolean {
  if (operators.has(token)) return true;
  return token.length > 0 && [...token].every((c) => PUNCT.includes(c));
}

export function segments(tokens: string[], operators: Set<string>): string[][] {
  const out: string[][] = [];
  let cur: string[] = [];
  for (const tok of tokens) {
    if (isOperator(tok, operators)) {
      if (cur.length) out.push(cur);
      cur = [];
    } else {
      cur.push(tok);
    }
  }
  if (cur.length) out.push(cur);
  return out;
}

export function isComposed(tokens: string[], command: string, operators: Set<string>): boolean {
  if (tokens.some((t) => isOperator(t, operators))) return true;
  return command.includes("$(") || command.includes("`") || command.includes("<<") || command.includes("\n");
}
