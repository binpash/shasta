#!/usr/bin/env python3

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from shasta.ast_node import (
    ArgChar,
    CArgChar,
    CommandNode,
    CondNode,
    CondType,
    QArgChar,
    ast_node_to_untyped_deep,
    cond_node_to_command_node,
)


def argchars(text: str) -> list[ArgChar]:
    return [CArgChar(ord(ch), bash_mode=True) for ch in text]


def qarg(text: str) -> list[ArgChar]:
    return [QArgChar(argchars(text))]


def cond_term(text: str, line: int = 1, invert: bool = False) -> CondNode:
    return CondNode(line, CondType.COND_TERM.value, argchars(text), None, None, invert)


def cond_term_raw(
    arg_list: list[ArgChar], line: int = 1, invert: bool = False
) -> CondNode:
    return CondNode(line, CondType.COND_TERM.value, arg_list, None, None, invert)


def cond_unary(
    op: str, inner: CondNode, line: int = 1, invert: bool = False
) -> CondNode:
    return CondNode(line, CondType.COND_UNARY.value, argchars(op), inner, None, invert)


def cond_binary(
    op: str, left: CondNode, right: CondNode, line: int = 1, invert: bool = False
) -> CondNode:
    return CondNode(line, CondType.COND_BINARY.value, argchars(op), left, right, invert)


def cond_and(
    left: CondNode, right: CondNode, line: int = 1, invert: bool = False
) -> CondNode:
    return CondNode(line, CondType.COND_AND.value, None, left, right, invert)


def cond_or(
    left: CondNode, right: CondNode, line: int = 1, invert: bool = False
) -> CondNode:
    return CondNode(line, CondType.COND_OR.value, None, left, right, invert)


def cond_expr(inner: CondNode, line: int = 1, invert: bool = False) -> CondNode:
    return CondNode(line, CondType.COND_EXPR.value, None, inner, None, invert)


def cmd(args: list[list[ArgChar]], line: int = 1) -> CommandNode:
    return CommandNode(line, [], [argchars("[[")] + args + [argchars("]]")], [])


def assert_cmd(cond: CondNode, expected: CommandNode) -> None:
    actual = cond_node_to_command_node(cond)
    assert ast_node_to_untyped_deep(actual) == ast_node_to_untyped_deep(expected)


def test_term_and_invert() -> None:
    cond = cond_term("x")
    expected = cmd([argchars("x")])
    assert_cmd(cond, expected)

    cond = cond_term("x", invert=True)
    expected = cmd([argchars("!"), argchars("x")])
    assert_cmd(cond, expected)


def test_term_quoted() -> None:
    cond = cond_term_raw(qarg("a b"))
    expected = cmd([qarg("a b")])
    assert_cmd(cond, expected)


def test_unary_ops() -> None:
    cond = cond_unary("-f", cond_term("file"))
    expected = cmd([argchars("-f"), argchars("file")])
    assert_cmd(cond, expected)

    cond = cond_unary("-n", cond_term("x"), invert=True)
    expected = cmd([argchars("!"), argchars("-n"), argchars("x")])
    assert_cmd(cond, expected)

    cond = cond_unary("-z", cond_term_raw(qarg("")))
    expected = cmd([argchars("-z"), qarg("")])
    assert_cmd(cond, expected)

    cond = cond_unary("-d", cond_term("dir", invert=True))
    expected = cmd([argchars("-d"), argchars("!"), argchars("dir")])
    assert_cmd(cond, expected)


def test_binary_ops() -> None:
    cond = cond_binary("=", cond_term("a"), cond_term("b"))
    expected = cmd([argchars("a"), argchars("="), argchars("b")])
    assert_cmd(cond, expected)

    cond = cond_binary("!=", cond_term("a"), cond_term("b"), invert=True)
    expected = cmd([argchars("!"), argchars("a"), argchars("!="), argchars("b")])
    assert_cmd(cond, expected)

    cond = cond_binary("-eq", cond_term("1"), cond_term("2"))
    expected = cmd([argchars("1"), argchars("-eq"), argchars("2")])
    assert_cmd(cond, expected)

    cond = cond_binary("=", cond_term_raw(qarg("a b")), cond_term_raw(qarg("c d")))
    expected = cmd([qarg("a b"), argchars("="), qarg("c d")])
    assert_cmd(cond, expected)


def test_and_or_expr() -> None:
    cond = cond_and(cond_term("a"), cond_term("b"))
    expected = cmd([argchars("a"), argchars("&&"), argchars("b")])
    assert_cmd(cond, expected)

    cond = cond_or(cond_term("a"), cond_term("b"))
    expected = cmd([argchars("a"), argchars("||"), argchars("b")])
    assert_cmd(cond, expected)

    cond = cond_expr(cond_term("a"))
    expected = cmd([argchars("("), argchars("a"), argchars(")")])
    assert_cmd(cond, expected)

    cond = cond_expr(cond_binary("=", cond_term("a"), cond_term("b")), invert=True)
    expected = cmd(
        [
            argchars("!"),
            argchars("("),
            argchars("a"),
            argchars("="),
            argchars("b"),
            argchars(")"),
        ]
    )
    assert_cmd(cond, expected)


def test_nested_combinations() -> None:
    cond = cond_and(
        cond_unary("-n", cond_term("x")),
        cond_binary("=", cond_term("a"), cond_term("b")),
    )
    expected = cmd(
        [
            argchars("-n"),
            argchars("x"),
            argchars("&&"),
            argchars("a"),
            argchars("="),
            argchars("b"),
        ]
    )
    assert_cmd(cond, expected)

    cond = cond_or(
        cond_expr(cond_binary("=", cond_term("a"), cond_term("b"))),
        cond_term("c"),
    )
    expected = cmd(
        [
            argchars("("),
            argchars("a"),
            argchars("="),
            argchars("b"),
            argchars(")"),
            argchars("||"),
            argchars("c"),
        ]
    )
    assert_cmd(cond, expected)


def test_complex_expressions() -> None:
    cond = cond_or(
        cond_expr(cond_and(cond_term("a"), cond_term("b"))),
        cond_expr(cond_and(cond_term("c"), cond_term("d"))),
    )
    expected = cmd(
        [
            argchars("("),
            argchars("a"),
            argchars("&&"),
            argchars("b"),
            argchars(")"),
            argchars("||"),
            argchars("("),
            argchars("c"),
            argchars("&&"),
            argchars("d"),
            argchars(")"),
        ]
    )
    assert_cmd(cond, expected)

    cond = cond_and(
        cond_expr(cond_or(cond_term("a"), cond_term("b")), invert=True),
        cond_expr(
            cond_or(
                cond_term("c"),
                cond_expr(cond_and(cond_term("d"), cond_term("e"))),
            )
        ),
    )
    expected = cmd(
        [
            argchars("!"),
            argchars("("),
            argchars("a"),
            argchars("||"),
            argchars("b"),
            argchars(")"),
            argchars("&&"),
            argchars("("),
            argchars("c"),
            argchars("||"),
            argchars("("),
            argchars("d"),
            argchars("&&"),
            argchars("e"),
            argchars(")"),
            argchars(")"),
        ]
    )
    assert_cmd(cond, expected)

    cond = cond_or(
        cond_and(cond_term("a"), cond_term("b")),
        cond_or(cond_term("c"), cond_term("d")),
    )
    expected = cmd(
        [
            argchars("a"),
            argchars("&&"),
            argchars("b"),
            argchars("||"),
            argchars("c"),
            argchars("||"),
            argchars("d"),
        ]
    )
    assert_cmd(cond, expected)


def test_line_number_passthrough() -> None:
    cond = cond_term("x", line=5)
    expected = cmd([argchars("x")], line=5)
    assert_cmd(cond, expected)


def run_tests() -> int:
    tests = [
        test_term_and_invert,
        test_term_quoted,
        test_unary_ops,
        test_binary_ops,
        test_and_or_expr,
        test_nested_combinations,
        test_complex_expressions,
        test_line_number_passthrough,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"{test.__name__}: OK")
        except AssertionError as exc:
            failures += 1
            print(f"{test.__name__}: FAIL")
            print(exc)
    return failures


if __name__ == "__main__":
    raise SystemExit(run_tests())
