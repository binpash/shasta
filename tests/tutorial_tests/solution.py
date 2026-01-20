#!/usr/bin/env python3
"""
Tutorial solution for shell AST analysis (steps 1-5).

This module demonstrates parsing, walking, unparsing, subshell counting,
and effect-free analysis of shell scripts using shasta.

Adapted from the POPL26 tutorial.
"""

from collections.abc import Iterator

from utils import parse_shell_to_asts, ast_to_code
from shasta.ast_walker import walk_ast, walk_ast_node
from shasta import ast_node as AST


def show_step(step: str, initial_blank=True):
    if initial_blank:
        print()
    print("-" * 80)
    print(f"STEP {step}")
    print("-" * 80)
    print()


##
## Step 1:
##   Parse a script and print its AST.
##
## You need `utils.parse_shell_to_asts` to parse the shell scripts.
##
## Note the structure of the `Parsed` type is a 4-tuple, comprising:
##   - the actual AST
##   - the original parsed text
##   - the starting line number
##   - the ending line number
##
## Look closely at the output to see the various node names.
##


def step1_parse_script(input_script):
    show_step(
        "1: parsing and printing the `Parsed` representation", initial_blank=False
    )

    # set ast to a list of parsed commands using `parse_shell_to_asts`
    ast = list(parse_shell_to_asts(input_script))
    print(ast)

    return ast


##
## Step 2:
##   Use our `walk_ast` visitor to print out every AST node.
##


def step2_walk_print(ast):
    show_step("2: visiting with walk_ast")

    walk_ast(ast, visit=print)


##
## Step 3:
##   Unparse the AST back to shell code
##
## You need `utils.ast_to_code` to unparse the AST.
## You can either call `walk_ast` with an identity visitor or use a comprehension to pull out the parsed AST.
##
## Also note the unparsed AST for its syntactic differences.
##
## Bonus exercise: can you write a script that unparses significantly differently,
##                 beyond just whitespace?
##
## Inspect the syntactic differences of the unparsed and original script
##
def step3_unparse(ast):
    show_step("3: unparse using `ast_to_code`")

    # convert the AST back using `ast_to_code`
    unparsed_code = ast_to_code([node for (node, _, _, _) in ast])
    print(unparsed_code)

    return unparsed_code


##
## Step 4:
##   Create a simple analysis that returns the number of subshells a script will create:
##   Four ways to create a subshell:
##   - Asynchronous commands `&`
##   - Pipes `|`
##   - Subshells `(...)`
##   - Command Substitution `$(...)`
##
## Find a (POSIX) shell script you use frequently (or pull one from binpash/koala) and see how many it creates.
##

class Counter:
    def __init__(self):
        self.cnt = 0

    def add(self, n):
        self.cnt += n

    def get(self):
        return self.cnt

def step4_subshells(ast):
    show_step("4: counting shell features")

    subshells = Counter()
    def count_features(node):
        match node:
            case AST.BackgroundNode():
                subshells.add(1)
            case AST.PipeNode():
                subshells.add(len(node.items))
            case AST.SubshellNode():
                subshells.add(1)
            case AST.BArgChar():
                subshells.add(1)
            case _:
                pass
        return node

    walk_ast(ast, visit=count_features)
    count = subshells.get()
    print("Number of subshells in script:", count)
    return count

##
## Step 5:
##   Identify top-level commands that are effect-free
##
## We say a top-level command is effect-free if executing the command doesn't have side-effects on the shell state.
##
## We'll confine our notion of "shell state" to the variables in the shell, so a top-level command is effect free
## when it does not set or change the values of variables. We can approximate this with the following syntactic restriction:
##
##   - It has no function definitions.
##   - Commands have no assignments in them. (`VAR=VAL cmd` usually won't affect the environment---unless `cmd` is a special builtin, like `set`.)
##   - The `${VAR=WORD}` and `${VAR:=WORD}` parameter formats are never used.
##   - There are no arithmetic expansions.
##
## Tip: if you're not sure what AST nodes correspond to a shell feature, create a custom file with just the code you're interested
## in, and then print the AST (unprettily).
##
##
## This list is not entirely sound---special builtins like `export` and `set` can affect shell state, as can `.` and `eval`.
## But it's a good start, and let's not get bogged down.


def is_effect_free(node):
    if node is None:
        return True

    safe = True
    def check_for_effects(n):
        nonlocal safe
        if not safe:
            return

        match n:
            case AST.DefunNode():
                safe = False
            case AST.CommandNode() if len(n.assignments) > 0:
                safe = False
            case AST.VArgChar() if n.fmt == "Assign":
                safe = False
            case AST.AArgChar():
                safe = False
            case _:
                pass

    walk_ast_node(node, visit=check_for_effects)
    return safe


def step5_effect_free(ast):
    show_step("5: safe-to-expand top-level commands")

    safe = []
    # only look at top-level nodes!
    for node, _, _, _ in ast:
        if is_effect_free(node):
            print(f"- {node.pretty()}")
