from __future__ import annotations

from enum import IntEnum

# We don't need libbash as a dependency since we only use its classes
# to hold already parsed data, but we still need its enums to interpret it.

# Enums are IntEnums so they can be compared with libbash enums by their numeric value,
# since libbash.AnyFlag.ANY != shasta.AnyFlag.ANY


class OFlag(IntEnum):
    """
    represents open flags present in the OpenFlag class
    """

    O_RDONLY = 0
    O_WRONLY = 1 << 0
    O_RDWR = 1 << 1
    O_APPEND = 1 << 3
    O_CREAT = 1 << 9
    O_TRUNC = 1 << 10


class WordDescFlag(IntEnum):
    """
    represents word description flags present in the WordDesc class
    """

    W_HASDOLLAR = 1 << 0  # dollar sign present
    W_QUOTED = 1 << 1  # some form of quote character is present
    W_ASSIGNMENT = 1 << 2  # this word is a variable assignment
    W_SPLITSPACE = 1 << 3  # split this word on " " regardless of IFS
    # do not perform word splitting on this word because IFS is empty string
    W_NOSPLIT = 1 << 4
    W_NOGLOB = 1 << 5  # do not perform globbing on this word
    # don't split word except for $@ expansion (using spaces) because context does not allow it
    W_NOSPLIT2 = 1 << 6
    W_TILDEEXP = 1 << 7  # tilde expand this assignment word
    W_DOLLARAT = 1 << 8  # UNUSED - $@ and its special handling
    W_ARRAYREF = 1 << 9  # word is a valid array reference
    W_NOCOMSUB = 1 << 10  # don't perform command substitution on this word
    W_ASSIGNRHS = 1 << 11  # word is rhs of an assignment statement
    W_NOTILDE = 1 << 12  # don't perform tilde expansion on this word
    W_NOASSNTILDE = 1 << 13  # don't do tilde expansion like an assignment statement
    W_EXPANDRHS = 1 << 14  # expanding word in ${paramOPword}
    W_COMPASSIGN = 1 << 15  # compound assignment
    W_ASSNBLTIN = 1 << 16  # word is a builtin command that takes assignments
    W_ASSIGNARG = 1 << 17  # word is assignment argument to command
    W_HASQUOTEDNULL = 1 << 18  # word contains a quoted null character
    W_DQUOTE = 1 << 19  # UNUSED - word should be treated as if double-quoted
    W_NOPROCSUB = 1 << 20  # don't perform process substitution
    W_SAWQUOTEDNULL = 1 << 21  # word contained a quoted null that was removed
    W_ASSIGNASSOC = 1 << 22  # word looks like associative array assignment
    W_ASSIGNARRAY = 1 << 23  # word looks like a compound indexed array assignment
    W_ARRAYIND = 1 << 24  # word is an array index being expanded
    # word is a global assignment to declare (declare/typeset -g)
    W_ASSNGLOBAL = 1 << 25
    W_NOBRACE = 1 << 26  # don't perform brace expansion
    W_COMPLETE = 1 << 27  # word is being expanded for completion
    W_CHKLOCAL = 1 << 28  # check for local vars on assignment
    # force assignments to be to local variables, non-fatal on assignment errors
    W_FORCELOCAL = 1 << 29


class CommandFlag(IntEnum):
    """
    represents command flags present in several command types
    """

    CMD_WANT_SUBSHELL = 1 << 0  # user wants subshell
    CMD_FORCE_SUBSHELL = 1 << 1  # shell needs to force subshell
    CMD_INVERT_RETURN = 1 << 2  # invert the exit value
    CMD_IGNORE_RETURN = 1 << 3  # ignore the exit value
    CMD_NO_FUNCTIONS = 1 << 4  # ignore functions during command lookup
    CMD_INHIBIT_EXPANSION = 1 << 5  # do not expand command words
    CMD_NO_FORK = 1 << 6  # do not fork, just call execv
    CMD_TIME_PIPELINE = 1 << 7  # time the pipeline
    CMD_TIME_POSIX = 1 << 8  # time -p was specified
    CMD_AMPERSAND = 1 << 9  # command &
    CMD_STDIN_REDIRECTED = 1 << 10  # async command needs implicit </dev/null
    CMD_COMMAND_BUILTIN = 1 << 11  # command executed by 'command' builtin
    CMD_COPROC_SHELL = 1 << 12  # coprocess shell
    CMD_LASTPIPE = 1 << 13  # last command in pipeline
    CMD_STD_PATH = 1 << 14  # use default PATH for command lookup
    CMD_TRY_OPTIMIZING = 1 << 15  # try to optimize simple command


class CommandType(IntEnum):
    """
    a command type enum
    """

    CM_FOR = 0  # for loop
    CM_CASE = 1  # switch case
    CM_WHILE = 2  # while loop
    CM_IF = 3  # if statement
    CM_SIMPLE = 4  # simple command
    CM_SELECT = 5  # select statement
    CM_CONNECTION = 6  # probably connectors like &,||, &&, ;
    CM_FUNCTION_DEF = 7  # function definition
    CM_UNTIL = 8  # until loop
    CM_GROUP = 9  # probably a command grouping via { } or ( )
    CM_ARITH = 10  # arithmetic expression, probably using $(( ))
    CM_COND = 11  # conditional expression, probably using [[ ]]
    CM_ARITH_FOR = 12  # probably for loop using (( ))
    CM_SUBSHELL = 13  # subshell via ( )
    CM_COPROC = 14  # coprocess


class RInstruction(IntEnum):
    """
    a redirection instruction enum
    """

    R_OUTPUT_DIRECTION = 0  # >foo
    R_INPUT_DIRECTION = 1  # <foo
    R_INPUTA_DIRECTION = 2  # foo & makes this -- might not be used
    R_APPENDING_TO = 3  # >>foo
    R_READING_UNTIL = 4  # << foo
    R_READING_STRING = 5  # <<< foo
    R_DUPLICATING_INPUT = 6  # 1<&2
    R_DUPLICATING_OUTPUT = 7  # 1>&2
    R_DEBLANK_READING_UNTIL = 8  # <<-foo
    R_CLOSE_THIS = 9  # <&-
    R_ERR_AND_OUT = 10  # command &>filename
    R_INPUT_OUTPUT = 11  # <>foo
    R_OUTPUT_FORCE = 12  # >| foo
    R_DUPLICATING_INPUT_WORD = 13  # 1<&$foo
    R_DUPLICATING_OUTPUT_WORD = 14  # 1>&$foo
    R_MOVE_INPUT = 15  # 1<&2-
    R_MOVE_OUTPUT = 16  # 1>&2-
    R_MOVE_INPUT_WORD = 17  # 1<&$foo-
    R_MOVE_OUTPUT_WORD = 18  # 1>&$foo-
    R_APPEND_ERR_AND_OUT = 19  # &>> filename


class CondTypeIntEnum(IntEnum):
    """
    a conditional expression type enum
    """

    COND_AND = 1
    COND_OR = 2
    COND_UNARY = 3
    COND_BINARY = 4
    COND_TERM = 5
    COND_EXPR = 6


class ConnectionType(IntEnum):
    """
    a connection type enum - refer to execute_connection in execute_cmd.c
    in the bash source code for more information, pretty funny approach
    to this
    """

    AMPERSAND = 38
    SEMICOLON = 59
    NEWLINE = 10
    PIPE = 124
    AND_AND = 288
    OR_OR = 289


class RedirectFlag(IntEnum):
    """
    a redirect flag enum
    """

    REDIR_VARASSIGN = 1 << 0


class PatternFlag(IntEnum):
    """
    a pattern flag enum, present in the CasePattern class
    """

    CASEPAT_FALLTHROUGH = 1 << 0  # fall through to next pattern
    CASEPAT_TESTNEXT = 1 << 1  # test next pattern
