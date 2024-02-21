## Development notes

### For loops, case statements, while loops, if statements

These are very similarly represented in bash and dash. Nothing exciting here.

### Simple commands

In Bash, assignments aren't part of the command. In Dash, they are. I'll probably make assignments optional depending on the bash flag. Will this mess up PaSh?

### Select

The select command doesn't exist in dash. A new node is needed.

### Connection

While Dash has separate nodes for each type of connection, Bash has a single node for all of them. Dash stores a bit extra information in the connection node, also they don't have a newline node.

### Functions

Pretty similar, not much to change

### Until

Bash has a single node for until, dash has a while node with a negated test in its representation. Will need to write a function to wrap that.

### Group

I don't see a group node in dash. Actually, it seems like dash just stores a group as the unwrapped group in bash.

### Arithmetic

Bash has a node for arithmetic, dash doesn't. Actually, dash interprets arithmetic as a double subshell.



