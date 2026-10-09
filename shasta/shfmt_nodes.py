"""Node subclasses used by shfmt_to_shasta_ast, with corrected `pretty()` output.

Shasta's printer was written for the dash and libbash converters. For some
shapes the shfmt converter builds, it writes text that bash reads differently
(or rejects). `ast_node.py` and the base `pretty()` methods are shared with
other tools and are deliberately left alone: each class here subclasses the
original node, overrides only `pretty()`, and is created only by this converter.

Each subclass keeps its parent's NodeName, fields and `json()`, so walkers,
`isinstance` checks and the JSON form see an ordinary Shasta node.

What each one fixes (all found by round-tripping the bash test corpus):

  Sequence          `a; b` inside `$( )` or `<( )` printed as `{ a ; }` newline `{ b ; }`
  CmdSubstArgChar   `$( ((x)) || y )` printed as `$(((x)) || y)`: ambiguous with arithmetic `$((`
                    (bash accepts it, but shfmt's parser rejects it); the padded form is unambiguous
  ProcSubstArgChar  same, for `<( )` / `>( )`
  FunctionNode      `f() ( x )` and `f() { x; } >&2` lost their shape (always `{ }`-wrapped)
  IfNode, WhileNode, ArithForNode
                    `if a; then b & fi` printed as `b &; fi`, a syntax error
  CaseNode          the `;;&` terminator printed as `;&`, which silently changes which bodies run
"""
from __future__ import annotations

from .ast_node import (
    ArithForNode as _ArithForNode,
    BArgChar,
    CaseNode as _CaseNode,
    DefunNode,
    IfNode as _IfNode,
    NotNode,
    PArgChar,
    SemiNode,
    WhileNode as _WhileNode,
    is_empty_cmd,
    string_of_arg,
    string_of_case,
)
from .print_lib import UNQUOTED, separated, string_of_redirs


def _body(node) -> str:
    """Print a command that may be a statement list."""
    return node.pretty(no_braces=True) if node.NodeName == "Semi" else node.pretty()


class Sequence(SemiNode):
    """Statements separated by newlines, never wrapped in braces."""

    def __init__(self, left_operand, right_operand):
        super().__init__(left_operand, right_operand, semicolon=False)

    def pretty(self, no_braces=False):
        return f"{_body(self.left_operand)}\n{_body(self.right_operand)}"


def sequence(nodes):
    """A list of commands as nested Sequence nodes (a single node is returned as is)."""
    acc = nodes[-1]
    for node in reversed(nodes[:-1]):
        acc = Sequence(node, acc)
    return acc


def _pad_subshell(body: str) -> str:
    # `$(((` is ambiguous with arithmetic `$((`, so a body that begins with `(` gets a space
    return f" {body} " if body[:1] == "(" else body


class CmdSubstArgChar(BArgChar):
    def pretty(self, quote_mode=UNQUOTED):
        return "$(" + _pad_subshell(_body(self.node)) + ")"


class ProcSubstArgChar(PArgChar):
    def pretty(self, quote_mode=UNQUOTED):
        return f"{self.op}{_pad_subshell(_body(self.node))})"


class FunctionNode(DefunNode):
    """Function definitions whose body is a subshell, or has redirects after it."""

    def pretty(self):
        keyword = "function " if self.bash_mode else ""
        name = string_of_arg(self.name)
        body = self.body
        if body.NodeName == "Redir" and body.node.NodeName == "Group":
            return (keyword + name + " () {\n" + body.node.pretty(no_braces=True)
                    + "\n}" + string_of_redirs(body.redir_list))
        if body.NodeName == "Redir" and body.node.NodeName == "Subshell":
            return keyword + name + " () " + body.node.pretty() + string_of_redirs(body.redir_list)
        if body.NodeName == "Subshell":
            return keyword + name + " () " + body.pretty()
        return super().pretty()


class IfNode(_IfNode):
    """Bodies end with a newline, so a trailing `&` is never followed by `;`."""

    def pretty(self):
        text = f"if {_body(self.cond)}; then\n{_body(self.then_b)}\n"
        other = self.else_b
        if not other or is_empty_cmd(other):
            return text + "fi"
        if isinstance(other, _IfNode):
            return text + "el" + other.pretty()  # elif
        return text + f"else\n{_body(other)}\nfi"


class WhileNode(_WhileNode):
    def pretty(self):
        test = self.test
        if isinstance(test, NotNode):
            keyword, test = "until", test.body
        else:
            keyword = "while"
        return f"{keyword} {_body(test)}; do\n{_body(self.body)}\ndone "


class CaseNode(_CaseNode):
    """Adds the `;;&` terminator (stored as a `terminator` key on the case item)."""

    def pretty(self):
        items = []
        for item in self.cases:
            text = string_of_case(item)
            if item.get("terminator") == ";;&" and text.endswith(";&"):
                text = text[:-2] + ";;&"
            items.append(text)
        return f"case {string_of_arg(self.argument)} in {' '.join(items)} esac"


class ArithForNode(_ArithForNode):
    def pretty(self):
        head = "; ".join(separated(string_of_arg, part) for part in (self.init, self.cond, self.step))
        return f"for (({head})); do\n{_body(self.action)}\ndone"
