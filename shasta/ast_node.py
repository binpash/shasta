from __future__ import annotations

import abc
from json import JSONEncoder
from .print_lib import *
from enum import Enum

from typing import TYPE_CHECKING

# Type hinting is only being used for documentation currently.
# To use the type checker in a useful way, you'd have to
# use isinstance instead of string tags for the AstNodes
# (or an equivalent "is_type(*AstNode)" function).
if TYPE_CHECKING:
    from typing import ClassVar, Literal, TypeAlias
    FdType: TypeAlias = tuple[Literal['var'], list["ArgChar"]] | tuple[Literal['fixed'], int]

class AstNode(metaclass=abc.ABCMeta):
    NodeName: ClassVar[str] = 'None'

    @abc.abstractmethod
    def json(self) -> list:
        pass
    
    @abc.abstractmethod
    def pretty(self) -> str:
        """
        Renders an AST back in shell syntax. 
        """
        pass

class BashNode:
    """
        Dummy class to mark whether an AstNode is only for Bash
    """
    pass

class Command(AstNode):
    pass

class CustomJSONEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, AstNode):
            return o.json()
        # Let the base class default method raise the TypeError
        return JSONEncoder.default(self, o)

class PipeNode(Command):
    NodeName = 'Pipe'
    is_background: bool
    items: "list[Command]"

    def __init__(self, is_background, items):
        self.is_background = is_background
        self.items = items

    def __repr__(self):
        if (self.is_background):
            return "Background Pipe: {}".format(self.items)    
        else:
            return "Pipe: {}".format(self.items)
        
    def json(self):
        json_output = make_kv(PipeNode.NodeName,
                              [self.is_background,
                               self.items])
        return json_output

    def pretty(self):
        bg = self.is_background
        ps = self.items

        deferred = None
        if self.items[0].NodeName == "Command" and \
                len([1 for x in self.items[0].redir_list if x.NodeName == "Heredoc"]) > 0:
            deferred = get_deferred_heredocs(self.items[0].redir_list)

        if deferred:
            headers = ' '.join([x.header_pretty() for x in deferred])
            bodies = ' '.join(reversed([x.body_pretty() for x in deferred]))
            return f'{ps[0].pretty(ignore_heredocs=True)} {headers} |\
             {intercalate(" | ", [item.pretty() for item in ps[1:]])}\n{bodies}'
        p = intercalate(" | ", [item.pretty() for item in ps])

        if bg:
            return background(p)
        else:
            return p


class CommandNode(Command):
    NodeName = 'Command'
    line_number: int
    assignments: list
    arguments: "list[list[ArgChar]]"
    redir_list: list

    def __init__(self, line_number, assignments, arguments, redir_list):
        self.line_number = line_number
        self.assignments = assignments
        self.arguments = arguments
        self.redir_list = redir_list

    def __repr__(self):
        output = "Command: {}".format(self.arguments)
        if(len(self.assignments) > 0):
            output += ", ass[{}]".format(self.assignments)
        if(len(self.redir_list) > 0):
            output += ", reds[{}]".format(self.redir_list)
        return output

    def json(self):
        json_output = make_kv(CommandNode.NodeName,
                              [self.line_number,
                               self.assignments,
                               self.arguments,
                               self.redir_list])
        return json_output
    
    def pretty(self, ignore_heredocs=False):
        assigns = self.assignments
        cmds = self.arguments
        redirs = self.redir_list

        str = " ".join([assign.pretty() for assign in assigns])
        if (len(assigns) == 0) or (len(cmds) == 0):
            pass
        else:
            str += " "
        str += separated(string_of_arg, cmds) + string_of_redirs(redirs, ignore_heredocs=ignore_heredocs)

        return str

class SubshellNode(Command):
    NodeName = 'Subshell'
    line_number: int
    body: Command
    redir_list: list # bash stores the redirects elsewhere

    def __init__(self, line_number, body, redir_list):
        self.line_number = line_number
        self.body = body
        self.redir_list = redir_list if redir_list else []

    def json(self):
        json_output = make_kv(SubshellNode.NodeName,
                              [self.line_number,
                               self.body,
                               self.redir_list])
        return json_output
    
    def pretty(self):
        if self.body.NodeName == "Semi":
            return f'( {self.body.pretty(no_braces=True)} )' + string_of_redirs(self.redir_list)
        else:
            return parens(self.body.pretty() + string_of_redirs(self.redir_list))
        
class AndNode(Command):
    NodeName = 'And'
    left_operand: Command
    right_operand: Command
    no_braces: bool

    def __init__(self, left_operand, right_operand, no_braces=False):
        self.left_operand = left_operand
        self.right_operand = right_operand
        self.no_braces = no_braces

    def __repr__(self):
        output = "{} && {}".format(self.left_operand, self.right_operand)
        return output
    
    def json(self):
        json_output = make_kv(AndNode.NodeName,
                              [self.left_operand,
                               self.right_operand])
        return json_output
    
    def pretty(self):
        deferred = None
        if self.left_operand.NodeName == "Command" and \
                len([1 for x in self.left_operand.redir_list if x.NodeName == "Heredoc"]) > 0:
            deferred = get_deferred_heredocs(self.left_operand.redir_list)

        if self.no_braces:
            if deferred:
                headers = ' '.join([x.header_pretty() for x in deferred])
                bodies = ' '.join(reversed([x.body_pretty() for x in deferred]))
                return f'{self.left_operand.pretty(ignore_heredocs=True)} {headers} &&\n{bodies}\
                 {self.right_operand.pretty()}'
            return f'{self.left_operand.pretty()} && {self.right_operand.pretty()}'
        else:
            if deferred:
                headers = ' '.join([x.header_pretty() for x in deferred])
                bodies = ' '.join(reversed([x.body_pretty() for x in deferred]))
                return f'{braces(self.left_operand.pretty(ignore_heredocs=True))} {headers} &&\n{bodies}\
                 {braces(self.right_operand.pretty())}'
            return f'{braces(self.left_operand.pretty())} && {braces(self.right_operand.pretty())}'

class OrNode(Command):
    NodeName = 'Or'
    left_operand: Command
    right_operand: Command
    no_braces: bool

    def __init__(self, left_operand, right_operand, no_braces=False):
        self.left_operand = left_operand
        self.right_operand = right_operand
        self.no_braces = no_braces

    def __repr__(self):
        output = "{} || {}".format(self.left_operand, self.right_operand)
        return output
    
    def json(self):
        json_output = make_kv(OrNode.NodeName,
                              [self.left_operand,
                               self.right_operand])
        return json_output
    
    def pretty(self):
        if self.no_braces:
            return f'{self.left_operand.pretty()} || {self.right_operand.pretty()}'
        else:
            return f'{braces(self.left_operand.pretty())} || {braces(self.right_operand.pretty())}'
    
class SemiNode(Command):
    NodeName = 'Semi'
    left_operand: Command
    right_operand: Command
    semicolon: bool

    def __init__(self, left_operand, right_operand, semicolon=False):
        self.left_operand = left_operand
        self.right_operand = right_operand
        self.semicolon = semicolon

    def __repr__(self):
        output = "{} ; {}".format(self.left_operand, self.right_operand)
        return output
    
    def json(self):
        json_output = make_kv(SemiNode.NodeName,
                              [self.left_operand,
                               self.right_operand])
        return json_output
    
    def pretty(self, no_braces=False):
        l = self.left_operand
        r = self.right_operand
        if not self.semicolon:
            if no_braces:
                return f'{l.pretty(no_braces=True) if l.NodeName == "Semi" else l.pretty()}\n\
                {r.pretty(no_braces=True) if r.NodeName == "Semi" else r.pretty()}'
            else:
                return f'{braces(self.left_operand.pretty())}\n{braces(self.right_operand.pretty())}'
        else:
            return f'{self.left_operand.pretty()} ; {self.right_operand.pretty()}'


class NotNode(Command):
    NodeName = 'Not'
    body: Command
    no_braces: bool

    def __init__(self, body, no_braces=False):
        self.body = body
        self.no_braces = no_braces

    def json(self):
        json_output = make_kv(NotNode.NodeName,
                              self.body)
        return json_output
    
    def pretty(self):
        if self.no_braces:
            return f'! {self.body.pretty()}'
        else:
            return f'! {braces(self.body.pretty())}'

class RedirNode(Command):
    NodeName = 'Redir'
    line_number: int | None # bash has no line number for redir nodes
    node: Command
    redir_list: list

    def __init__(self, line_number, node, redir_list):
        self.line_number = line_number
        self.node = node
        self.redir_list = redir_list

    def json(self):
        json_output = make_kv(RedirNode.NodeName,
                              [self.line_number,
                               self.node,
                               self.redir_list])
        return json_output
    
    def pretty(self):
        return self.node.pretty() + string_of_redirs(self.redir_list)

class BackgroundNode(Command):
    NodeName = 'Background'
    line_number: int | None  # bash has no line number for background nodes
    node: Command
    after_ampersand: Command | None # only used in bash
    redir_list: list
    no_braces: bool

    def __init__(self, line_number, node, redir_list, after_ampersand=None, no_braces=False):
        self.line_number = line_number
        self.node = node
        self.redir_list = redir_list
        self.after_ampersand = after_ampersand
        self.no_braces = no_braces

    def json(self):
        json_output = make_kv(BackgroundNode.NodeName,
                              [self.line_number,
                               self.node,
                               self.redir_list])
        return json_output

    def pretty(self):
        if not self.after_ampersand:
            return background(self.node.pretty() + string_of_redirs(self.redir_list), self.no_braces)
        else:
            # we have to do some deferred heredocs stuff here
            if self.after_ampersand.NodeName == "Background" and self.after_ampersand.after_ampersand:
                return self.node.pretty() + string_of_redirs(self.redir_list) + " " + self.after_ampersand.pretty() \
                    + " &"
            elif self.after_ampersand.NodeName != "Background":
                return self.node.pretty() + string_of_redirs(self.redir_list) + " " + " &" + \
                    self.after_ampersand.pretty()
            else:
                return self.node.pretty() + string_of_redirs(self.redir_list) + " " + self.after_ampersand.pretty()


class DefunNode(Command):
    NodeName = 'Defun'
    line_number: int
    name: list["ArgChar"]
    body: Command
    bash_mode: bool

    def __init__(self, line_number, name, body, bash_mode=False):
        self.line_number = line_number
        self.name = name
        self.body = body
        self.bash_mode = bash_mode

    def json(self):
        json_output = make_kv(DefunNode.NodeName,
                              [self.line_number,
                               self.name,
                               self.body])
        return json_output
    
    def pretty(self):
        name = self.name
        body = self.body
        if body.NodeName == "Group":
            if self.bash_mode:
                return "function " + string_of_arg(name) + " () {\n" + body.pretty(no_braces=True) + "\n}"
            return string_of_arg(name) + " () {\n" + body.pretty(no_braces=True) + "\n}"
        else:
            if self.bash_mode:
                return "function " + string_of_arg(name) + " () {\n" + body.pretty() + "\n}"
            return string_of_arg(name) + " () {\n" + body.pretty() + "\n}"


class ForNode(Command):
    NodeName = 'For'
    line_number: int
    argument: "list[list[ArgChar]]"
    body: Command
    variable: "list[ArgChar]"

    def __init__(self, line_number, argument, body, variable):
        self.line_number = line_number
        self.argument = argument
        self.body = body
        self.variable = variable

    def __repr__(self):
        output = "for {} in {}; do ({})".format(self.variable, self.argument, self.body)
        return output
    
    def json(self):
        json_output = make_kv(ForNode.NodeName,
                              [self.line_number,
                               self.argument,
                               self.body,
                               self.variable])
        return json_output

    def pretty(self):
        a = self.argument
        body = self.body
        var = self.variable
        return f'for {string_of_arg(var)} in {separated(string_of_arg, a)}; \n do \
        {body.pretty(no_braces=True) if body.NodeName == "Semi" else body.pretty()}\ndone'

class WhileNode(Command):
    NodeName = 'While'
    test: Command
    body: Command

    def __init__(self, test, body):
        self.test = test
        self.body = body

    def json(self):
        json_output = make_kv(WhileNode.NodeName,
                              [self.test,
                               self.body])
        return json_output

    def pretty(self):
        first = self.test
        b = self.body
        
        if isinstance(first, NotNode):
            t = first.body
            return f'until {t.pretty(no_braces=True) if t.NodeName == "Semi" else t.pretty()}; do \
            {b.pretty(no_braces=True) if b.NodeName == "Semi" else b.pretty()}; done '
        else:
            t = first
            return f'while {t.pretty(no_braces=True) if t.NodeName == "Semi" else t.pretty()}; do \
            {b.pretty(no_braces=True) if b.NodeName == "Semi" else b.pretty()}; done '

class IfNode(Command):
    NodeName = 'If'
    cond: Command
    then_b: Command
    else_b: Command | None

    def __init__(self, cond, then_b, else_b):
        self.cond = cond
        self.then_b = then_b
        self.else_b = else_b

    def json(self):
        json_output = make_kv(IfNode.NodeName,
                              [self.cond,
                               self.then_b,
                               self.else_b])
        return json_output

    def pretty(self):
        c = self.cond
        t = self.then_b
        e = self.else_b
        str1 = f'if {c.pretty(no_braces=True) if c.NodeName == "Semi" else c.pretty()}\
        ; then {t.pretty(no_braces=True) if t.NodeName == "Semi" else t.pretty()}'

        if not e or is_empty_cmd(e):
            str1 += "; fi"
        elif isinstance(e, IfNode):
            str1 += "; el" + (e.pretty(no_braces=True) if e.NodeName == "Semi" else e.pretty())
        else:
            str1 += f'; else {e.pretty(no_braces=True) if e.NodeName == "Semi" else e.pretty()}; fi'

        return str1

class CaseNode(Command):
    NodeName = 'Case'
    line_number: int
    argument: "list[ArgChar]"
    cases: list

    def __init__(self, line_number, argument, cases):
        self.line_number = line_number
        self.argument = argument
        self.cases = cases

    def json(self):
        json_output = make_kv(CaseNode.NodeName,
                              [self.line_number,
                               self.argument,
                               self.cases])
        return json_output
    
    def pretty(self):
        a = self.argument
        cs = self.cases
        return f'case {string_of_arg(a)} in {separated(string_of_case, cs)} esac'


class ArgChar(AstNode):
    ## This method formats an arg_char to a string to
    ## the best of its ability
    def format(self) -> str:
        raise NotImplementedError

class CArgChar(ArgChar):
    NodeName = 'C'
    char: int
    # Hack:
    # We're using CArgChars to represent all bash characters in shasta
    # because we haven't reimplemented the expansion code. This means that
    # no CArgChars can be escaped in bash, since they could be special characters.
    bash_mode: bool

    def __init__(self, char: int, bash_mode: bool = False):
        self.char = char
        self.bash_mode = bash_mode

    def __repr__(self):
        return self.format()
    
    def format(self) -> str:
        return str(chr(self.char))

    def json(self):
        json_output = make_kv(CArgChar.NodeName,
                              self.char)
        return json_output
    
    def pretty(self, quote_mode=UNQUOTED):
        if quote_mode==QUOTED and chr(self.char) == '"':
            return '\\"'
        else:
            return chr(self.char)

class EArgChar(ArgChar):
    NodeName = 'E'
    char: int
    # currently unused
    # internal: bool  # bash specific, specify that the character was escaped internally rather than by the user

    def __init__(self, char: int):
        self.char = char

    ## TODO: Implement
    def __repr__(self):
        return f'\\{chr(self.char)}'

    def format(self) -> str:
        ## TODO: This is not right. I think the main reason for the
        ## problems is the differences between bash and the posix
        ## standard.
        non_escape_chars = [92, # \
                            61, # =
                            91, # [
                            93, # ]
                            45, # -
                            58, # :
                            126,# ~
                            42] # *
        if(self.char in non_escape_chars):
            return '{}'.format(chr(self.char))
        else:
            return '{}'.format(chr(self.char))

    def json(self):
        json_output = make_kv(EArgChar.NodeName,
                              self.char)
        return json_output
    
    def pretty(self, quote_mode=UNQUOTED):
        param = self.char
        char = chr(param)

        ## MMG 2021-09-20 It might be safe to move everything except for " in the second list, but no need to do it if the tests pass
        ## '!' dropped for bash non-interactive bash compatibility
        ## Chars to escape unconditionally
        chars_to_escape = ["'", '"', '`', '(', ')', '{', '}', '$', '&', '|', ';']
        ## Chars to escape only when not quoted
        chars_to_escape_when_no_quotes = ['*', '?', '[', ']', '#', '<', '>', '~', ' ']
        if char in chars_to_escape:
            return '\\' + char
        elif char in chars_to_escape_when_no_quotes and quote_mode==UNQUOTED:
            return '\\' + char
        else:
            return escaped(param)


class TArgChar(ArgChar):
    NodeName = 'T'
    string: str

    def __init__(self, string: str):
        self.string = string

    ## TODO: Implement
    # def __repr__(self):
    #     return f''

    def json(self):
        json_output = make_kv(TArgChar.NodeName,
                              self.string)
        return json_output

    def pretty(self, quote_mode=UNQUOTED):
        param = self.string
        ## TODO: Debug this
        if param == "None":
            return "~"
        elif len(param) == 2:
            if param[0] == "Some":
                (_, u) = param

                return "~" + u
            else:
                assert(False)
        else:
            print ("Unexpected param for T: %s" % param)
            assert(False)

class AArgChar(ArgChar):
    NodeName = 'A'
    arg: "list[ArgChar]"

    def __init__(self, arg: "list[ArgChar]"):
        self.arg = arg

    ## TODO: Implement
    # def __repr__(self):
    #     return f''

    def json(self):
        json_output = make_kv(AArgChar.NodeName,
                              self.arg)
        return json_output
    
    def pretty(self, quote_mode=UNQUOTED):
        param = self.arg
        return f'$(({string_of_arg(param, quote_mode)}))'

class VArgChar(ArgChar):
    NodeName = 'V'
    fmt: object
    null: bool
    var: str
    arg: "list[ArgChar]"

    def __init__(self, fmt, null: bool, var: str, arg: "list[ArgChar]"):
        self.fmt = fmt
        self.null = null
        self.var = var
        self.arg = arg

    def __repr__(self):
        return f'V({self.fmt},{self.null},{self.var},{self.arg})'

    def format(self) -> str:
        return '${{{}}}'.format(self.var)

    def json(self):
        json_output = make_kv(VArgChar.NodeName,
                              [self.fmt,
                               self.null,
                               self.var,
                               self.arg])
        return json_output
    
    def pretty(self, quote_mode=UNQUOTED):
        vt = self.fmt
        nul = self.null
        name = self.var
        a = self.arg
        if vt == "Length":
            return "${#" + name + "}"
        else:
            stri = "${" + name

            # Depending on who generated the JSON, nul may be
            # a string or a boolean! In Python, non-empty strings
            # to True.
            if (str(nul).lower() == "true"):
                stri += ":"
            elif (str (nul).lower() == "false"):
                pass
            else:
                assert(False)

            stri += string_of_var_type(vt) + string_of_arg(a, quote_mode) + "}"

            return stri


class QArgChar(ArgChar):
    NodeName = 'Q'
    arg: "list[ArgChar]"

    def __init__(self, arg: "list[ArgChar]"):
        self.arg = arg

    def __repr__(self):
        return f'Q({self.arg})'
    
    def format(self) -> str:
        chars = [arg_char.format() for arg_char in self.arg]
        joined_chars = "".join(chars)
        return '"{}"'.format(joined_chars)

    def json(self):
        json_output = make_kv(QArgChar.NodeName,
                              self.arg)
        return json_output

    def pretty(self, quote_mode=UNQUOTED):
        param = self.arg
        return "\"" + string_of_arg(param, quote_mode=QUOTED) + "\""


class BArgChar(ArgChar):
    NodeName = 'B'
    node: Command

    def __init__(self, node: Command):
        self.node = node

    ## TODO: Implement
    # def __repr__(self):
    #     return f''

    def format(self) -> str:
        return '$({})'.format(self.node)

    def json(self):
        json_output = make_kv(BArgChar.NodeName,
                              self.node)
        return json_output
    
    def pretty(self, quote_mode=UNQUOTED):
        param = self.node
        body = param.pretty()
        # to handle $( () )
        try:
            if body[0] == "(" and body[-1] == ")":
                body = f" {body} "
        except IndexError:
            pass
        return "$(" + body + ")"

class AssignNode(AstNode):
    var: str
    val: "list[ArgChar]"

    def __init__(self, var: str, val):
        self.var = var
        self.val = val

    # TODO: Implement
    def __repr__(self):
        return f'{self.var}={self.val}'

    def json(self):
        json_output = [self.var, self.val]
        return json_output
    
    def pretty(self):
        return f'{self.var}={string_of_arg(self.val)}'

    
class RedirectionNode(AstNode):
    redir_type: str
    fd: FdType # either ('var', filename) or ('fixed', fd)
    pass

class FileRedirNode(RedirectionNode):
    NodeName = "File"
    redir_type: str
    fd: FdType # either ('var', filename) or ('fixed', fd)
    arg: "list[ArgChar]"

    def __init__(self, redir_type, fd, arg):
        self.redir_type = redir_type
        self.fd = fd
        self.arg = arg

    # TODO: Implement
    # def __repr__(self):
    #     return f''

    def json(self):
        json_output = make_kv(FileRedirNode.NodeName,
                              [self.redir_type,
                               self.fd,
                               self.arg])
        return json_output
    
    def pretty(self):
        subtype = self.redir_type
        a = self.arg
        checkVarAssignOut = handle_redirvarassign(self.fd, 1)
        checkVarAssignIn = handle_redirvarassign(self.fd, 0)
        if subtype == "To":
            return checkVarAssignOut + "> " + string_of_arg(a)
        elif subtype == "Clobber":
            return checkVarAssignOut + ">| " + string_of_arg(a)
        elif subtype == "From":
            return checkVarAssignIn + "< " + string_of_arg(a)
        elif subtype == "FromTo":
            return checkVarAssignIn + "<> " + string_of_arg(a)
        elif subtype == "Append":
            return checkVarAssignOut + ">> " + string_of_arg(a)
        elif subtype == "ReadingString":
            # bash specific
            return checkVarAssignIn + "<<< " + string_of_arg(a)
        assert(False)


class DupRedirNode(RedirectionNode):
    NodeName = "Dup"
    dup_type: str
    fd: FdType # either ('var', filename) or ('fixed', fd)
    arg: FdType # either ('var', filename) or ('fixed', fd)
    move: bool

    def __init__(self,
                 dup_type,
                 fd,
                 arg,
                 move=False):
        self.dup_type = dup_type
        self.fd = fd
        self.arg = arg
        self.move = move

    # TODO: Implement
    # def __repr__(self):
    #     return f''

    def json(self):
        json_output = make_kv(DupRedirNode.NodeName,
                              [self.dup_type,
                               self.fd,
                               self.arg,
                               self.move])
        return json_output
    
    def pretty(self):
        subtype = self.dup_type
        fd = self.fd
        tgt = self.arg
        return_str = None
        if tgt[0] == "var":
            len(tgt[1]) # this acts as an assertion of sorts that this is a list of ArgChar
            if subtype == "ToFD":
                return_str = handle_redirvarassign(self.fd, 1) + ">&" + string_of_arg(tgt[1])
            elif subtype == "FromFD":
                return_str = handle_redirvarassign(self.fd, 0) + "<&" + string_of_arg(tgt[1])
        # this is bash specific
        elif tgt[0] == "fixed":
            if subtype == "ToFD":
                return_str = handle_redirvarassign(self.fd, 1) + f">&{tgt[1]}"
            elif subtype == "FromFD":
                return_str = handle_redirvarassign(self.fd, 0) + f"<&{tgt[1]}"
        else:
            raise ValueError("Invalid redirection target")

        if self.move:
            return return_str + "-"
        else:
            return return_str

    
class HeredocRedirNode(RedirectionNode):
    NodeName = "Heredoc"
    heredoc_type: str
    fd: FdType  # either ('var', filename) or ('fixed', fd)
    arg: "list[ArgChar]"
    kill_leading: bool
    eof: str | None

    def __init__(self, heredoc_type, fd, arg, kill_leading=False, eof=None):
        self.heredoc_type = heredoc_type
        self.fd = fd
        self.arg = arg
        self.kill_leading = kill_leading
        self.eof = eof

    # TODO: Implement
    # def __repr__(self):
    #     return f''

    def json(self):
        json_output = make_kv(HeredocRedirNode.NodeName,
                              [self.heredoc_type,
                               self.fd,
                               self.arg,
                               self.eof])
        return json_output


    def header_pretty(self):
        t = self.heredoc_type
        fd = self.fd
        a = self.arg
        heredoc = string_of_arg(a, quote_mode=HEREDOC)
        marker = fresh_marker0(heredoc) if not self.eof else self.eof

        stri = handle_redirvarassign(fd, 0) + "<<" + ("-" if self.kill_leading else "")
        if t == "XHere":
            stri += marker
        else:
            stri += "'" + marker + "'"

        return stri

    def body_pretty(self):
        a = self.arg
        heredoc = string_of_arg(a, quote_mode=HEREDOC)
        marker = fresh_marker0(heredoc) if not self.eof else self.eof

        return heredoc + marker + "\n"
    
    def pretty(self):
        t = self.heredoc_type
        fd = self.fd
        a = self.arg
        heredoc = string_of_arg(a, quote_mode=HEREDOC)
        marker = fresh_marker0(heredoc)

        stri = handle_redirvarassign(fd, 0) + "<<" + ("-" if self.kill_leading else "")
        if t == "XHere":
            stri += marker
        else:
            stri += "'" + marker + "'"

        stri += "\n" + heredoc + marker + "\n"

        return stri

## This function takes an object that contains a mix of untyped and typed AstNodes (yuck) 
## and turns it into untyped json-like object. It is required atm because the infrastructure that
## we have does not translate everything to its typed form at once before compiling, and therefore
## we end up with these abomination objects.
##
## Very important TODO: 
##    We need to fix this by properly defining types (based on `compiler/parser/ast_atd.atd`)
##    and creating a bidirectional transformation from these types to the untyped json object.
##    Then we can have all ast_to_ir infrastructure work on these objects, and only in the end
##    requiring to go to the untyped form to interface with printing and parsing 
##    (which ATM does not interface with the typed form).
def ast_node_to_untyped_deep(node):
    if(isinstance(node, AstNode)):
        json_key, json_val = node.json()
        return [json_key, ast_node_to_untyped_deep(json_val)]
    elif(isinstance(node, list)):
        return [ast_node_to_untyped_deep(obj) for obj in node]
    elif(isinstance(node, tuple)):
        return [ast_node_to_untyped_deep(obj) for obj in node]
    elif(isinstance(node, dict)):
        return {k: ast_node_to_untyped_deep(v) for k, v in node.items()}
    else:
        return node

def make_typed_semi_sequence(asts: "list[AstNode]") -> SemiNode:
    assert(len(asts) > 0)

    if(len(asts) == 1):
        return asts[0]
    else:
        acc = asts[-1]
        ## Remove the last ast
        iter_asts = asts[:-1]
        for ast in iter_asts[::-1]:
            acc = SemiNode(ast, acc)
        return acc

## This has to be here and not in print_lib to avoid circular dependencies
def string_of_arg(args, quote_mode=UNQUOTED):
    i = 0
    text = []
    while i < len(args):
        c = args[i].pretty(quote_mode=quote_mode)
        # escape dollar signs to avoid variable interpolation
        if isinstance(args[i], CArgChar) and not args[i].bash_mode and c == "$" and i + 1 < len(args):
            c = "\\$"
        if c == "$" and not isinstance(args[i], CArgChar):
            raise RuntimeError(f"{c}, {type(c)}")
        text.append(c)

        i = i+1
    
    text = "".join(text)

    return text

def string_of_case(c):
    pats = map(string_of_arg, c["cpattern"])
    body = c["cbody"].pretty() if c["cbody"] else ""
    body = c["cbody"].pretty(no_braces=True) if (body and c["cbody"].NodeName == "Semi") else body
    delim = ";&" if c.get("fallthrough") else ";;"

    return f'{"(" if string_of_arg(c["cpattern"][0]) == "esac" else ""}{intercalate("|", pats)}) {body}{delim}'


def is_empty_cmd(e: Command):
    return isinstance(e, CommandNode) \
        and e.line_number == -1 \
        and len(e.assignments) == 0 \
        and len(e.arguments) == 0 \
        and len(e.redir_list) == 0


## Implements a pattern-matching style traversal over the AST
def ast_match(ast_node, cases, *args):
    return cases[type(ast_node).NodeName](*args)(ast_node)

## Util function
def make_kv(key, val) -> list:
    return [key, val]


##### BASH SPECIFIC NODES #####

class SelectNode(Command, BashNode):
    NodeName = 'Select'
    line_number: int
    variable: list[ArgChar]
    body: Command
    map_list: list[list[ArgChar]]

    def __init__(self, line_number, variable, body, map_list):
        self.line_number = line_number
        self.variable = variable
        self.body = body
        self.map_list = map_list

    def __repr__(self):
        output = "select {} in {};do;{};done".format(self.variable, self.map_list, self.body)
        return output

    def json(self):
        json_output = make_kv(SelectNode.NodeName,
                              [self.line_number,
                               self.variable,
                               self.body,
                               self.map_list])
        return json_output

    def pretty(self):
        var = self.variable
        ml = self.map_list
        b = self.body
        return f'select {string_of_arg(var)} in {separated(string_of_arg, ml)};\ndo\n{b.pretty()}\ndone'


class ArithNode(Command, BashNode):
    NodeName = 'Arith'
    line_number: int
    body: "list[list[ArgChar]]"

    def __init__(self, line_number, body):
        self.line_number = line_number
        self.body = body

    def __repr__(self):
        output = "Arith: {}".format(self.body)
        return output

    def json(self):
        json_output = make_kv(ArithNode.NodeName,
                              [self.line_number,
                               self.body])
        return json_output

    def pretty(self):
        return "((" + ' '.join([string_of_arg(x) for x in self.body]) + "))"

class CondType(Enum):
    COND_AND = 1
    COND_OR = 2
    COND_UNARY = 3
    COND_BINARY = 4
    COND_TERM = 5
    COND_EXPR = 6

class CondNode(Command, BashNode):
    NodeName = 'Cond'
    line_number: int
    cond_type: CondType
    op: list[ArgChar] | None
    left: Command | None
    right: Command | None
    invert_return: bool

    def __init__(self, line_number, cond_type, op, left, right, invert_return):
        self.line_number = line_number
        self.cond_type = cond_type
        self.op = op
        self.left = left
        self.right = right
        self.invert_return = invert_return

    def __repr__(self):
        output = "Cond: type: {}".format(self.op)
        output += ", op: {}".format(self.op)
        output += ", left: {}".format(self.left)
        output += ", right: {}".format(self.right)
        output += ", invert_return: {}".format(self.invert_return)
        return output

    def json(self):
        json_output = make_kv(CondNode.NodeName,
                              [self.line_number,
                               self.cond_type,
                               self.op,
                               self.left,
                               self.right,
                               self.invert_return])
        return json_output

    def pretty(self, with_brackets=True):
        t = self.cond_type
        o = self.op
        l = self.left
        r = self.right
        result = "[[ " if with_brackets else ""
        if self.invert_return:
            result += "! "
        if t == CondType.COND_EXPR.value:
            result += "( " + l.pretty(with_brackets=False) + " )"
        elif t == CondType.COND_AND.value:
            result += l.pretty(with_brackets=False) + " && " + r.pretty(with_brackets=False)
        elif t == CondType.COND_OR.value:
            result += l.pretty(with_brackets=False) + " || " + r.pretty(with_brackets=False)
        elif t == CondType.COND_UNARY.value:
            result += string_of_arg(o) + " " + l.pretty(with_brackets=False)
        elif t == CondType.COND_BINARY.value:
            result += l.pretty(with_brackets=False) + " " + string_of_arg(o) + " " + r.pretty(with_brackets=False)
        elif t == CondType.COND_TERM.value:
            result += string_of_arg(o)
        else:
            raise ValueError("Invalid cond type")

        result += (" ]]" if with_brackets else "")
        return result


class ArithForNode(Command, BashNode):
    NodeName = 'ArithFor'
    line_number: int
    init: "list[list[ArgChar]]"
    cond: "list[list[ArgChar]]"
    step: "list[list[ArgChar]]"
    action: Command

    def __init__(self, line_number, init, cond, step, action):
        self.line_number = line_number
        self.init = init
        self.cond = cond
        self.step = step
        self.action = action

    def __repr__(self):
        output = "ArithFor: init: {}".format(self.init)
        output += ", cond: {}".format(self.cond)
        output += ", step: {}".format(self.step)
        output += ", action: {}".format(self.action)
        return output

    def json(self):
        json_output = make_kv(ArithForNode.NodeName,
                              [self.line_number,
                               self.init,
                               self.cond,
                               self.step,
                               self.action])
        return json_output

    def pretty(self):
        i = self.init
        c = self.cond
        s = self.step
        a = self.action
        return f'for (({separated(string_of_arg,i)}; {separated(string_of_arg,c)}; {separated(string_of_arg, s)})); \
        do {a.pretty(no_braces=True) if a.NodeName == "Semi" else a.pretty()}; done'


class CoprocNode(Command, BashNode):
    NodeName = 'Coproc'
    name: list[ArgChar]
    body: Command

    def __init__(self, name, body):
        self.name = name
        self.body = body

    def __repr__(self):
        output = "Coproc: {}".format(self.name)
        output += ", body: {}".format(self.body)
        return output

    def json(self):
        json_output = make_kv(CoprocNode.NodeName,
                              [self.name,
                               self.body])
        return json_output

    def pretty(self):
        n = self.name
        b = self.body
        if self.body.NodeName != "Command":
            return f'coproc {string_of_arg(n)} {b.pretty()}'
        else:
            return f'coproc {b.pretty()}'

class TimeNode(Command, BashNode):
    NodeName = 'Time'
    time_posix: bool
    command: Command

    def __init__(self, time_posix, command):
        self.time_posix = time_posix
        self.command = command

    def __repr__(self):
        output = "TimeNode:"
        if self.time_posix:
            output += "posix "
        output += ", command: {}".format(self.command)
        return output

    def json(self):
        json_output = make_kv(TimeNode.NodeName,
                              [self.time_posix,
                               self.command])
        return json_output


    def pretty(self):
        c = self.command
        if self.time_posix:
            return f'time -p {c.pretty()}'
        else:
            return f'time {c.pretty()}'


class SingleArgRedirNode(RedirectionNode, BashNode):
    NodeName = "SingleArg"
    redir_type: str
    fd: FdType # Either ('var', filename) or ('fixed', fd)
    arg: None

    def __init__(self, redir_type, fd):
        self.redir_type = redir_type
        self.fd = fd
        self.arg = None

    # TODO: Implement
    # def __repr__(self):
    #     return f''

    def json(self):
        json_output = make_kv(FileRedirNode.NodeName,
                              [self.redir_type,
                               self.fd])
        return json_output

    def pretty(self):
        subtype = self.redir_type
        item = self.fd
        if subtype == "CloseThis":
            return handle_redirvarassign(item) + ">&-"
        elif subtype == "ErrAndOut":
            assert item[0] == 'var'
            return f"&> {string_of_arg(item[1])}"
        elif subtype == "AppendErrAndOut":
            assert item[0] == 'var'
            return f"&>> {string_of_arg(item[1])}"
        assert False


def handle_redirvarassign(item: FdType, showFdUnless: int | None = None) -> str:
    if item[0] == 'var':
        return "{" + string_of_arg(item[1]) + "}"
    else:
        return show_unless(showFdUnless, item[1]) if showFdUnless else str(item[1])

class GroupNode(AstNode, BashNode):
    NodeName = 'Group'
    body: Command
    # TODO: Support redirections
    # redirections: list

    def __init__(self, body):
        self.body = body

    def __repr__(self):
        return f'Group({self.body})'

    def json(self):
        json_output = make_kv(GroupNode.NodeName,
                              self.body)
        return json_output

    def pretty(self, no_braces=False):
        deferred_heredocs = False
        if self.body.NodeName == "Command":
            deferred_heredocs = len(get_deferred_heredocs(self.body.redir_list)) > 0
        if no_braces:
            if self.body.NodeName == "Semi":
                return self.body.pretty(no_braces=True)
            else:
                return self.body.pretty()
        else:
            if self.body.NodeName == "Semi":
                return "{ " + self.body.pretty(no_braces=True) + "; }"
            elif (self.body.NodeName == "Background" and not self.body.after_ampersand) or deferred_heredocs:
                return "{ " + self.body.pretty() + " }"
            else:
                return "{ " + self.body.pretty() + "; }"
