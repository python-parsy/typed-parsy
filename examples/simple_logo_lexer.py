"""
Stripped down logo lexer, for tokenizing Turtle Logo programs like:

   fd 1
   bk 2
   rt 90

etc.
"""

from parsy import Parser, eof, regex, string, string_from, whitespace

command = string_from("fd", "bk", "rt", "lt")
number = regex(r"[0-9]+").map(int)
optional_whitespace = regex(r"\s*")
eol = string("\n")
line = (optional_whitespace >> command) & (whitespace >> number) & (eof | eol | (whitespace >> eol)).result("\n")
lexer: Parser[list[object]] = line.many().map(lambda lines: sum(([t0, t1, t2] for ((t0, t1), t2) in lines), []))


def test_lexer() -> None:
    assert (
        lexer.parse(
            """fd 1
bk 2
"""
        )
        == ["fd", 1, "\n", "bk", 2, "\n"]
    )
