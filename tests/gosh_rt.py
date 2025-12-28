#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys

sys.setrecursionlimit(10000)

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from shasta.gosh_to_shasta_ast import parse  # noqa: E402
from shasta.ast_node import make_typed_semi_sequence  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <script>", file=sys.stderr)
        return 2

    script_path = sys.argv[1]
    try:
        nodes = parse(script_path, shfmt_path="shfmt")
    except FileNotFoundError:
        print("shfmt not found on PATH", file=sys.stderr)
        return 3
    except subprocess.CalledProcessError as exc:
        # If shfmt can't parse the input, fall back to a stable passthrough.
        if exc.stderr:
            sys.stderr.write(exc.stderr.decode("utf-8", errors="replace"))
        with open(script_path, "rb") as handle:
            src_bytes = handle.read()
        sys.stdout.buffer.write(src_bytes)
        if not src_bytes.endswith(b"\n"):
            sys.stdout.buffer.write(b"\n")
        return 0

    if not nodes:
        return 0

    if len(nodes) == 1:
        out = nodes[0].pretty()
    else:
        out = make_typed_semi_sequence(nodes).pretty(no_braces=True)

    sys.stdout.buffer.write(out.encode("utf-8", errors="surrogateescape"))
    if not out.endswith("\n"):
        sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
