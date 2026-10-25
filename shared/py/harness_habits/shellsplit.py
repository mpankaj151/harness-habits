"""Minimal shell tokenising for the output guard."""
import json
import shlex

from .paths import rules_path

_PUNCT = set("();<>|&")
_OPERATORS = None


def _operators() -> set:
    global _OPERATORS
    if _OPERATORS is None:
        _OPERATORS = set(json.loads(rules_path().read_text()).get("operators", []))
    return _OPERATORS


def split(command: str):
    """Tokenise; None when quotes are unbalanced."""
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    try:
        return list(lex)
    except ValueError:
        return None


def is_operator(token: str, operators=None) -> bool:
    ops = _operators() if operators is None else operators
    return token in ops or (bool(token) and all(ch in _PUNCT for ch in token))


def segments(tokens, operators=None) -> list:
    out, cur = [], []
    for tok in tokens:
        if is_operator(tok, operators):
            if cur:
                out.append(cur)
            cur = []
        else:
            cur.append(tok)
    if cur:
        out.append(cur)
    return out


def is_composed(tokens, command: str = "", operators=None) -> bool:
    if any(is_operator(t, operators) for t in tokens):
        return True
    return "$(" in command or "`" in command or "<<" in command
