from __future__ import annotations

import json
import re
import subprocess
from typing import Any, Callable

from .ast_node import (
    AndNode,
    ArithNode,
    ArgChar,
    AssignNode,
    AstNode,
    AArgChar,
    BackgroundNode,
    CArgChar,
    CommandNode,
    CondNode,
    CondType,
    CoprocNode,
    DupRedirNode,
    FileRedirNode,
    ForNode,
    GroupNode,
    HeredocRedirNode,
    NotNode,
    OrNode,
    PipeNode,
    QArgChar,
    RedirNode,
    RedirectionNode,
    SelectNode,
    SingleArgRedirNode,
    SubshellNode,
    TimeNode,
    VArgChar,
    string_of_arg,
)
from .shfmt_nodes import (
    ArithForNode,
    CaseNode,
    CmdSubstArgChar,
    FunctionNode,
    IfNode,
    ProcSubstArgChar,
    WhileNode,
    sequence,
)

MIN_SHFMT_VERSION = (3, 14, 0)

Json = dict[str, Any]

def check_shfmt_version(shfmt_path: str = "shfmt") -> None:
    out = subprocess.run(
        [shfmt_path, "--version"], check=True, capture_output=True, text=True
    ).stdout.strip()
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", out)
    if not match or tuple(int(g) for g in match.groups()) < MIN_SHFMT_VERSION:
        need = ".".join(map(str, MIN_SHFMT_VERSION))
        raise RuntimeError(f"shfmt >= {need} required (found {out!r})")


def parse_string(source: str, shfmt_path: str = "shfmt") -> list[AstNode]:
    """Parse bash source text into a list of top-level Shasta nodes."""
    check_shfmt_version(shfmt_path)
    proc = subprocess.run(
        [shfmt_path, "-ln=bash", "-tojson"],
        input=source.encode("utf-8", errors="surrogateescape"),
        check=True,
        capture_output=True,
    )
    return to_ast_nodes(json.loads(proc.stdout))


def parse(path: str, shfmt_path: str = "shfmt") -> list[AstNode]:
    """Parse a bash script file into a list of top-level Shasta nodes."""
    with open(path, "rb") as handle:
        source = handle.read().decode("utf-8", errors="surrogateescape")
    return parse_string(source, shfmt_path)


def to_ast_nodes(file_json: Json) -> list[AstNode]:
    assert file_json["Type"] == "File"
    return [stmt_to_node(stmt) for stmt in file_json.get("Stmts", [])]


def stmt_to_node(stmt: Json) -> AstNode:
    if stmt.get("Coprocess") or stmt.get("Disown"):
        raise NotImplementedError("mksh/zsh statement modifiers")

    cmd = stmt.get("Cmd")  # missing for a bare redirect such as `> f`
    node = _empty_command() if cmd is None else command_to_node(cmd)

    # Redirects belong to the command itself, so attach them before wrapping
    # it in `!` or `&`.
    node = with_redirs(node, [redir_to_node(r) for r in stmt.get("Redirs", [])])

    if stmt.get("Negated"):
        node = NotNode(node, no_braces=True)

    if stmt.get("Background"):
        node = BackgroundNode(
            line_number=stmt["Pos"]["Line"], node=node, redir_list=[], no_braces=True
        )

    return node


def with_redirs(node: AstNode, redirs: list[RedirectionNode]) -> AstNode:
    """Attach redirections to a command.

    A simple command carries them itself. Anything else is wrapped in a
    RedirNode, which prints them *after* the whole command (`( a ) > f`).
    (SubshellNode.redir_list is avoided: it prints them inside the parens.)
    """
    if not redirs:
        return node
    if isinstance(node, CommandNode):
        node.redir_list.extend(redirs)
        return node
    return RedirNode(line_number=None, node=node, redir_list=redirs)


def stmts_to_node(stmts: list[Json]) -> AstNode:
    """A list of statements (a body, a condition...) as one node."""
    nodes = [stmt_to_node(s) for s in stmts]
    if not nodes:
        return _empty_command()
    return sequence(nodes)


def command_to_node(cmd: Json) -> AstNode:
    handler = _COMMAND_HANDLERS.get(cmd["Type"])
    if handler is None:
        raise NotImplementedError(f"shfmt command type {cmd['Type']!r}")
    return handler(cmd)

def call_expr_to_node(cmd: Json) -> AstNode:
    """WORKED EXAMPLE: `x=1 y=2 prog arg1 arg2`.

    JSON:  {"Type": "CallExpr",
            "Assigns": [{"Name": {"Value": "x"}, "Value": <Word>}, ...],
            "Args":    [<Word>, ...]}
    Either key may be missing when empty (shfmt omits empty fields).
    """
    assignments = [assign_to_node(a) for a in cmd.get("Assigns", [])]
    arguments = [word_to_arg_chars(w) for w in cmd.get("Args", [])]
    return CommandNode(
        line_number=cmd["Pos"]["Line"],
        assignments=assignments,
        arguments=arguments,
        redir_list=[],
    )


def assign_to_node(assign: Json) -> AssignNode:
    """`x=1`, and the bash forms `x+=1`, `x[i]=1`, `x=(a b)`.

    AssignNode only has a name string and a value, so the bash-only decorations
    are folded into the name (`x+`, `x[i]`) which prints back correctly. The
    index expression is rendered to text, so nodes inside it are not kept.
    """
    if assign.get("Naked"):
        raise NotImplementedError("naked assignment outside declare")
    var = assign["Name"]["Value"]
    if assign.get("Index"):
        var += "[" + string_of_arg(arith_to_arg_chars(assign["Index"])) + "]"
    if assign.get("Append"):
        var += "+"
    if assign.get("Array"):
        val = array_to_arg_chars(assign["Array"])
    else:
        val = word_to_arg_chars(assign.get("Value"))
    return AssignNode(var=var, val=val)


def assign_to_arg_chars(assign: Json) -> list[ArgChar]:
    """An assignment as one word, for `declare x=(1 2)` style arguments."""
    name = assign.get("Name")
    if assign.get("Naked"):
        if name is None:  # a flag such as `-a`
            return word_to_arg_chars(assign.get("Value"))
        out = text_to_arg_chars(name["Value"])
        if assign.get("Index"):
            out += text_to_arg_chars("[") + arith_to_arg_chars(assign["Index"]) + text_to_arg_chars("]")
        return out
    out = text_to_arg_chars(name["Value"])
    if assign.get("Index"):
        out += text_to_arg_chars("[") + arith_to_arg_chars(assign["Index"]) + text_to_arg_chars("]")
    out += text_to_arg_chars("+=" if assign.get("Append") else "=")
    if assign.get("Array"):
        out += array_to_arg_chars(assign["Array"])
    else:
        out += word_to_arg_chars(assign.get("Value"))
    return out


def array_to_arg_chars(array: Json) -> list[ArgChar]:
    out = text_to_arg_chars("(")
    for n, elem in enumerate(array.get("Elems", [])):
        if n:
            out += text_to_arg_chars(" ")
        if elem.get("Index"):
            out += text_to_arg_chars("[") + arith_to_arg_chars(elem["Index"]) + text_to_arg_chars("]=")
        out += word_to_arg_chars(elem.get("Value"))
    return out + text_to_arg_chars(")")


def flatten_pipe(left: AstNode, right: AstNode) -> list[AstNode]:
    if isinstance(left, PipeNode):
        items = list(left.items)
    else:
        items = [left]
    items.append(right)
    return items
    
def binary_cmd_to_node(cmd: Json) -> AstNode:
    left = stmt_to_node(cmd["X"])
    right = stmt_to_node(cmd["Y"])

    op = cmd["Op"]
    if op == "&&":
        return AndNode(left, right, no_braces=True)
    elif op == "||":
        return OrNode(left, right, no_braces=True)
    elif op == "|":
        return PipeNode(is_background=False, items=flatten_pipe(left, right))
    elif op == "|&":
        # `a |& b` is `a 2>&1 | b`; the redirect goes on the command just left of the pipe
        merge = DupRedirNode("ToFD", ("fixed", 2), ("fixed", 1))
        if isinstance(left, PipeNode):
            items = list(left.items)
            items[-1] = with_redirs(items[-1], [merge])
            left = PipeNode(is_background=False, items=items)
        else:
            left = with_redirs(left, [merge])
        return PipeNode(is_background=False, items=flatten_pipe(left, right))
    else:
        raise NotImplementedError(f"BinaryCmd operator {op!r}")

def if_clause_to_node(cmd: Json) -> AstNode:
    cond = stmts_to_node(cmd["Cond"])
    then_b = stmts_to_node(cmd["Then"])

    else_json = cmd.get("Else")
    if else_json is None:
        else_b = None
    elif "Cond" in else_json:
        # `elif`: the Else is itself an IfClause, so recurse
        else_b = if_clause_to_node(else_json)
    else:
        # plain `else`: no condition, just a body
        else_b = stmts_to_node(else_json["Then"])

    return IfNode(cond=cond, then_b=then_b, else_b=else_b)


def while_clause_to_node(cmd: Json) -> AstNode:
    test = stmts_to_node(cmd["Cond"])
    body = stmts_to_node(cmd["Do"])
    if cmd.get("Until"):
        # Shasta has no `until`; `until c` is `while ! c`
        test = NotNode(test, no_braces=True)
    return WhileNode(test=test, body=body)


def for_clause_to_node(cmd: Json) -> AstNode:
    loop = cmd["Loop"]
    line_number = cmd["Pos"]["Line"]
    body = stmts_to_node(cmd["Do"])

    if loop["Type"] == "CStyleLoop":
        def part(expr):
            return [arith_to_arg_chars(expr)] if expr else []
        return ArithForNode(
            line_number=line_number,
            init=part(loop.get("Init")),
            cond=part(loop.get("Cond")),
            step=part(loop.get("Post")),
            action=body,
        )

    variable = lit_to_arg_chars(loop["Name"])
    items = [word_to_arg_chars(w) for w in loop.get("Items", [])]
    if "InPos" not in loop:
        # `for i; do` iterates over the positional parameters, i.e. `for i in "$@"`
        items = [[QArgChar([VArgChar("Normal", False, "@", [])])]]

    if cmd.get("Select"):
        return SelectNode(line_number=line_number, variable=variable, body=body, map_list=items)
    return ForNode(line_number=line_number, argument=items, body=body, variable=variable)


def case_clause_to_node(cmd: Json) -> AstNode:
    cases = []
    for item in cmd.get("Items", []):
        op = item.get("Op", ";;")
        stmts = item.get("Stmts", [])
        case = {
            "cpattern": [word_to_arg_chars(p) for p in item["Patterns"]],
            "cbody": stmts_to_node(stmts) if stmts else None,
            "fallthrough": op != ";;",
        }
        if op == ";;&":
            # `;;&` keeps testing later patterns; `fallthrough` alone means `;&`
            case["terminator"] = op
        cases.append(case)
    return CaseNode(
        line_number=cmd["Pos"]["Line"],
        argument=word_to_arg_chars(cmd["Word"]),
        cases=cases,
    )


def block_to_node(cmd: Json) -> AstNode:
    node = stmts_to_node(cmd["Stmts"])
    return GroupNode(node)


def subshell_to_node(cmd: Json) -> AstNode:
    node = stmts_to_node(cmd["Stmts"])
    line_number = cmd["Pos"]["Line"]
    return SubshellNode(line_number=line_number, body=node, redir_list=[])



def func_decl_to_node(cmd: Json) -> AstNode:
    # Keep the GroupNode: DefunNode.pretty() only prints a multi-statement body
    # correctly when it is a Group (otherwise each statement gets its own { }).
    return FunctionNode(
        line_number=cmd["Pos"]["Line"],
        name=lit_to_arg_chars(cmd["Name"]),
        body=stmt_to_node(cmd["Body"]),
        bash_mode=bool(cmd.get("RsrvWord")),
    )


# --- bash-only commands ---------------------------------------------------

def decl_clause_to_node(cmd: Json) -> AstNode:
    """declare / local / export / readonly / typeset ... as a command whose
    arguments keep their structure (`declare -a x=(1 $y)`)."""
    args = [lit_to_arg_chars(cmd["Variant"])]
    args += [assign_to_arg_chars(a) for a in cmd.get("Args", [])]
    return CommandNode(line_number=cmd["Pos"]["Line"], assignments=[], arguments=args, redir_list=[])


def let_clause_to_node(cmd: Json) -> AstNode:
    # Each expression is one shell word, so render without spaces: `let x=1 y++`
    args = [text_to_arg_chars("let")]
    args += [arith_to_arg_chars(e, spaced=False) for e in cmd.get("Exprs", [])]
    return CommandNode(line_number=cmd["Pos"]["Line"], assignments=[], arguments=args, redir_list=[])


def arithm_cmd_to_node(cmd: Json) -> AstNode:
    return ArithNode(line_number=cmd["Pos"]["Line"], body=[arith_to_arg_chars(cmd["X"])])


def test_clause_to_node(cmd: Json) -> AstNode:
    """`[[ ... ]]` as a CondNode tree."""
    return cond_expr_to_node(cmd["X"], cmd["Pos"]["Line"])


def cond_expr_to_node(expr: Json, line: int) -> CondNode:
    kind = expr["Type"]

    def build(cond_type, op=None, left=None, right=None):
        return CondNode(line, cond_type.value, op, left, right, False)

    if kind == "Word":
        return build(CondType.COND_TERM, op=word_to_arg_chars(expr))
    if kind == "ParenTest":
        return build(CondType.COND_EXPR, left=cond_expr_to_node(expr["X"], line))
    if kind == "UnaryTest":
        inner = cond_expr_to_node(expr["X"], line)
        if expr["Op"] == "!":
            # CondNode has an invert flag instead of a negation node
            if inner.invert_return:
                raise NotImplementedError("double negation inside [[ ]]")
            inner.invert_return = True
            return inner
        return build(CondType.COND_UNARY, op=text_to_arg_chars(expr["Op"]), left=inner)
    if kind == "BinaryTest":
        left = cond_expr_to_node(expr["X"], line)
        right = cond_expr_to_node(expr["Y"], line)
        if expr["Op"] == "&&":
            return build(CondType.COND_AND, left=left, right=right)
        if expr["Op"] == "||":
            return build(CondType.COND_OR, left=left, right=right)
        return build(CondType.COND_BINARY, op=text_to_arg_chars(expr["Op"]), left=left, right=right)
    raise NotImplementedError(f"test expression {kind!r}")


def time_clause_to_node(cmd: Json) -> AstNode:
    stmt = cmd.get("Stmt")
    inner = stmt_to_node(stmt) if stmt else _empty_command()
    return TimeNode(time_posix=bool(cmd.get("PosixFormat")), command=inner)


def coproc_clause_to_node(cmd: Json) -> AstNode:
    name = word_to_arg_chars(cmd["Name"]) if cmd.get("Name") else []
    return CoprocNode(name=name, body=stmt_to_node(cmd["Stmt"]))


_COMMAND_HANDLERS: dict[str, Callable[[Json], AstNode]] = {
    "CallExpr": call_expr_to_node,
    "BinaryCmd": binary_cmd_to_node,
    "IfClause": if_clause_to_node,
    "WhileClause": while_clause_to_node,
    "ForClause": for_clause_to_node,
    "CaseClause": case_clause_to_node,
    "Block": block_to_node,
    "Subshell": subshell_to_node,
    "FuncDecl": func_decl_to_node,
    "DeclClause": decl_clause_to_node,
    "LetClause": let_clause_to_node,
    "ArithmCmd": arithm_cmd_to_node,
    "TestClause": test_clause_to_node,
    "TimeClause": time_clause_to_node,
    "CoprocClause": coproc_clause_to_node,
    # Not supported: TestDecl (bats `@test`)
}


# --------------------------------------------------------------------------
# Words
#
# A Word is {"Parts": [...]}. Each part becomes one or more ArgChars.
#
# `quoted` is True while converting the inside of "...". The only thing it
# changes is how a backslash-escaped double quote in plain text is spelled,
# because QArgChar re-escapes every `"` it prints.
# --------------------------------------------------------------------------

def text_to_arg_chars(text: str) -> list[ArgChar]:
    """Literal text, character by character, printed back verbatim."""
    return [CArgChar(ord(ch), bash_mode=True) for ch in text]


def word_to_arg_chars(word: Json | None, quoted: bool = False) -> list[ArgChar]:
    chars: list[ArgChar] = []
    for part in (word or {}).get("Parts", []):
        chars.extend(word_part_to_arg_chars(part, quoted))
    return chars


def word_part_to_arg_chars(part: Json, quoted: bool = False) -> list[ArgChar]:
    handler = _WORD_PART_HANDLERS.get(part["Type"])
    if handler is None:
        raise NotImplementedError(f"shfmt word part {part['Type']!r}")
    return handler(part, quoted)


def lit_to_arg_chars(part: Json, quoted: bool = False) -> list[ArgChar]:
    """Plain text. Value is the *raw* source text: a backslash stays a
    backslash, so emitting each character verbatim prints back identically."""
    text = part["Value"]
    if not quoted:
        return text_to_arg_chars(text)

    chars: list[ArgChar] = []
    i = 0
    while i < len(text):
        pair = text[i : i + 2]
        if pair == '\\"':
            chars.append(CArgChar(ord('"'), bash_mode=True))  # Q adds the backslash back
            i += 2
        elif pair == "\\\\":
            chars += text_to_arg_chars(pair)
            i += 2
        else:
            chars.append(CArgChar(ord(text[i]), bash_mode=True))
            i += 1
    return chars


def sgl_quoted_to_arg_chars(part: Json, quoted: bool = False) -> list[ArgChar]:
    # Shasta has no single-quote node, and QArgChar prints double quotes (which
    # would make `$x` expand). Keep the quotes as literal characters instead.
    return text_to_arg_chars(("$" if part.get("Dollar") else "") + "'" + part.get("Value", "") + "'")


def dbl_quoted_to_arg_chars(part: Json, quoted: bool = False) -> list[ArgChar]:
    inner: list[ArgChar] = []
    for p in part.get("Parts", []):
        inner.extend(word_part_to_arg_chars(p, quoted=True))
    prefix = text_to_arg_chars("$") if part.get("Dollar") else []  # $"..." (translation)
    return prefix + [QArgChar(inner)]


def cmd_subst_to_arg_chars(part: Json, quoted: bool = False) -> list[ArgChar]:
    if part.get("ReplyVar") or part.get("TempFile"):
        raise NotImplementedError("${ cmd; } / ${| cmd; } substitution")
    return [CmdSubstArgChar(stmts_to_node(part.get("Stmts", [])))]


def proc_subst_to_arg_chars(part: Json, quoted: bool = False) -> list[ArgChar]:
    return [ProcSubstArgChar(part["Op"], stmts_to_node(part.get("Stmts", [])))]


def arithm_exp_to_arg_chars(part: Json, quoted: bool = False) -> list[ArgChar]:
    return [AArgChar(arith_to_arg_chars(part["X"], quoted))]


def ext_glob_to_arg_chars(part: Json, quoted: bool = False) -> list[ArgChar]:
    return text_to_arg_chars(part["Op"] + part["Pattern"]["Value"] + ")")


# Parameter expansions that fit VArgChar: operator -> (fmt, null)
_VAR_FORMS = {
    ":-": ("Minus", True), "-": ("Minus", False),
    ":+": ("Plus", True), "+": ("Plus", False),
    ":?": ("Question", True), "?": ("Question", False),
    ":=": ("Assign", True), "=": ("Assign", False),
    "%": ("TrimR", False), "%%": ("TrimRMax", False),
    "#": ("TrimL", False), "##": ("TrimLMax", False),
}
_UNSUPPORTED_PARAM_FIELDS = ("Flags", "Width", "IsSet", "Split", "GlobSubst", "RcExpand", "Modifiers")
_COMPLEX_PARAM_FIELDS = ("Excl", "NestedParam", "Index", "Slice", "Repl", "Names")
# shfmt omits empty fields, but a present-and-empty struct (`${a/}`) encodes as {},
# which is falsy in Python, so test these by key presence.


def param_exp_to_arg_chars(part: Json, quoted: bool = False) -> list[ArgChar]:
    for key in _UNSUPPORTED_PARAM_FIELDS:
        if key in part:
            raise NotImplementedError(f"parameter expansion field {key!r} (zsh/mksh)")

    name = (part.get("Param") or {}).get("Value")
    exp = part.get("Exp")
    if part.get("Short") and "Index" in part and "Dollar" not in part:
        # `a[i]` inside (( )) with no `$`: a variable to assign to, not a value
        return text_to_arg_chars(name) + text_to_arg_chars("[") + arith_to_arg_chars(part["Index"], quoted) + text_to_arg_chars("]")
    if name is not None and not any(k in part for k in _COMPLEX_PARAM_FIELDS):
        if part.get("Length") and exp is None:
            return [VArgChar("Length", False, name, [])]
        if not part.get("Length"):
            if exp is None:
                return [VArgChar("Normal", False, name, [])]
            if exp["Op"] in _VAR_FORMS:
                fmt, null = _VAR_FORMS[exp["Op"]]
                return [VArgChar(fmt, null, name, word_to_arg_chars(exp.get("Word"), quoted))]
    return param_exp_skeleton(part, quoted)


def param_exp_skeleton(part: Json, quoted: bool) -> list[ArgChar]:
    """Expansions with no VArgChar form (`${a[1]}`, `${a:1:2}`, `${a//x/y}`,
    `${!a}`, `${a^^}`...). The syntax is kept as literal characters, but every
    nested word, expression and substitution inside it stays a real node."""
    text = text_to_arg_chars
    out = text("${")
    if part.get("Excl"):
        out += text("!")
    if part.get("Length"):
        out += text("#")

    if part.get("Param"):
        out += text(part["Param"]["Value"])
    elif part.get("NestedParam"):
        out += word_part_to_arg_chars(part["NestedParam"], quoted)

    if part.get("Index"):
        out += text("[") + arith_to_arg_chars(part["Index"], quoted) + text("]")

    if "Slice" in part:
        sl = part["Slice"]
        # the space keeps `${a: -1}` from reading as the `:-` operator
        out += text(": ") + arith_to_arg_chars(sl["Offset"], quoted)
        if sl.get("Length"):
            out += text(": ") + arith_to_arg_chars(sl["Length"], quoted)

    if "Repl" in part:
        repl = part["Repl"]
        out += text("//" if repl.get("All") else "/") + word_to_arg_chars(repl.get("Orig"), quoted)
        if repl.get("With") is not None:
            out += text("/") + word_to_arg_chars(repl["With"], quoted)

    if part.get("Names"):
        out += text(part["Names"])  # ${!prefix*} / ${!prefix@}

    if "Exp" in part:
        out += text(part["Exp"]["Op"]) + word_to_arg_chars(part["Exp"].get("Word"), quoted)

    return out + text("}")


_WORD_PART_HANDLERS: dict[str, Callable[[Json, bool], list[ArgChar]]] = {
    "Lit": lit_to_arg_chars,
    "SglQuoted": sgl_quoted_to_arg_chars,
    "DblQuoted": dbl_quoted_to_arg_chars,
    "ParamExp": param_exp_to_arg_chars,
    "CmdSubst": cmd_subst_to_arg_chars,
    "ProcSubst": proc_subst_to_arg_chars,
    "ArithmExp": arithm_exp_to_arg_chars,
    "ExtGlob": ext_glob_to_arg_chars,
}

def arith_to_arg_chars(expr: Json, quoted: bool = False, spaced: bool = True) -> list[ArgChar]:
    kind = expr["Type"]
    sp = " " if spaced else ""

    def sub(e):
        return arith_to_arg_chars(e, quoted, spaced)

    if kind == "Word":
        return word_to_arg_chars(expr, quoted)
    if kind == "BinaryArithm":
        return sub(expr["X"]) + text_to_arg_chars(f"{sp}{expr['Op']}{sp}") + sub(expr["Y"])
    if kind == "UnaryArithm":
        if expr.get("Post"):
            return sub(expr["X"]) + text_to_arg_chars(expr["Op"])
        return text_to_arg_chars(expr["Op"]) + sub(expr["X"])
    if kind == "ParenArithm":
        return text_to_arg_chars("(") + sub(expr["X"]) + text_to_arg_chars(")")
    raise NotImplementedError(f"arithmetic expression {kind!r}")


_FILE_REDIRS = {  # op -> (FileRedirNode type, default fd)
    ">": ("To", 1),
    ">>": ("Append", 1),
    "<": ("From", 0),
    "<>": ("FromTo", 0),
    ">|": ("Clobber", 1),
    "<<<": ("ReadingString", 0),
}


def redir_fd(n: Json | None, default: int):
    """The redirect's file descriptor: `2>` or `{fd}>`."""
    if not n:
        return ("fixed", default)
    value = n["Value"]
    if value.isdigit():
        return ("fixed", int(value))
    if value.startswith("{") and value.endswith("}"):
        return ("var", text_to_arg_chars(value[1:-1]))
    raise NotImplementedError(f"redirect fd {value!r}")


def _plain_lit(word: Json | None) -> str | None:
    parts = (word or {}).get("Parts", [])
    if len(parts) == 1 and parts[0]["Type"] == "Lit":
        return parts[0]["Value"]
    return None


def redir_to_node(redir: Json) -> RedirectionNode:
    op = redir["Op"]
    word = redir.get("Word")

    if op in _FILE_REDIRS:
        kind, default = _FILE_REDIRS[op]
        return FileRedirNode(kind, redir_fd(redir.get("N"), default), word_to_arg_chars(word))

    if op in ("<<", "<<-"):
        return heredoc_to_node(redir)

    if op in (">&", "<&"):
        to_fd = op == ">&"
        fd = redir_fd(redir.get("N"), 1 if to_fd else 0)
        target = _plain_lit(word)
        if target == "-":
            return SingleArgRedirNode("CloseThis", fd)
        move = bool(target) and re.fullmatch(r"\d+-", target) is not None
        if move:
            target = target[:-1]
        arg = ("fixed", int(target)) if target and target.isdigit() else ("var", word_to_arg_chars(word))
        return DupRedirNode("ToFD" if to_fd else "FromFD", fd, arg, move=move)

    if op == "&>":
        return SingleArgRedirNode("ErrAndOut", ("var", word_to_arg_chars(word)))
    if op == "&>>":
        return SingleArgRedirNode("AppendErrAndOut", ("var", word_to_arg_chars(word)))

    raise NotImplementedError(f"redirect operator {op!r}")


def heredoc_to_node(redir: Json) -> HeredocRedirNode:
    word = redir["Word"]
    # A quoted delimiter (<<'EOF', <<"EOF", <<\EOF) turns off expansion in the body.
    quoted = any(p["Type"] != "Lit" or "\\" in p["Value"] for p in word["Parts"])
    return HeredocRedirNode(
        "Here" if quoted else "XHere",
        redir_fd(redir.get("N"), 0),
        word_to_arg_chars(redir.get("Hdoc")),
        kill_leading=(redir["Op"] == "<<-"),
        eof=_unquoted_delimiter(word),
    )


def _unquoted_delimiter(word: Json) -> str:
    """The heredoc marker with its quoting removed (<<'E"OF' ends at E"OF)."""
    out = []
    for p in word["Parts"]:
        if p["Type"] == "SglQuoted":
            out.append(p["Value"])
        elif p["Type"] == "DblQuoted":
            out.append("".join(re.sub(r"\\(.)", r"\1", q.get("Value", "")) for q in p.get("Parts", [])))
        else:
            out.append(re.sub(r"\\(.)", r"\1", p.get("Value", "")))
    return "".join(out)


# --------------------------------------------------------------------------

def _empty_command() -> CommandNode:
    return CommandNode(line_number=-1, assignments=[], arguments=[], redir_list=[])
