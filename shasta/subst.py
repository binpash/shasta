from __future__ import annotations

from .ast_node import ArgChar, CArgChar

from math import log
from .flags import WordDescFlag

CTLESC = int.from_bytes(b"\x01", byteorder="big")  # octal 1
CTLNUL = int.from_bytes(b"\x7f", byteorder="big")  # octal 177
NULL = 0

OPEN_BRACE = int.from_bytes(b"{", byteorder="big")
CLOSE_BRACE = int.from_bytes(b"}", byteorder="big")
COMMA = int.from_bytes(b",", byteorder="big")
SINGLE_QUOTE = int.from_bytes(b"'", byteorder="big")
DOUBLE_QUOTE = int.from_bytes(b'"', byteorder="big")
TILDE = int.from_bytes(b"~", byteorder="big")
SLASH = int.from_bytes(b"/", byteorder="big")
BACK_SLASH = int.from_bytes(b"\\", byteorder="big")
DOLLAR = int.from_bytes(b"$", byteorder="big")
AT = int.from_bytes(b"@", byteorder="big")
LESS_THAN = int.from_bytes(b"<", byteorder="big")
GREATER_THAN = int.from_bytes(b">", byteorder="big")
LEFT_PAREN = int.from_bytes(b"(", byteorder="big")
RIGHT_PAREN = int.from_bytes(b")", byteorder="big")
OPEN_BRACKET = int.from_bytes(b"[", byteorder="big")
CLOSE_BRACKET = int.from_bytes(b"]", byteorder="big")
EQUALS = int.from_bytes(b"=", byteorder="big")
BACK_QUOTE = int.from_bytes(b"`", byteorder="big")
SPACE = int.from_bytes(b" ", byteorder="big")
COLON = int.from_bytes(b":", byteorder="big")

# currently supports:
# normal chars


def expand_word(word: list[int], flags: list[WordDescFlag]) -> list[ArgChar]:
    new_string = []

    i = 0
    while True:
        if i >= len(word):
            break

        c = word[i]

        if c == CTLESC:
            i += 1
            new_string.append(CArgChar(utf8_to_unicode(word[i]), bash_mode=True))
            i += 1
        elif c == BACK_SLASH:
            if (i + 1 < len(word) and word[i + 1] == CTLESC) and (
                not (i + 2 < len(word) and word[i + 2] == CTLNUL)
                or (i + 2 >= len(word))
            ):
                new_string.append(CArgChar(utf8_to_unicode(word[i]), bash_mode=True))
                i += 1
                new_string.append(CArgChar(utf8_to_unicode(word[i]), bash_mode=True))
                i += 1
            else:
                new_string.append(CArgChar(utf8_to_unicode(word[i]), bash_mode=True))
                i += 1
        else:
            new_string.append(CArgChar(utf8_to_unicode(word[i]), bash_mode=True))
            i += 1

    return new_string


def bytes_needed(n):
    if n == 0:
        return 1
    return int(log(n, 256)) + 1


def utf8_to_unicode(c: int) -> int:
    num_bytes = bytes_needed(c)
    b = c.to_bytes(num_bytes, byteorder="big")
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        return c
    return ord(s)
