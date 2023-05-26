# shasta

A python library with shell AST definitions for the [libdash](https://github.com/mgree/libdash) AST. It can be used to develop shell AST analyses and transfomations. All AST nodes support a `pretty()` method that extracts them as a shell script, and the library offers a [json_to_ast](./shasta/json_to_ast.py) module that creates an AST object from a JSON object.

It was originally part of [PaSh](https://github.com/binpash/pash) but was separated to allow others to build on it.
