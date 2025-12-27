from __future__ import annotations

import json
import subprocess
from typing import Any, Iterable

from .ast_node import (
    AstNode,
    AssignNode,
    CommandNode,
    RedirNode,
    BackgroundNode,
    NotNode,
    TimeNode,
    RedirectionNode,
    FileRedirNode,
    DupRedirNode,
    HeredocRedirNode,
    SingleArgRedirNode,
    ArgChar,
    CArgChar,
    QArgChar,
    AArgChar,
    BArgChar,
    VArgChar,
    PipeNode,
    AndNode,
    OrNode,
    IfNode,
    WhileNode,
    ForNode,
    SelectNode,
    CaseNode,
    SubshellNode,
    GroupNode,
    DefunNode,
    ArithForNode,
    ArithNode,
    CoprocNode,
    make_typed_semi_sequence,
    string_of_arg,
)

# NOTE: This adapter targets shfmt's typed JSON output.
# Use: shfmt -tojson <script.sh> > ast.json
# Then: json.load(ast.json) and pass to to_ast_nodes/to_ast_node.

_SOURCE_BYTES: bytes | None = None


def set_source(text: str) -> None:
    # Needed for exact literal reconstruction from shfmt Pos/End offsets.
    global _SOURCE_BYTES
    _SOURCE_BYTES = text.encode("utf-8", errors="surrogateescape")

# This function would live inside a parser module.
# For now it is here to keep the adapter self-contained.
# TODO: Rename to shfmt_parse
def parse(path: str, shfmt_path: str | None = None) -> list[AstNode]:
    shfmt = shfmt_path or "shfmt"
    with open(path, "rb") as handle:
        src_bytes = handle.read()
    src = src_bytes.decode("utf-8", errors="surrogateescape")
    proc = subprocess.run(
        [shfmt, "-tojson", "-filename", path],
        input=src_bytes,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    set_source(src)
    obj = json.loads(proc.stdout.decode("utf-8"))
    return to_ast_nodes(obj)

# Binary command operators (mvdan/sh BinCmdOperator) -> names
BIN_CMD_OPS = {
    10: "AndStmt",
    11: "OrStmt",
    12: "Pipe",
    13: "PipeAll",
}

# Case operators (mvdan/sh CaseOperator) -> names
CASE_OPS = {
    33: "Break",
    34: "Fallthrough",
    35: "Resume",
    36: "ResumeKorn",
}

# Redirection operators (mvdan/sh RedirOperator) -> names
REDIR_OPS = {
    54: "RdrOut",
    55: "AppOut",
    56: "RdrIn",
    57: "RdrInOut",
    58: "DplIn",
    59: "DplOut",
    60: "RdrClob",
    61: "RdrTrunc",
    62: "AppClob",
    63: "AppTrunc",
    64: "Hdoc",
    65: "DashHdoc",
    66: "WordHdoc",
    67: "RdrAll",
    68: "RdrAllClob",
    69: "RdrAllTrunc",
    70: "AppAll",
    71: "AppAllClob",
    72: "AppAllTrunc",
}

# Parameter expansion operators (mvdan/sh ParExpOperator) -> names
PAR_EXP_OPS = {
    68: "AlternateUnset",
    69: "AlternateUnsetOrNull",
    70: "DefaultUnset",
    71: "DefaultUnsetOrNull",
    72: "ErrorUnset",
    73: "ErrorUnsetOrNull",
    74: "AssignUnset",
    75: "AssignUnsetOrNull",
    76: "RemSmallSuffix",
    77: "RemLargeSuffix",
    78: "RemSmallPrefix",
    79: "RemLargePrefix",
}

PAR_EXP_TO_VAR_TYPE = {
    "AlternateUnset": "Plus",
    "AlternateUnsetOrNull": "Plus",
    "DefaultUnset": "Minus",
    "DefaultUnsetOrNull": "Minus",
    "ErrorUnset": "Question",
    "ErrorUnsetOrNull": "Question",
    "AssignUnset": "Assign",
    "AssignUnsetOrNull": "Assign",
    "RemSmallSuffix": "TrimR",
    "RemLargeSuffix": "TrimRMax",
    "RemSmallPrefix": "TrimL",
    "RemLargePrefix": "TrimLMax",
}

PAR_EXP_NULL = {
    "AlternateUnsetOrNull",
    "DefaultUnsetOrNull",
    "ErrorUnsetOrNull",
    "AssignUnsetOrNull",
}

PAR_EXP_OP_STR = {
    "AlternateUnset": "+",
    "AlternateUnsetOrNull": ":+",
    "DefaultUnset": "-",
    "DefaultUnsetOrNull": ":-",
    "ErrorUnset": "?",
    "ErrorUnsetOrNull": ":?",
    "AssignUnset": "=",
    "AssignUnsetOrNull": ":=",
    "RemSmallSuffix": "%",
    "RemLargeSuffix": "%%",
    "RemSmallPrefix": "#",
    "RemLargePrefix": "##",
}

GLOB_OPS = {
    122: "?(",
    123: "*(",
    124: "+(",
    125: "@(",
    126: "!(",
}

PROC_SUBST_OPS = {
    66: "<(",
    67: "=(",
    68: ">(",
}

UN_TEST_OPS = {
    88: "-e",
    89: "-f",
    90: "-d",
    91: "-c",
    92: "-b",
    93: "-p",
    94: "-S",
    95: "-L",
    96: "-k",
    97: "-g",
    98: "-u",
    99: "-G",
    100: "-O",
    101: "-N",
    102: "-r",
    103: "-w",
    104: "-x",
    105: "-s",
    106: "-t",
    107: "-z",
    108: "-n",
    109: "-o",
    110: "-v",
    111: "-R",
    112: "!",
    113: "(",
}

BIN_TEST_OPS = {
    112: "=~",
    113: "-nt",
    114: "-ot",
    115: "-ef",
    116: "-eq",
    117: "-ne",
    118: "-le",
    119: "-ge",
    120: "-lt",
    121: "-gt",
    122: "&&",
    123: "||",
    124: "=",
    125: "==",
    126: "!=",
    127: "<",
    128: ">",
}

# Arithmetic operator tokens (mvdan/sh token values) -> symbols
ARITH_TOKEN_STR = {
    68: "+",
    70: "-",
    38: "*",
    85: "/",
    76: "%",
    39: "**",
    40: "==",
    54: ">",
    56: "<",
    41: "!=",
    42: "<=",
    43: ">=",
    9: "&",
    12: "|",
    80: "^",
    55: ">>",
    61: "<<",
    10: "&&",
    11: "||",
    81: "^^",
    82: ",",
    72: "?",
    87: ":",
    74: "=",
    44: "+=",
    45: "-=",
    46: "*=",
    47: "/=",
    48: "%=",
    49: "&=",
    50: "|=",
    51: "^=",
    52: "<<=",
    53: ">>=",
    34: "!",
    35: "~",
    36: "++",
    37: "--",
}


def to_ast_nodes(obj: Any) -> list[AstNode]:
    if isinstance(obj, dict) and obj.get("Type") == "File":
        return [to_ast_node(stmt) for stmt in obj.get("Stmts", [])]
    if isinstance(obj, list):
        return [to_ast_node(item) for item in obj]
    return [to_ast_node(obj)]


def to_ast_node(obj: Any) -> AstNode:
    if isinstance(obj, dict) and (
        "Cmd" in obj or "Redirs" in obj or "Background" in obj or "Negated" in obj
    ):
        return _stmt_to_command(obj)
    if isinstance(obj, dict) and obj.get("Type"):
        return _command_to_ast(obj)
    raise ValueError(f"Unsupported mvdan/sh node: {type(obj)}")


def _stmt_to_command(stmt: dict[str, Any]) -> AstNode:
    cmd = _command_to_ast(stmt.get("Cmd")) if stmt.get("Cmd") else _empty_command()
    redirs = _to_redirs(stmt.get("Redirs", []))

    if stmt.get("Negated"):
        cmd = NotNode(cmd, no_braces=True)

    if stmt.get("Background"):
        return BackgroundNode(line_number=None, node=cmd, redir_list=redirs, no_braces=True)

    if redirs:
        cmd = RedirNode(line_number=None, node=cmd, redir_list=redirs)

    return cmd


def _command_to_ast(node: dict[str, Any]) -> AstNode:
    node_type = node.get("Type")
    if node_type == "CallExpr":
        return _call_expr_to_command(node)
    if node_type == "BinaryCmd":
        return _binary_cmd_to_ast(node)
    if node_type == "IfClause":
        return _if_clause_to_ast(node)
    if node_type == "WhileClause":
        return _while_clause_to_ast(node)
    if node_type == "ForClause":
        return _for_clause_to_ast(node)
    if node_type == "CaseClause":
        return _case_clause_to_ast(node)
    if node_type == "Subshell":
        return _subshell_to_ast(node)
    if node_type == "Block":
        return _block_to_ast(node)
    if node_type == "FuncDecl":
        return _func_decl_to_ast(node)
    if node_type == "ArithmCmd":
        return _arithm_cmd_to_ast(node)
    if node_type == "TimeClause":
        return _time_clause_to_ast(node)
    if node_type == "CoprocClause":
        return _coproc_clause_to_ast(node)
    if node_type == "DeclClause":
        return _decl_clause_to_ast(node)
    if node_type == "LetClause":
        return _let_clause_to_ast(node)
    if node_type == "TestClause":
        return _test_clause_to_ast(node)
    if node_type == "TestDecl":
        return _test_decl_to_ast(node)

    raise NotImplementedError(f"Unsupported mvdan/sh command node: {node_type}")


def _call_expr_to_command(node: dict[str, Any]) -> CommandNode:
    line_number = _line_from_pos(node.get("Pos"))
    assignments: list[AssignNode] = []
    extra_args: list[list[ArgChar]] = []
    for assign in node.get("Assigns", []):
        assign_node, assign_arg = _assign_to_shasta(assign)
        if assign_node:
            assignments.append(assign_node)
        if assign_arg:
            extra_args.append(assign_arg)

    arguments = [_word_to_arg_chars(w) for w in node.get("Args", [])]
    arguments = extra_args + arguments
    return CommandNode(
        line_number=line_number if line_number is not None else -1,
        assignments=assignments,
        arguments=arguments,
        redir_list=[],
    )


def _binary_cmd_to_ast(node: dict[str, Any]) -> AstNode:
    op = BIN_CMD_OPS.get(node.get("Op"))
    left = _stmt_to_command(node["X"])
    right = _stmt_to_command(node["Y"])

    if op == "AndStmt":
        return AndNode(left_operand=left, right_operand=right, no_braces=True)
    if op == "OrStmt":
        return OrNode(left_operand=left, right_operand=right, no_braces=True)
    if op in ("Pipe", "PipeAll"):
        items = _flatten_pipe_items(left) + _flatten_pipe_items(right)
        return PipeNode(is_background=False, items=items)

    raise NotImplementedError(f"Unsupported binary operator: {node.get('Op')}")


def _if_clause_to_ast(node: dict[str, Any]) -> IfNode:
    cond = _stmts_to_command(node.get("Cond", []))
    then_b = _stmts_to_command(node.get("Then", []))
    else_clause = node.get("Else")

    else_b = None
    if else_clause:
        cond_list = else_clause.get("Cond", [])
        if not cond_list:
            else_b = _stmts_to_command(else_clause.get("Then", []))
        else:
            else_b = _if_clause_to_ast(else_clause)

    return IfNode(cond=cond, then_b=then_b, else_b=else_b)


def _while_clause_to_ast(node: dict[str, Any]) -> WhileNode:
    test = _stmts_to_command(node.get("Cond", []))
    body = _stmts_to_command(node.get("Do", []))
    if node.get("Until"):
        test = NotNode(test, no_braces=True)
    return WhileNode(test=test, body=body)


def _for_clause_to_ast(node: dict[str, Any]) -> AstNode:
    loop = node.get("Loop")
    body = _stmts_to_command(node.get("Do", []))
    line_number = _line_from_pos(node.get("ForPos"))

    if not loop or "Type" not in loop:
        raise NotImplementedError("ForClause without Loop is not supported")

    if loop["Type"] == "WordIter":
        var = _lit_to_arg_chars(loop["Name"])
        items = [_word_to_arg_chars(w) for w in loop.get("Items", [])]
        if node.get("Select"):
            return SelectNode(
                line_number=line_number if line_number is not None else -1,
                variable=var,
                body=body,
                map_list=items,
            )
        return ForNode(
            line_number=line_number if line_number is not None else -1,
            argument=items,
            body=body,
            variable=var,
        )

    if loop["Type"] == "CStyleLoop":
        init = _arithm_expr_to_arg_list(loop.get("Init"))
        cond = _arithm_expr_to_arg_list(loop.get("Cond"))
        post = _arithm_expr_to_arg_list(loop.get("Post"))
        return ArithForNode(
            line_number=line_number if line_number is not None else -1,
            init=init,
            cond=cond,
            step=post,
            action=body,
        )

    raise NotImplementedError(f"Unsupported ForClause loop: {loop.get('Type')}")


def _case_clause_to_ast(node: dict[str, Any]) -> CaseNode:
    line_number = _line_from_pos(node.get("Case"))
    argument = _word_to_arg_chars(node["Word"])
    cases = []
    for item in node.get("Items", []):
        op_name = CASE_OPS.get(item.get("Op"))
        fallthrough = op_name not in (None, "Break")
        cases.append(
            {
                "cpattern": [_word_to_arg_chars(w) for w in item.get("Patterns", [])],
                "cbody": _stmts_to_command(item.get("Stmts", [])),
                "fallthrough": fallthrough,
            }
        )
    return CaseNode(line_number=line_number, argument=argument, cases=cases)


def _subshell_to_ast(node: dict[str, Any]) -> SubshellNode:
    line_number = _line_from_pos(node.get("Lparen"))
    body = _stmts_to_command(node.get("Stmts", []))
    return SubshellNode(line_number=line_number, body=body, redir_list=[])


def _block_to_ast(node: dict[str, Any]) -> GroupNode:
    body = _stmts_to_command(node.get("Stmts", []))
    return GroupNode(body)


def _func_decl_to_ast(node: dict[str, Any]) -> DefunNode:
    line_number = _line_from_pos(node.get("Position"))
    name = _lit_to_arg_chars(node.get("Name"))
    body = _stmt_to_command(node["Body"])
    return DefunNode(
        line_number=line_number if line_number is not None else -1,
        name=name,
        body=body,
        bash_mode=bool(node.get("RsrvWord")),
    )


def _arithm_cmd_to_ast(node: dict[str, Any]) -> ArithNode:
    line_number = _line_from_pos(node.get("Left"))
    body = _arithm_expr_to_arg_list(node.get("X"))
    return ArithNode(line_number=line_number if line_number is not None else -1, body=body)


def _time_clause_to_ast(node: dict[str, Any]) -> TimeNode:
    stmt = node.get("Stmt")
    inner = _stmt_to_command(stmt) if stmt is not None else _empty_command()
    return TimeNode(time_posix=bool(node.get("PosixFormat")), command=inner)


def _coproc_clause_to_ast(node: dict[str, Any]) -> CoprocNode:
    name_word = node.get("Name")
    name = _word_to_arg_chars(name_word) if name_word else []
    inner = _stmt_to_command(node.get("Stmt"))
    return CoprocNode(name=name, body=inner)


def _assign_to_shasta(
    node: dict[str, Any],
) -> tuple[AssignNode | None, list[ArgChar] | None]:
    if node.get("Append") or node.get("Array") or node.get("Index") or node.get("Naked"):
        return None, _string_to_literal_arg_chars(_assign_to_word_text(node))

    name = node.get("Name")
    value = node.get("Value")
    var = name.get("Value") if isinstance(name, dict) else ""
    return AssignNode(var=var, val=_word_to_arg_chars(value) if value else []), None


def _word_to_arg_chars(word: dict[str, Any]) -> list[ArgChar]:
    if word is None:
        return []
    parts = word.get("Parts", [])
    arg_chars: list[ArgChar] = []
    for part in parts:
        arg_chars.extend(_word_part_to_arg_chars(part))
    return arg_chars


def _word_part_to_arg_chars(part: dict[str, Any]) -> list[ArgChar]:
    literal = _literal_from_node(part)
    if literal is not None:
        return _literal_word_part_chars(literal)

    part_type = part.get("Type")
    if part_type == "Lit":
        return _string_to_arg_chars(part.get("Value", ""))
    if part_type == "SglQuoted":
        return [QArgChar(_string_to_arg_chars(part.get("Value", "")))]
    if part_type == "DblQuoted":
        inner = []
        for p in part.get("Parts", []):
            inner.extend(_word_part_to_arg_chars(p))
        return [QArgChar(inner)]
    if part_type == "ParamExp":
        return _param_exp_to_arg_chars(part)
    if part_type == "CmdSubst":
        cmd = _stmts_to_command(part.get("Stmts", []))
        return [BArgChar(cmd)]
    if part_type == "ArithmExp":
        expr = _arithm_expr_to_string(part.get("X"))
        return [AArgChar(_string_to_arg_chars(expr))]
    if part_type == "ProcSubst":
        return _literal_word_part_chars(_proc_subst_to_string(part))
    if part_type == "ExtGlob":
        return _literal_word_part_chars(_extglob_to_string(part))
    if part_type == "BraceExp":
        return _literal_word_part_chars(_brace_exp_to_string(part))

    raise NotImplementedError(f"Unsupported word part: {part_type}")


def _param_exp_to_arg_chars(node: dict[str, Any]) -> list[ArgChar]:
    return _literal_word_part_chars(_param_exp_to_string(node))


def _arithm_expr_to_arg_list(expr: dict[str, Any] | None) -> list[list[ArgChar]]:
    if not expr:
        return []
    return [_string_to_arg_chars(_arithm_expr_to_string(expr))]


def _arithm_expr_to_string(expr: dict[str, Any]) -> str:
    expr_type = expr.get("Type")
    if expr_type == "Word":
        return string_of_arg(_word_to_arg_chars(expr))
    if expr_type == "BinaryArithm":
        op = ARITH_TOKEN_STR.get(expr.get("Op"))
        if not op:
            raise NotImplementedError(f"Unsupported arithmetic op: {expr.get('Op')}")
        left = _arithm_expr_to_string(expr["X"])
        right = _arithm_expr_to_string(expr["Y"])
        return f"{left} {op} {right}"
    if expr_type == "UnaryArithm":
        op = ARITH_TOKEN_STR.get(expr.get("Op"))
        if not op:
            raise NotImplementedError(f"Unsupported unary arithmetic op: {expr.get('Op')}")
        inner = _arithm_expr_to_string(expr["X"])
        if expr.get("Post"):
            return f"{inner}{op}"
        return f"{op}{inner}"
    if expr_type == "ParenArithm":
        inner = _arithm_expr_to_string(expr["X"])
        return f"({inner})"

    raise NotImplementedError(f"Unsupported arithmetic expr: {expr_type}")


def _to_redirs(redirs: Iterable[dict[str, Any]]) -> list[RedirectionNode]:
    return [_redir_to_node(r) for r in redirs]


def _redir_to_node(redir: dict[str, Any]) -> RedirectionNode:
    op_name = REDIR_OPS.get(redir.get("Op"))
    if not op_name:
        raise NotImplementedError(f"Unsupported redirection op: {redir.get('Op')}")

    default_fd = 0 if op_name in ("RdrIn", "RdrInOut", "DplIn", "Hdoc", "DashHdoc", "WordHdoc") else 1
    fd = _redir_fd(redir.get("N"), default_fd)
    word = redir.get("Word")
    heredoc = redir.get("Hdoc")

    if op_name == "RdrOut":
        return FileRedirNode("To", fd, _word_to_arg_chars(word))
    if op_name == "AppOut":
        return FileRedirNode("Append", fd, _word_to_arg_chars(word))
    if op_name == "RdrIn":
        return FileRedirNode("From", fd, _word_to_arg_chars(word))
    if op_name == "RdrInOut":
        return FileRedirNode("FromTo", fd, _word_to_arg_chars(word))
    if op_name in ("RdrClob", "RdrTrunc"):
        return FileRedirNode("Clobber", fd, _word_to_arg_chars(word))
    if op_name in ("AppClob", "AppTrunc"):
        return FileRedirNode("Append", fd, _word_to_arg_chars(word))
    if op_name in ("Hdoc", "DashHdoc"):
        delimiter = string_of_arg(_word_to_arg_chars(word))
        heredoc_type = "Here" if _word_has_quotes(word) else "XHere"
        return HeredocRedirNode(
            heredoc_type,
            fd,
            _word_to_arg_chars(heredoc),
            kill_leading=(op_name == "DashHdoc"),
            eof=delimiter,
        )
    if op_name == "WordHdoc":
        return FileRedirNode("ReadingString", fd, _word_to_arg_chars(word))
    if op_name in ("DplIn", "DplOut"):
        dup_type = "FromFD" if op_name == "DplIn" else "ToFD"
        if _word_lit_equals(word, "-"):
            return SingleArgRedirNode("CloseThis", fd)
        return DupRedirNode(dup_type, fd, _redir_arg(word))
    if op_name in ("RdrAll", "RdrAllClob", "RdrAllTrunc"):
        return SingleArgRedirNode("ErrAndOut", ("var", _word_to_arg_chars(word)))
    if op_name in ("AppAll", "AppAllClob", "AppAllTrunc"):
        return SingleArgRedirNode("AppendErrAndOut", ("var", _word_to_arg_chars(word)))

    raise NotImplementedError(f"Unsupported redirection op: {op_name}")


def _redir_fd(
    n_lit: dict[str, Any] | None, default_fd: int
) -> tuple[str, int] | tuple[str, list[ArgChar]]:
    if not n_lit:
        return ("fixed", default_fd)
    value = n_lit.get("Value", "")
    if value.isdigit():
        return ("fixed", int(value))
    return ("var", _string_to_arg_chars(value))


def _redir_arg(word: dict[str, Any]) -> tuple[str, int] | tuple[str, list[ArgChar]]:
    if _word_is_int(word):
        return ("fixed", int(_word_lit(word)))
    return ("var", _word_to_arg_chars(word))


def _word_lit(word: dict[str, Any]) -> str:
    if not word:
        return ""
    parts = word.get("Parts", [])
    if len(parts) != 1 or parts[0].get("Type") != "Lit":
        return ""
    return parts[0].get("Value", "")


def _word_lit_equals(word: dict[str, Any], value: str) -> bool:
    return _word_lit(word) == value


def _word_is_int(word: dict[str, Any]) -> bool:
    lit = _word_lit(word)
    return lit.isdigit()


def _word_has_quotes(word: dict[str, Any] | None) -> bool:
    if not word:
        return False
    for part in word.get("Parts", []):
        if part.get("Type") in ("SglQuoted", "DblQuoted"):
            return True
    return False


def _word_to_string(word: dict[str, Any] | None) -> str:
    return string_of_arg(_word_to_arg_chars(word))


def _assign_to_word_text(node: dict[str, Any]) -> str:
    name = node.get("Name")
    var = name.get("Value") if isinstance(name, dict) else ""
    value = node.get("Value")
    array = node.get("Array")
    index = node.get("Index")
    append = "+=" if node.get("Append") else "="

    if node.get("Naked"):
        if var:
            return var
        if value:
            return _word_to_string(value)
        return ""

    if index:
        idx = _arithm_expr_to_string(index)
        if array:
            return f"{var}[{idx}]{append}{_array_expr_to_string(array)}"
        if value:
            return f"{var}[{idx}]{append}{_word_to_string(value)}"
        return f"{var}[{idx}]{append}"

    if array:
        return f"{var}{append}{_array_expr_to_string(array)}"
    if value:
        return f"{var}{append}{_word_to_string(value)}"
    return f"{var}{append}"


def _array_expr_to_string(node: dict[str, Any]) -> str:
    elems = []
    for elem in node.get("Elems", []):
        idx = elem.get("Index")
        val = elem.get("Value")
        if idx is not None:
            idx_str = _arithm_expr_to_string(idx)
            if val is None:
                elems.append(f"[{idx_str}]=")
            else:
                elems.append(f"[{idx_str}]={_word_to_string(val)}")
        elif val is not None:
            elems.append(_word_to_string(val))
    inner = " ".join(elems)
    return f"({inner})"


def _param_exp_to_string(node: dict[str, Any]) -> str:
    short = bool(node.get("Short"))
    flags = node.get("Flags")
    excl = bool(node.get("Excl"))
    length = bool(node.get("Length"))
    param = node.get("Param")
    nested = node.get("NestedParam")
    index = node.get("Index")
    slice_node = node.get("Slice")
    repl = node.get("Repl")
    names = node.get("Names")
    exp = node.get("Exp")

    def param_text() -> str:
        if param:
            return param.get("Value", "")
        if nested:
            ntype = nested.get("Type")
            if ntype == "ParamExp":
                return _param_exp_to_string(nested)
            if ntype == "CmdSubst":
                cmd = _stmts_to_command(nested.get("Stmts", []))
                return f"$({cmd.pretty()})"
        return ""

    name = param_text()
    if short and not index:
        return f"${name}"

    if length:
        return "${#" + name + "}"

    prefix = "!" if excl else ""
    buf = "${" + prefix
    if flags:
        buf += f"({flags.get('Value','')})"

    buf += name

    if index:
        buf += f"[{_arithm_expr_to_string(index)}]"
    if slice_node:
        offset = _arithm_expr_to_string(slice_node.get("Offset"))
        length_part = slice_node.get("Length")
        if length_part is None:
            buf += f":{offset}"
        else:
            buf += f":{offset}:{_arithm_expr_to_string(length_part)}"
    if repl:
        orig = _word_to_string(repl.get("Orig"))
        with_word = repl.get("With")
        with_str = _word_to_string(with_word) if with_word else ""
        buf += f"/{orig}/{with_str}"
    if names:
        # Names operator is encoded as a token.
        op = "*" if names == 1 else "@"
        buf = "${!" + name + op
    if exp:
        op_name = PAR_EXP_OPS.get(exp.get("Op"))
        op_str = PAR_EXP_OP_STR.get(op_name, "")
        buf += f"{op_str}{_word_to_string(exp.get('Word'))}"

    buf += "}"
    return buf


def _proc_subst_to_string(node: dict[str, Any]) -> str:
    op = PROC_SUBST_OPS.get(node.get("Op"), "<(")
    cmd = _stmts_to_command(node.get("Stmts", []))
    return f"{op}{cmd.pretty()})"


def _extglob_to_string(node: dict[str, Any]) -> str:
    op = GLOB_OPS.get(node.get("Op"), "?(")
    pattern = node.get("Pattern", {}).get("Value", "")
    return f"{op}{pattern})"


def _brace_exp_to_string(node: dict[str, Any]) -> str:
    elems = [_word_to_string(w) for w in node.get("Elems", [])]
    if node.get("Sequence"):
        inner = "..".join(elems)
    else:
        inner = ",".join(elems)
    return "{" + inner + "}"


def _literal_word_part_chars(text: str) -> list[ArgChar]:
    return [CArgChar(ord(ch), bash_mode=True) for ch in text]


def _literal_from_node(node: dict[str, Any]) -> str | None:
    if _SOURCE_BYTES is None:
        return None
    pos = node.get("Pos")
    end = node.get("End")
    if not isinstance(pos, dict) or not isinstance(end, dict):
        return None
    start = pos.get("Offset")
    finish = end.get("Offset")
    if start is None or finish is None:
        return None
    try:
        return _SOURCE_BYTES[int(start) : int(finish)].decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return None


def _lit_to_arg_chars(lit: dict[str, Any] | None) -> list[ArgChar]:
    if not lit:
        return []
    return _string_to_arg_chars(lit.get("Value", ""))


def _string_to_arg_chars(text: str) -> list[ArgChar]:
    return [CArgChar(ord(ch), bash_mode=True) for ch in text]


def _string_to_literal_arg_chars(text: str) -> list[ArgChar]:
    return _string_to_arg_chars(text)


def _flatten_pipe_items(node: AstNode) -> list[AstNode]:
    if isinstance(node, PipeNode):
        return list(node.items)
    return [node]


def _stmts_to_command(stmts: list[dict[str, Any]]) -> AstNode:
    nodes = [_stmt_to_command(stmt) for stmt in stmts]
    if not nodes:
        return _empty_command()
    if len(nodes) == 1:
        return nodes[0]
    return make_typed_semi_sequence(nodes)


def _empty_command() -> CommandNode:
    return CommandNode(line_number=-1, assignments=[], arguments=[], redir_list=[])


def _line_from_pos(pos: dict[str, Any] | None) -> int | None:
    if not isinstance(pos, dict):
        return None
    line = pos.get("Line")
    return int(line) if line is not None else None


def _decl_clause_to_ast(node: dict[str, Any]) -> CommandNode:
    variant = node.get("Variant")
    args = [_string_to_arg_chars(variant.get("Value", ""))] if variant else []
    for assign in node.get("Args", []):
        args.append(_string_to_literal_arg_chars(_assign_to_word_text(assign)))
    return CommandNode(line_number=-1, assignments=[], arguments=args, redir_list=[])


def _let_clause_to_ast(node: dict[str, Any]) -> CommandNode:
    exprs = [_arithm_expr_to_string(expr) for expr in node.get("Exprs", [])]
    args = [_string_to_arg_chars("let")] + [_string_to_literal_arg_chars(e) for e in exprs]
    return CommandNode(line_number=-1, assignments=[], arguments=args, redir_list=[])


def _test_clause_to_ast(node: dict[str, Any]) -> CommandNode:
    expr = node.get("X")
    words = [_string_to_arg_chars("[[")]
    words.extend(_test_expr_to_words(expr))
    words.append(_string_to_arg_chars("]]"))
    return CommandNode(line_number=-1, assignments=[], arguments=words, redir_list=[])


def _test_expr_to_words(expr: dict[str, Any]) -> list[list[ArgChar]]:
    etype = expr.get("Type")
    if etype == "Word":
        return [_word_to_arg_chars(expr)]
    if etype == "UnaryTest":
        op = UN_TEST_OPS.get(expr.get("Op"), "")
        inner = _test_expr_to_words(expr.get("X"))
        return [_string_to_arg_chars(op)] + inner
    if etype == "BinaryTest":
        op = BIN_TEST_OPS.get(expr.get("Op"), "")
        left = _test_expr_to_words(expr.get("X"))
        right = _test_expr_to_words(expr.get("Y"))
        return left + [_string_to_arg_chars(op)] + right
    if etype == "ParenTest":
        inner = _test_expr_to_words(expr.get("X"))
        return [_string_to_arg_chars("(")] + inner + [_string_to_arg_chars(")")]

    raise NotImplementedError(f"Unsupported test expr: {etype}")


def _test_decl_to_ast(node: dict[str, Any]) -> CommandNode:
    desc = _word_to_string(node.get("Description"))
    body = _stmt_to_command(node.get("Body"))
    body_str = body.pretty()
    if body.NodeName != "Group":
        body_str = "{ " + body_str + " ; }"
    text = f"@test {desc} {body_str}"
    return CommandNode(
        line_number=_line_from_pos(node.get("Position")) or -1,
        assignments=[],
        arguments=[_literal_word_part_chars(text)],
        redir_list=[],
    )
