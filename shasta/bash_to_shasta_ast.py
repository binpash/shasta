
from .ast_node import *
from libbash.bash_command import *

def to_ast_nodes(node_list: list[Command]) -> list[AstNode]:
    return [to_ast_node(node) for node in node_list]

def to_ast_node(node: Command) -> AstNode:
    node_type = node.type

    if node_type == CommandType.CM_FOR:
        return to_for_node(node.value.for_com)
    elif node_type == CommandType.CM_CASE:
        return to_case_node(node.value.case_com)
    elif node_type == CommandType.CM_WHILE:
        return to_while_node(node.value.while_com)
    elif node_type == CommandType.CM_IF:
        return to_if_node(node.value.if_com)
    elif node_type == CommandType.CM_SIMPLE:
        return to_command_node(node.value.simple_com)
    elif node_type == CommandType.CM_SELECT:
        return to_select_node(node.value.select_com)
    elif node_type == CommandType.CM_CONNECTION:
        return to_connection_node(node.value.connection)
    elif node_type == CommandType.CM_FUNCTION_DEF:
        return to_function_def_node(node)
    elif node_type == CommandType.CM_UNTIL:
        return to_until_node(node.value.until_com)
    elif node_type == CommandType.CM_GROUP:
        # TODO - dash doesn't have a group command, is it as easy as just unwrapping the group?
        pass
    elif node_type == CommandType.CM_ARITH:
        # TODO - dash doesn't have an arithmetic command, will need to make new node.
        pass
    elif node_type == CommandType.CM_COND:
        # TODO PICKUP HERE
        pass
    elif node_type == CommandType.CM_ARITH_FOR:
        pass
    elif node_type == CommandType.CM_SUBSHELL:
        pass
    elif node_type == CommandType.CM_COPROC:
        pass
    else:
        raise ValueError("Invalid node type")


def to_for_node(node: ForCom) -> ForNode:
    line_number = node.line
    action = node.action
    variable = node.name
    map_list = node.map_list
    return ForNode(
        line_number=line_number,
        argument=to_args(map_list),
        body=to_ast_node(action),
        variable=variable)

def to_case_node(node: CaseCom) -> CaseNode:
    line_number = node.line
    argument = node.word
    cases = node.clauses
    return CaseNode(
        line_number=line_number,
        argument=to_arg_char(argument),
        cases=to_case_list(cases))

def to_while_node(node: WhileCom) -> WhileNode:
    test = node.test
    body = node.action
    return WhileNode(
        test=to_ast_node(test),
        body=to_ast_node(body))

def to_if_node(node: IfCom) -> IfNode:
    cond = node.test
    then_b = node.true_case
    else_b = node.false_case
    return IfNode(
        cond=to_ast_node(cond),
        then_b=to_ast_node(then_b),
        else_b=to_ast_node(else_b))

def to_command_node(node: SimpleCom) -> CommandNode:
    line_number = node.line
    arguments = node.words
    redirs = node.redirects
    return CommandNode(
        line_number=line_number,
        assignments=None, # TODO - simple commands in bash don't have assignments ...
        arguments=to_args(arguments),
        redir_list=to_redirs(redirs))

def to_select_node(node: SelectCom) -> SelectNode:
    line_number = node.line
    action = node.action
    variable = node.name
    map_list = node.map_list
    return SelectNode(
        line_number=line_number,
        body=to_ast_node(action),
        variable=variable,
        map_list=to_args(map_list))

def to_function_def_node(node: Command) -> DefunNode:
    line_number = node.value.function_def.line
    name = node.value.function_def.name
    body = node.value.function_def.command
    source_file = node.value.function_def.source_file  # TODO - dash doesn't have source file, will this be important ...
    return DefunNode(
        line_number=line_number,
        name=name,
        body=to_ast_node(body))

def to_connection_node(node: Connection) -> Union[BackgroundNode, SemiNode, PipeNode, AndNode, OrNode]:
    conn_type = node.connector
    left = node.first
    right = node.second
    if conn_type == ConnectionType.AMPERSAND:
        return BackgroundNode(
            line_number=None,  # TODO - bash doesn't store line numbers here, assuming that doesn't really matter
            node=to_ast_node(left),
            redir_list=None)  # TODO - bash doesn't store redirection for connections, that might matter, but maybe
        # we should pull from top level node. Need to figure out if that's right
    elif conn_type == ConnectionType.SEMICOLON:
        return SemiNode(
            left_operand=to_ast_node(left),
            right_operand=to_ast_node(right))
    elif conn_type == ConnectionType.PIPE:
        return PipeNode(
            is_background=None,  # TODO - bash doesn't store background status here, assuming that doesn't really matter
            items=[to_ast_node(left),
                   to_ast_node(right)])  # TODO should I recursively disect the right side into a longer list?
    elif conn_type == ConnectionType.AND_AND:
        return AndNode(
            left_operand=to_ast_node(left),
            right_operand=to_ast_node(right))
    elif conn_type == ConnectionType.OR_OR:
        return OrNode(
            left_operand=to_ast_node(left),
            right_operand=to_ast_node(right))
    elif conn_type == ConnectionType.NEWLINE:
        pass  # TODO - dash doesn't have a newline connection, what even is this?
    else:
        raise ValueError("Invalid connection type")

def to_until_node(node: None) -> None:
    # TODO - wrap until in a while node with a not node
    pass

def to_group_node(node: GroupCom) -> None:
    # TODO - dash doesn't have a group command, is it as easy as just unwrapping the group?
    pass

def to_arith_node(node: ArithCom) -> None:
    # TODO - dash doesn't have an arithmetic command, will need to make new node.
    pass

def to_cond_node(node: CondCom) -> None:
    # TODO PICKUP HERE
    pass

def to_arith_for_node(node: ArithForCom) -> None:
    # TODO
    pass

def to_subshell_node(node: SubshellCom) -> None:
    # TODO
    pass

def to_coproc_node(node: CoprocCom) -> None:
    # TODO
    pass



def to_arg_char(word: WordDesc) -> list[ArgChar]:
    # TODO
    pass


def to_args(words: list[WordDesc]) -> list[list[ArgChar]]:
    return [to_arg_char(word) for word in words]

def to_case_list(cases: list[Pattern]) -> list[dict]:
    return [
        {'cpattern': to_args(case.patterns),
         'cbody': to_ast_node(case.action)}
        for case in cases
    ]

def to_redirs(redirs: list[Redirect]) -> list[RedirectionNode]:
    return [to_redir(redir) for redir in redirs]

def to_redir(redir: Redirect) -> RedirectionNode:
    # TODO
    pass