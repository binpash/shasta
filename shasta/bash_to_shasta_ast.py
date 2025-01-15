from __future__ import annotations

from typing import Union, TYPE_CHECKING

# bulk imports are annoying but necessary to keep linters happy
# and disambiguate between classes with the same name

from .ast_node import (
    AstNode,
    AssignNode,
    CommandNode,
    DupRedirNode,
    SingleArgRedirNode,
    FileRedirNode,
    HeredocRedirNode,
    RedirNode,
    NotNode,
    TimeNode,
    RedirectionNode,
    ArgChar,
    CondNode,
    ArithForNode,
    ArithNode,
    SelectNode,
    SubshellNode,
    CoprocNode,
    CaseNode,
    WhileNode,
    IfNode,
    ForNode,
    GroupNode,
    DefunNode,
    BackgroundNode,
    SemiNode,
    PipeNode,
    AndNode,
    OrNode,
)

if TYPE_CHECKING:
    from libbash.bash_command import (
        Command,
        CommandType,
        Redirect,
        WordDesc,
        Pattern,
        SubshellCom,
        ArithCom,
        ArithForCom,
        CommandFlag,
        CoprocCom,
        CondCom,
        GroupCom,
        CaseCom,
        WhileCom,
        IfCom,
        ForCom,
        SimpleCom,
        SelectCom,
        Connection,
    )

from .flags import CommandFlag, CommandType, ConnectionType, PatternFlag, RInstruction, WordDescFlag, RedirectFlag


from .subst import expand_word

IN_FUNCTION = False


def is_empty_command(node: AstNode) -> bool:
    return (
        node.NodeName == "CommandNode"
        and len(node.arguments) == 0
        and len(node.assignments) == 0
        and (node.redir_list is None or len(node.redir_list) == 0)
    )


def to_ast_nodes(node_list: list[Command]) -> list[AstNode]:
    return [to_ast_node(node) for node in node_list]


def to_ast_node(node: Command) -> AstNode:
    node_type = node.type

    # Enum equality is usually bad practice,
    # but these aren't the same type (libbash enum vs shasta enum),
    # so they have to be compared based upon their int values.
    if node_type == CommandType.CM_FOR:
        return_node = to_for_node(node.value.for_com)
    elif node_type == CommandType.CM_CASE:
        return_node = to_case_node(node.value.case_com)
    elif node_type == CommandType.CM_WHILE:
        return_node = to_while_node(node.value.while_com)
    elif node_type == CommandType.CM_IF:
        return_node = to_if_node(node.value.if_com)
    elif node_type == CommandType.CM_SIMPLE:
        return_node = to_command_node(node.value.simple_com)
    elif node_type == CommandType.CM_SELECT:
        return_node = to_select_node(node.value.select_com)
    elif node_type == CommandType.CM_CONNECTION:
        return_node = to_connection_node(node.value.connection, node.redirects)
    elif node_type == CommandType.CM_FUNCTION_DEF:
        return_node = to_function_def_node(node)
    elif node_type == CommandType.CM_UNTIL:
        return_node = to_until_node(node.value.while_com)
    elif node_type == CommandType.CM_GROUP:
        return_node = to_group_node(node.value.group_com)
    elif node_type == CommandType.CM_ARITH:
        return_node = to_arith_node(node.value.arith_com)
    elif node_type == CommandType.CM_COND:
        return_node = to_cond_node(node.value.cond_com)
    elif node_type == CommandType.CM_ARITH_FOR:
        return_node = to_arith_for_node(node.value.arith_for_com)
    elif node_type == CommandType.CM_SUBSHELL:
        return_node = to_subshell_node(node.value.subshell_com)
    elif node_type == CommandType.CM_COPROC:
        return_node = to_coproc_node(node.value.coproc_com)
    else:
        raise ValueError("Invalid node type")

    return_node = try_wrap_redir(return_node, node.redirects)
    return_node = try_wrap_flags(return_node, node.flags)
    return return_node


def try_wrap_redir(node: AstNode, redirs: list[Redirect]) -> AstNode:
    if len(redirs) > 0:
        return RedirNode(
            line_number=None,  # MICHAEL - bash doesn't store line numbers here, assuming that doesn't really matter
            node=node,
            redir_list=to_redirs(redirs),
        )
    else:
        return node


def try_wrap_flags(node: AstNode, flags: list[CommandFlag]) -> AstNode:
    if CommandFlag.CMD_INVERT_RETURN in flags:
        node = NotNode(body=node, no_braces=True)

    if CommandFlag.CMD_TIME_PIPELINE in flags:
        return TimeNode(time_posix=CommandFlag.CMD_TIME_POSIX in flags, command=node)
    else:
        return node


def to_for_node(node: ForCom) -> ForNode:
    line_number = node.line
    action = node.action
    variable = node.name
    map_list = node.map_list
    return ForNode(
        line_number=line_number,
        argument=to_args(map_list),
        body=to_ast_node(action),
        variable=to_arg_char(variable),
    )


def to_case_node(node: CaseCom) -> CaseNode:
    line_number = node.line
    argument = node.word
    cases = node.clauses
    return CaseNode(
        line_number=line_number,
        argument=to_arg_char(argument),
        cases=to_case_list(cases),
    )


def to_while_node(node: WhileCom) -> WhileNode:
    test = node.test
    body = node.action
    return WhileNode(test=to_ast_node(test), body=to_ast_node(body))


def to_if_node(node: IfCom) -> IfNode:
    cond = node.test
    then_b = node.true_case
    else_b = node.false_case
    return IfNode(
        cond=to_ast_node(cond),
        then_b=to_ast_node(then_b),
        else_b=to_ast_node(else_b) if else_b else None,
    )


def to_assign_node(word: WordDesc) -> AssignNode:
    # this is valid because bash variables can't have '=' in their names
    assigns = word.word.split(b"=", 1)
    assign_var = assigns[0]
    assign_val = assigns[1]
    return AssignNode(
        var=assign_var.decode("utf-8"), val=to_arg_char_bytes(assign_val, word.flags)
    )


def to_command_node(node: SimpleCom) -> CommandNode:
    line_number = node.line
    arguments = node.words
    redirs = node.redirects

    assignments = []
    new_arguments = []
    for i, word in enumerate(arguments):
        flags = word.flags
        if WordDescFlag.W_ASSIGNMENT in flags and i == 0:
            assignments.append(to_assign_node(word))
        else:
            new_arguments.append(to_arg_char(word))

    return CommandNode(
        line_number=line_number,
        assignments=assignments,
        arguments=new_arguments,
        redir_list=to_redirs(redirs),
    )


def to_select_node(node: SelectCom) -> SelectNode:
    line_number = node.line
    action = node.action
    variable = node.name
    map_list = node.map_list
    return SelectNode(
        line_number=line_number,
        body=to_ast_node(action),
        variable=to_arg_char(variable),
        map_list=to_args(map_list),
    )


def to_function_def_node(node: Command) -> DefunNode:
    global IN_FUNCTION
    line_number = node.value.function_def.line
    name = node.value.function_def.name
    body = node.value.function_def.command
    IN_FUNCTION = True
    ast_node = DefunNode(
        line_number=line_number, name=to_arg_char(name), body=to_ast_node(body), bash_mode=True
    )
    IN_FUNCTION = False
    return ast_node


def to_connection_node(
    node: Connection, redirs: list[Redirect]
) -> Union[BackgroundNode, SemiNode, PipeNode, AndNode, OrNode]:
    conn_type = node.connector
    left = node.first
    right = node.second
    if conn_type == ConnectionType.AMPERSAND:
        return BackgroundNode(
            line_number=None,  # MICHAEL - bash doesn't store line numbers here, assuming that doesn't really matter
            node=to_ast_node(left),
            redir_list=to_redirs(redirs),
            after_ampersand=to_ast_node(right) if right else None,
            no_braces=True,
        )
    elif conn_type == ConnectionType.SEMICOLON:
        return SemiNode(
            left_operand=to_ast_node(left),
            right_operand=to_ast_node(right),
            semicolon=not IN_FUNCTION,
        )  # getting a little C-like here with global variables :(
    elif conn_type == ConnectionType.PIPE:
        return PipeNode(
            is_background=False,  # MICHAEL - bash just wraps the pipe in a background node if it's a background pipe
            items=(
                [to_ast_node(left)]
                if right is None
                else [to_ast_node(left), to_ast_node(right)]
            ),
        )  # MICHAEL - is it fine to not unwrap
    elif conn_type == ConnectionType.AND_AND:
        return AndNode(
            left_operand=to_ast_node(left),
            right_operand=to_ast_node(right),
            no_braces=True,
        )
    elif conn_type == ConnectionType.OR_OR:
        return OrNode(
            left_operand=to_ast_node(left),
            right_operand=to_ast_node(right),
            no_braces=True,
        )
    elif conn_type == ConnectionType.NEWLINE:
        raise ValueError(
            "Newline connections are not implemented"
        )  # this seems to be unused
    else:
        raise ValueError("Invalid connection type")


def to_until_node(node: WhileCom) -> WhileNode:
    test = node.test
    body = node.action
    return WhileNode(
        test=NotNode(to_ast_node(test)),  # not node make it an until
        body=to_ast_node(body),
    )


def to_group_node(node: GroupCom) -> GroupNode:
    # TODO: Support redirections
    # Libbash doesn't store the redirs currently
    return GroupNode(to_ast_node(node.command))


def to_arith_node(node: ArithCom) -> ArithNode:
    exp = node.exp
    line = node.line
    return ArithNode(line_number=line, body=to_args(exp))


def to_cond_node(node: CondCom) -> CondNode:
    line = node.line
    cond_type = node.type
    op = to_arg_char(node.op) if node.op else None
    left = to_cond_node(node.left) if node.left else None
    right = to_cond_node(node.right) if node.right else None
    invert_return = True if CommandFlag.CMD_INVERT_RETURN in node.flags else False
    return CondNode(
        line_number=line,
        cond_type=cond_type,
        op=op,
        left=left,
        right=right,
        invert_return=invert_return,
    )


def to_arith_for_node(node: ArithForCom) -> ArithForNode:
    line = node.line
    init = node.init
    test = node.test
    step = node.step
    body = node.action

    return ArithForNode(
        line_number=line,
        init=to_args(init),
        cond=to_args(test),
        step=to_args(step),
        action=to_ast_node(body),
    )


def to_subshell_node(node: SubshellCom) -> SubshellNode:
    line = node.line
    body = node.command
    return SubshellNode(
        line_number=line,
        body=to_ast_node(body),
        redir_list=None,  # MICHAEL - bash doesn't store redirections here
    )


def to_coproc_node(node: CoprocCom) -> CoprocNode:
    name = node.name
    action = node.command
    return CoprocNode(name=to_arg_char_string(name), body=to_ast_node(action))


def to_arg_char_bytes(word: bytes, flags: list[WordDescFlag]) -> list[ArgChar]:
    chars = split_utf8(word)
    c_arg_chars = [int.from_bytes(c, byteorder="big") for c in chars]
    return expand_word(c_arg_chars, flags)


def split_utf8(word: bytes) -> list[bytes]:
    split_bytes = []
    i = 0
    while i < len(word):
        for j in range(1, 5):  # UTF-8 characters can be between 1 and 4 bytes long
            # Attempt to decode the next 1-4 bytes
            if valid_utf8(word[i : i + j]):
                split_bytes.append(word[i : i + j])
                i += j  # Move past the successfully decoded character
                break
            else:
                if (
                    j == 4
                ):  # If we've reached 4 bytes without success, it's an invalid sequence
                    split_bytes.append(word[i : i + 1])
                    i += 1  # Move past the invalid byte
    return split_bytes

def valid_utf8(str: bytes) -> bool:    
    try:
        str.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True
    
def to_arg_char_string(word: str) -> list[ArgChar]:
    return to_arg_char_bytes(word.encode("utf-8"), [])


def to_arg_char(word: WordDesc) -> list[ArgChar]:
    return to_arg_char_bytes(word.word, word.flags)


def to_args(words: list[WordDesc]) -> list[list[ArgChar]]:
    return [to_arg_char(word) for word in words]


def to_case_list(cases: list[Pattern]) -> list[dict]:
    return [
        {
            "cpattern": to_args(case.patterns),
            "cbody": to_ast_node(case.action) if case.action else None,
            "fallthrough": PatternFlag.CASEPAT_FALLTHROUGH in case.flags
        }
        for case in cases
    ]


def to_redirs(redirs: list[Redirect]) -> list[RedirectionNode]:
    return [to_redir(redir) for redir in redirs]


def to_redir(redir: Redirect) -> RedirectionNode:
    redirector = redir.redirector
    rflags = redir.rflags
    instruction = redir.instruction
    redirectee = redir.redirectee
    here_doc_eof = redir.here_doc_eof

    the_fd = (
        ("var", to_arg_char(redirector.filename))
        if RedirectFlag.REDIR_VARASSIGN in rflags
        else ("fixed", redirector.dest)
    )
    arg_as_filename = to_arg_char(redirectee.filename) if redirectee.filename else None
    arg_as_either = (
        ("var", to_arg_char(redirectee.filename))
        if redirectee.filename
        else ("fixed", redirectee.dest)
    )

    if instruction == RInstruction.R_OUTPUT_DIRECTION:
        return FileRedirNode(redir_type="To", fd=the_fd, arg=arg_as_filename)
    elif instruction == RInstruction.R_INPUT_DIRECTION:
        return FileRedirNode(
            redir_type="From",
            fd=the_fd,
            arg=arg_as_filename,
        )
    elif instruction == RInstruction.R_INPUTA_DIRECTION:
        # this redirection is never created in parse.y in the bash source
        raise ValueError("RInstruction.R_INPUTA_DIRECTION not implemented")
    elif instruction == RInstruction.R_APPENDING_TO:
        return FileRedirNode(
            redir_type="Append",
            fd=the_fd,
            arg=to_arg_char(redirectee.filename),
        )
    elif instruction == RInstruction.R_READING_UNTIL:
        return HeredocRedirNode(
            heredoc_type=(
                "Here"
                if WordDescFlag.W_QUOTED in redirectee.filename.flags
                else "XHere"
            ),
            fd=the_fd,
            arg=arg_as_filename,
            eof=here_doc_eof,
        )
    elif instruction == RInstruction.R_READING_STRING:
        return FileRedirNode(
            redir_type="ReadingString",
            fd=the_fd,
            arg=arg_as_filename,
        )
    elif instruction == RInstruction.R_DUPLICATING_INPUT:
        return DupRedirNode(
            dup_type="FromFD",
            fd=the_fd,
            arg=arg_as_either,
        )
    elif instruction == RInstruction.R_DUPLICATING_OUTPUT:
        return DupRedirNode(
            dup_type="ToFD",
            fd=the_fd,
            arg=arg_as_either,
        )
    elif instruction == RInstruction.R_DEBLANK_READING_UNTIL:
        return HeredocRedirNode(
            heredoc_type=(
                "Here"
                if WordDescFlag.W_QUOTED in redirectee.filename.flags
                else "XHere"
            ),
            fd=the_fd,
            arg=to_arg_char(redirectee.filename),
            kill_leading=True,
        )
    elif instruction == RInstruction.R_CLOSE_THIS:
        return SingleArgRedirNode(
            redir_type="CloseThis",
            fd=the_fd,
        )
    elif instruction == RInstruction.R_ERR_AND_OUT:
        return SingleArgRedirNode(
            redir_type="ErrAndOut", fd=("var", to_arg_char(redirectee.filename))
        )
    elif instruction == RInstruction.R_INPUT_OUTPUT:
        return FileRedirNode(
            redir_type="FromTo",
            fd=the_fd,
            arg=arg_as_filename,
        )
    elif instruction == RInstruction.R_OUTPUT_FORCE:
        return FileRedirNode(
            redir_type="Clobber",
            fd=the_fd,
            arg=arg_as_filename,
        )
    elif instruction == RInstruction.R_DUPLICATING_INPUT_WORD:
        return DupRedirNode(
            dup_type="FromFD",
            fd=the_fd,
            arg=arg_as_either,
        )
    elif instruction == RInstruction.R_DUPLICATING_OUTPUT_WORD:
        return DupRedirNode(
            dup_type="ToFD",
            fd=the_fd,
            arg=arg_as_either,
        )
    elif instruction == RInstruction.R_MOVE_INPUT:
        return DupRedirNode(
            dup_type="FromFD",
            fd=the_fd,
            arg=arg_as_either,
            move=True,
        )
    elif instruction == RInstruction.R_MOVE_OUTPUT:
        return DupRedirNode(
            dup_type="ToFD",
            fd=the_fd,
            arg=arg_as_either,
            move=True,
        )
    elif instruction == RInstruction.R_MOVE_INPUT_WORD:
        return DupRedirNode(
            dup_type="FromFD",
            fd=the_fd,
            arg=arg_as_either,
            move=True,
        )
    elif instruction == RInstruction.R_MOVE_OUTPUT_WORD:
        return DupRedirNode(
            dup_type="ToFD",
            fd=the_fd,
            arg=arg_as_either,
            move=True,
        )
    elif instruction == RInstruction.R_APPEND_ERR_AND_OUT:
        return SingleArgRedirNode(
            redir_type="AppendErrAndOut",
            fd=("var", to_arg_char(redirectee.filename)),
        )
    else:
        raise ValueError("Invalid redirection instruction")
