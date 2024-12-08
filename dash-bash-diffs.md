# Differences between Dash and Bash frontends

Shasta was designed for libdash, with libbash support added later.
Both `json_to_ast` (for libdash) and `bash_to_shasta_ast` (for libbash) contain `to_ast_node(s)` functions,
which each take a parsed, untyped AST and convert it to a shasta AST as defined in `ast_node`.
Thr transformation is direct; bash is assumed to be a subset of dash. This is not strictly true, since
both have some minor divergences from the POSIX spec, but is good enough.

### The following fields of `AstNodes` are only used for Bash scripts:

- `RedirectionNode` and `*RedirNode`: The `fd` field is either `('var', filename)` or `('fixed', fd)`.
   Dash only uses the latter form; the first exists to support bashisms like `exec {fd} > log.txt`,
   which open the file and assigns `fd` the new file descriptor.
- `FileRedirNode`: 'ReadingString' subtype. Handles here-strings.
- `BackgroundNode`: The `after_ampersand` field. Handles an edge case with heredocs.

The pretty printer uses the various `nobraces` and `semicolon` fields to determine
whether braces and semicolons are printed. In dash, this doesn't matter, but in bash
they can lead to a syntax error. For example:

```bash
( { echo hi; echo bye } )
```

is invalid.

### The following AstNodes are only used for Bash scripts:

- `SelectNode`
- `ArithNode`
- `CondNode`
- `ArithForNode`
- `CoprocNode`
- `TimeNode`
- `SingleArgRedirNode`
- `GroupNode`
