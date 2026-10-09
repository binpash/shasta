#!/usr/bin/env python3
"""Semantic round-trip test for shasta.shfmt_to_shasta_ast.

For each snippet:  source -> Shasta nodes -> .pretty() -> text
and then check that shfmt parses `text` into the same tree as the original
source (ignoring positions, comments and formatting).

Run as a script for a readable report:   python3 tests/test_shfmt_to_shasta.py
Or with pytest:                          pytest tests/test_shfmt_to_shasta.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shasta.ast_node import make_typed_semi_sequence  # noqa: E402
from shasta.shfmt_to_shasta_ast import parse_string  # noqa: E402

# Add cases as you implement each construct. Grouped in the suggested order.
CASES = {
    "simple": [
        "echo hi",
        "x=1 y=2 prog a b",
        "echo a\\ b",
    ],
    "step1_stmt": [
        "! ls",
        "ls &",
        "ls; ls; ls",
    ],
    "step2_binary": [
        "a && b",
        "a || b",
        "a | b | c",
        "a && b || c",
        "a | b && c",
        "! a | b",
        "a && ! b",
        "a | b &",
        "a && b | c",
    ],
    "step3_compound": [
        "if a; then b; fi",
        "if a; then b; elif c; then d; else e; fi",
        "if a; then b; elif c; then d; elif e; then f; fi",
        "if a; then b; else c; fi",
        "if a; then if b; then c; fi; fi",
        "while a && b; do c; d; done",
        "! until a; do b; done",
        "while a; do b; done",
        "until a; do b; done",
        "{ a; b; }",
        "( a; b )",
    ],
    # constructs whose printing needed the node subclasses in shasta/shfmt_to_shasta_ast.py
    "printer_shims": [
        "if a; then b & fi",
        "if a; then b & else c & fi",
        "if a; then b; elif c; then d & fi",
        "while a; do b & done",
        "until a; do b & c & done",
        "for ((i=0;i<3;i++)); do b & done",
        "for i in a; do b & done",
        "case w in a) b & ;; c) d ;; esac",
        "x=$(a; b)",
        "x=$(a & b)",
        "cat <(a; b)",
        "x=$( ((i%9)) || printf z )",
        "f() { x; } >&2",
        "f() ( a; b ) >&2",
        "echo $(cat <<EOF\nhi\nEOF\n)",
    ],
    "step4_for_case_func": [
        "for i in a b c; do echo x; done",
        "for i in; do x; done",
        "for i; do x; done",
        "case w in a) b;;& c) d;; esac",
        "echo foo |& cat",
        "a | b |& c",
        "select i in a b; do x; done",
        "case w in a) b;; c|d) e;; esac",
        "case w in a) b;& c) d;; esac",
        "case w in a) ;; *) b;; esac",
        "f() { echo x; }",
        "f() { a; b; c; }",
        "function f { a; b; }",
        "function f { echo x; }",
        "f() { if a; then b; fi; }",
        "f() ( x )",
        "for i in a b c; do echo $i; done",
        "case $x in a) b;; c|d) e;; esac",
        "f() { echo hi; }",
    ],
    "step5_quoting": [
        "echo 'a$x'",
        'echo "a\\"b"',
        'echo "hi $x"',
        "echo ${x:-y} ${x#p} ${#x}",
        "echo $(ls | wc -l)",
        'echo "n: $(ls)"',
    ],
    "step6_redirects": [
        "cat > f",
        "cat < f >> g",
        "cmd 2>&1",
        "cat <<EOF\nhi $x\nEOF",
        "cat <<'EOF'\nhi $x\nEOF",
        "> f",            # bare redirect, no command
        "> f &",          # empty command + background
    ],
}


def shfmt_tree(source: str):
    out = subprocess.run(
        ["shfmt", "-ln=bash", "-tojson"], input=source.encode(), capture_output=True, check=True
    ).stdout
    return normalise(json.loads(out))


def is_position(value) -> bool:
    return isinstance(value, dict) and "Offset" in value and "Line" in value


# Spelling only, never meaning: `function f {}` vs `function f() {}` ("Parens"),
# `$x` vs `${x}` ("Short"), `ls` vs $(ls) ("Backquotes"), `$[ ]` vs `$(( ))`
# ("Bracket"), `for ((;;)) { }` vs `do ... done` ("Braces").
IGNORED_KEYS = ("Comments", "Last", "CondLast", "ThenLast", "DoLast", "Parens", "Short", "Backquotes", "Bracket", "Braces")

# File descriptor a redirect uses when none is written: `>f` is `1>f`
DEFAULT_FD = {">": "1", ">>": "1", ">|": "1", ">&": "1", "<": "0", "<>": "0",
              "<<": "0", "<<-": "0", "<<<": "0", "<&": "0"}


def _delimiter(word) -> dict:
    """Heredoc marker without its quoting: <<\\EOT, <<'EOT' and <<"EOT" are one marker."""
    import re
    quoted = any(p["Type"] != "Lit" or "\\" in p.get("Value", "") for p in word["Parts"])
    text = ""
    for p in word["Parts"]:
        if p["Type"] == "SglQuoted":
            text += p.get("Value", "")
        elif p["Type"] == "DblQuoted":
            text += "".join(re.sub(r"\\(.)", r"\1", q.get("Value", "")) for q in p.get("Parts", []))
        else:
            text += re.sub(r"\\(.)", r"\1", p.get("Value", ""))
    return {"Delimiter": text, "Quoted": quoted}


def _canonical_redirect(r: dict) -> dict:
    r = dict(r)
    op = r.get("Op")
    word = normalise(r["Word"]) if r.get("Word") else None
    n = normalise(r["N"]) if r.get("N") else None
    if op in ("<<", "<<-") and r.get("Word"):
        r["Word"] = _delimiter(r["Word"])
    if op in ("<&", ">&") and word == {"Parts": [{"Type": "Lit", "Value": "-"}]}:
        # closing a descriptor: `<&-` and `>&-` are the same; Shasta always writes the fd
        r["Op"] = ">&"
        r["N"] = n or {"Value": DEFAULT_FD[op]}
    elif n is not None and n == {"Value": DEFAULT_FD.get(op)}:
        del r["N"]
    return r


def _merge_literals(parts):
    """Adjacent plain-text pieces are one string (a `\\<newline>` splits them)."""
    out = []
    for p in parts:
        if out and p.get("Type") == "Lit" and out[-1].get("Type") == "Lit":
            out[-1] = {"Type": "Lit", "Value": out[-1].get("Value", "") + p.get("Value", "")}
        else:
            out.append(p)
    return out


def _with_stderr_merged(stmt: dict) -> dict:
    """Add `2>&1` to the last command of a pipeline statement."""
    cmd = stmt.get("Cmd", {})
    if cmd.get("Type") == "BinaryCmd" and cmd.get("Op") in ("|", "|&"):
        return {**stmt, "Cmd": {**cmd, "Y": _with_stderr_merged(cmd["Y"])}}
    merge = {"Op": ">&", "N": {"Value": "2"}, "Word": {"Parts": [{"Type": "Lit", "Value": "1"}]}}
    return {**stmt, "Redirs": list(stmt.get("Redirs", [])) + [merge]}


def _desugar_pipe_all(obj):
    """`a |& b` is `a 2>&1 | b`."""
    if obj.get("Type") == "BinaryCmd" and obj.get("Op") == "|&":
        return {**obj, "Op": "|", "X": _with_stderr_merged(obj["X"])}
    return obj


def _desugar_bare_for(obj):
    """`for i; do` is `for i in "$@"; do`."""
    if obj.get("Type") == "WordIter" and "InPos" not in obj:
        at = {"Parts": [{"Type": "DblQuoted", "Parts": [{"Type": "ParamExp", "Param": {"Value": "@"}}]}]}
        return {**obj, "Items": [at]}
    return obj


def normalise(obj):
    """Drop everything that is not about meaning: positions, comments, spelling."""
    if isinstance(obj, dict):
        obj = _desugar_bare_for(_desugar_pipe_all(obj))
        out = {
            k: normalise(v)
            for k, v in obj.items()
            if not is_position(v) and k not in IGNORED_KEYS
        }
        if "Redirs" in out:
            out["Redirs"] = [normalise(_canonical_redirect(r)) for r in obj["Redirs"]]
        if isinstance(out.get("Parts"), list):
            out["Parts"] = _merge_literals(out["Parts"])
        return out
    if isinstance(obj, list):
        return [normalise(x) for x in obj]
    return obj


def roundtrip_text(source: str) -> str:
    nodes = parse_string(source)
    return "\n".join(n.pretty() for n in nodes)


def check(source: str) -> str | None:
    """Return None if OK, otherwise a message describing the failure."""
    try:
        text = roundtrip_text(source)
    except NotImplementedError as exc:
        return f"not implemented yet: {exc}"
    except Exception as exc:  # noqa: BLE001 - we want the message for learners
        return f"{type(exc).__name__}: {exc}"
    try:
        same = shfmt_tree(source) == shfmt_tree(text)
    except subprocess.CalledProcessError:
        return f"printed text does not parse:\n{text}"
    if not same:
        return f"meaning changed.\n  printed: {text!r}"
    return None


def _all_cases():
    return [(g, s) for g, snippets in CASES.items() for s in snippets]


try:
    import pytest

    @pytest.mark.parametrize("group,source", _all_cases())
    def test_roundtrip(group, source):
        failure = check(source)
        if failure and failure.startswith("not implemented"):
            pytest.xfail(failure)
        assert failure is None, failure

except ImportError:  # plain-script mode
    pass


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    counts = {"ok": 0, "todo": 0, "FAIL": 0}
    for group, source in _all_cases():
        if only and only not in group:
            continue
        failure = check(source)
        if failure is None:
            status = "ok"
        elif failure.startswith("not implemented"):
            status = "todo"
        else:
            status = "FAIL"
        counts[status] += 1
        label = source.replace("\n", "\\n")
        print(f"[{status:4}] {group:20} {label}")
        if status == "FAIL":
            print("       " + failure.replace("\n", "\n       "))
    print(f"\n{counts['ok']} ok, {counts['todo']} todo, {counts['FAIL']} FAIL")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
