#!/usr/bin/env python3
"""Scratch tool: show what a snippet becomes at each stage.

    ./shfmt_try.py 'x=1 echo hi'
    echo 'ls | wc' | ./shfmt_try.py
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from shasta.ast_node import ArgChar, AstNode, CArgChar  # noqa: E402
from shasta.shfmt_to_shasta_ast import parse_string  # noqa: E402

def is_position(value) -> bool:
    # shfmt positions look like {"Offset": 3, "Line": 1, "Col": 4}
    return isinstance(value, dict) and "Offset" in value and "Line" in value


def strip_positions(obj):
    if isinstance(obj, dict):
        return {k: strip_positions(v) for k, v in obj.items() if not is_position(v)}
    if isinstance(obj, list):
        return [strip_positions(x) for x in obj]
    return obj


SKIP_FIELDS = {"line_number", "no_braces", "semicolon", "after_ampersand"}


def _fields(node):
    """The constructor arguments of a Shasta node, in order, skipping noise."""
    params = [p for p in inspect.signature(type(node).__init__).parameters if p != "self"]
    out = []
    for name in params:
        value = getattr(node, name, None)
        if name in SKIP_FIELDS or value is None or value is False or value == [] or value == ():
            continue
        out.append((name, value))
    return out


def _is_word(value) -> bool:
    return isinstance(value, list) and value and all(isinstance(x, ArgChar) for x in value)


def _word_lines(chars, label, pad) -> list[str]:
    """A word (list of ArgChars): one line if it is plain text, else one line per piece."""
    if all(isinstance(c, CArgChar) for c in chars):
        return [f'{pad}{label}: "{"".join(c.format() for c in chars)}"'.replace("\n", "\\n")]
    lines = [f"{pad}{label}:"]
    run = ""
    for c in chars:
        if isinstance(c, CArgChar):
            run += c.format()
            continue
        if run:
            lines.append(f'{pad}  C "{run}"'); run = ""
        lines += tree_of(c, indent=len(pad) // 2 + 1)
    if run:
        lines.append(f'{pad}  C "{run}"')
    return lines


def tree_of(value, indent=0, label=None) -> list[str]:
    """Readable outline of a Shasta node: class name, then its fields, nested."""
    pad = "  " * indent
    prefix = f"{label}: " if label else ""
    if _is_word(value):
        return _word_lines(value, label or "word", pad)
    if isinstance(value, ArgChar) or isinstance(value, AstNode):
        name = type(value).__name__
        fields = _fields(value)
        simple = [(k, v) for k, v in fields if isinstance(v, (str, int, bool)) and not isinstance(v, AstNode)]
        rest = [(k, v) for k, v in fields if (k, v) not in simple]
        head = f"{pad}{prefix}{name}" + ("(" + ", ".join(f"{k}={v!r}" for k, v in simple) + ")" if simple else "")
        lines = [head]
        for k, v in rest:
            lines += tree_of(v, indent + 1, k)
        return lines
    if isinstance(value, dict):  # a case item
        lines = [f"{pad}{prefix}item"]
        for k, v in value.items():
            if v in (None, False, []):
                continue
            lines += tree_of(v, indent + 1, k)
        return lines
    if isinstance(value, (list, tuple)):
        if not value:
            return [f"{pad}{prefix}[]"]
        if all(isinstance(x, (str, int)) for x in value):
            return [f"{pad}{prefix}{list(value)!r}"]
        lines = [f"{pad}{prefix}[{len(value)}]"]
        for i, v in enumerate(value):
            lines += tree_of(v, indent + 1, f"#{i}")
        return lines
    return [f"{pad}{prefix}{value!r}"]


def main() -> int:
    src = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()

    raw = subprocess.run(
        ["shfmt", "-ln=bash", "-tojson"], input=src.encode(), capture_output=True, check=True
    ).stdout
    print("== shfmt JSON (positions removed) ==")
    print(json.dumps(strip_positions(json.loads(raw)), indent=1))

    nodes = parse_string(src)
    print("\n== Shasta tree ==")
    for node in nodes:
        print("\n".join(tree_of(node)))
    print("\n== Printed back ==")
    for node in nodes:
        print(node.pretty())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
