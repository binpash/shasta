from typing import Iterable, Iterator

import libdash
from shasta import json_to_ast
from shasta import ast_node as AST

# Parses straight a shell script to an AST
# through python bindings to dash
# without calling dash as an executable
INITIALIZE_LIBDASH = True
type Parsed = tuple[AST.AstNode, str | None, int, int]

def parse_shell_to_asts(input_script_path: str) -> Iterator[Parsed]:
    global INITIALIZE_LIBDASH
    new_ast_objects = libdash.parser.parse(input_script_path, init=INITIALIZE_LIBDASH)
    INITIALIZE_LIBDASH = False
    # Transform the untyped ast objects to typed ones
    for (
        untyped_ast,
        original_text,
        linno_before,
        linno_after,
    ) in new_ast_objects:
        typed_ast = json_to_ast.to_ast_node(untyped_ast)
        yield (typed_ast, original_text, linno_before, linno_after)


def ast_to_code(ast: Iterable[AST.AstNode]) -> str:
    """
    Turns an AST into a single, pretty-printed valid shell script (as a `str`).

    (Not the most memory efficient, but now we can print it for debugging and
    also write it to a file.)

    :param ast: Description
    """
    return "\n".join([node.pretty() for node in ast]) # REPLACE return # FILL IN HERE with each node in `ast` pretty-printed, compiled into a single newline-separated string


##
## Auxiliary functions for ASTs
##


def string_to_argchars(text: str) -> list[AST.ArgChar]:
    return [AST.CArgChar(ord(ch)) for ch in text]

