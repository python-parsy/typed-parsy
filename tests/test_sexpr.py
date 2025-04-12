import unittest
from typing import List, TypeVar, Union

from parsy import Parser, ParserReference, generate, regex, string

whitespace = regex(r"\s+")
comment = regex(r";.*")
ignore = (whitespace | comment).many()

T = TypeVar("T")


def lexeme(parser: Parser[T]) -> Parser[T]:
    return parser << ignore


lparen = lexeme(string("("))
rparen = lexeme(string(")"))
number = lexeme(regex(r"\d+")).map(int)
symbol = lexeme(regex(r"[\d\w_-]+"))
true = lexeme(string("#t")).result(True)
false = lexeme(string("#f")).result(False)

atom = true | false | number | symbol

PT = Union[str, bool, int, List["PT"]]


@generate
def _expr() -> ParserReference[PT]:
    # expr is referred to before it's defined
    return (yield expr)


# expr is indirectly used via _expr
form = lparen >> _expr.many() << rparen
quote = string("'") >> _expr.map(lambda e: ["quote", e])

# Here, expr is finally defined, combining parsers which already refer to it via
# _expr, which creates a recursive parser
expr = form | quote | atom
program = ignore >> expr.many()


class TestSexpr(unittest.TestCase):
    def test_form(self):
        result = program.parse("(1 2 3)")
        self.assertEqual(result, [[1, 2, 3]])

    def test_quote(self):
        result = program.parse("'foo '(bar baz)")
        self.assertEqual(result, [["quote", "foo"], ["quote", ["bar", "baz"]]])

    def test_double_quote(self):
        result = program.parse("''foo")
        self.assertEqual(result, [["quote", ["quote", "foo"]]])

    def test_boolean(self):
        result = program.parse("#t #f")
        self.assertEqual(result, [True, False])

    def test_comments(self):
        result = program.parse(
            """
            ; a program with a comment
            (           foo ; that's a foo
            bar )
            ; some comments at the end
            """
        )

        self.assertEqual(result, [["foo", "bar"]])


if __name__ == "__main__":
    unittest.main()
